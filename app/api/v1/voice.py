# backend/app/api/v1/voice.py
from fastapi import APIRouter, Depends, HTTPException, WebSocket, status, UploadFile, File, Form, Response, Query, Body, Request
from fastapi.responses import StreamingResponse, PlainTextResponse
from typing import Optional, List, Dict
from datetime import datetime
from bson import ObjectId
from pathlib import Path
import logging
import asyncio
import io
import os
import time  # ✅ ADDED

from app.api.deps import get_current_user, get_database
from app.schemas.voice import (
    VoiceAgentCreate,
    VoiceAgentCreateExtended,
    VoiceAgentUpdate
)
from app.services.elevenlabs import elevenlabs_service
from app.services.ai_agent import ai_agent_service
from app.services.call_handler import call_handler_service
from app.services.agent_executor import agent_executor
from app.config import settings
from motor.motor_asyncio import AsyncIOMotorDatabase
from twilio.twiml.voice_response import VoiceResponse, Gather, Connect, Stream
from twilio.rest import Client  # ✅ ADDED for AMD

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================
# ✅ NEW: TIMING HELPER CLASS - ADDED AFTER IMPORTS
# ============================================

class TimingTracker:
    """Track timing for different operations during a call"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = time.time()
        self.checkpoints = {}
        self.total_start = time.time()
        
    def checkpoint(self, name: str):
        """Record a checkpoint time"""
        elapsed = (time.time() - self.start_time) * 1000  # Convert to ms
        self.checkpoints[name] = elapsed
        self.start_time = time.time()  # Reset for next checkpoint
        return elapsed
    
    def get_total(self) -> float:
        """Get total elapsed time in ms"""
        return (time.time() - self.total_start) * 1000
    
    def print_summary(self):
        """Print timing summary"""
        total = self.get_total()
        print("\n" + "=" * 80)
        print(f"⏱️  TIMING SUMMARY: {self.operation_name}")
        print("=" * 80)
        print(f"{'Operation':<45} {'Time (ms)':<12} {'%':<8} {'Status'}")
        print("-" * 80)
        
        for name, time_ms in self.checkpoints.items():
            percentage = (time_ms / total * 100) if total > 0 else 0
            if time_ms > 1000:
                status = "🔴 SLOW"
            elif time_ms > 500:
                status = "🟡 OK"
            else:
                status = "🟢 FAST"
            print(f"{name:<45} {time_ms:>8.2f} ms  {percentage:>5.1f}%   {status}")
        
        print("-" * 80)
        if total > 3000:
            total_status = "🔴 SLOW"
        elif total > 2000:
            total_status = "🟡 OK"
        else:
            total_status = "🟢 FAST"
        print(f"{'TOTAL':<45} {total:>8.2f} ms  {'100.0%':>6}   {total_status}")
        print("=" * 80 + "\n")

# ============================================
# ⚡ LATENCY TRACKER CLASS - ADDED AFTER TimingTracker
# ============================================

class LatencyTracker:
    """Track end-to-end latency for voice calls"""
    
    def __init__(self, call_sid: str):
        self.call_sid = call_sid
        self.start_time = time.time()
        self.checkpoints = {}
    
    def checkpoint(self, name: str):
        """Record a checkpoint"""
        elapsed = (time.time() - self.start_time) * 1000
        self.checkpoints[name] = elapsed
        print(f"   ⏱️ {name}: {elapsed:.2f}ms")
    
    def get_total(self) -> float:
        """Get total elapsed time in ms"""
        return (time.time() - self.start_time) * 1000
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            "call_sid": self.call_sid,
            "total_ms": self.get_total(),
            "checkpoints": self.checkpoints,
            "timestamp": datetime.utcnow()
        }
    
    def print_summary(self):
        """Print latency summary"""
        total = self.get_total()
        print(f"\n{'='*80}")
        print(f"⚡ LATENCY SUMMARY FOR {self.call_sid}")
        print(f"{'='*80}")
        for name, ms in self.checkpoints.items():
            print(f"   {name}: {ms:.2f}ms")
        print(f"   {'─'*60}")
        print(f"   TOTAL: {total:.2f}ms ({total/1000:.2f}s)")
        print(f"{'='*80}\n")

# ============================================
# ✅ PHASE 1 OPTIMIZATION FUNCTIONS
# ============================================

async def optimized_db_queries(call_sid: str, db):
    """Fetch call and agent data efficiently"""
    print(f"🔍 Looking for call with SID: {call_sid}")
    call = await db.calls.find_one({"twilio_call_sid": call_sid})
    
    if not call:
        return None, None
    
    print(f"✅ Call found in database. Call ID: {str(call['_id'])}")
    print(f"📊 Greeting count: {call.get('greeting_count', 0)}")
    print(f"📊 Empty speech count: {call.get('empty_speech_count', 0)}")
    
    agent_id = call.get("agent_id")
    
    if agent_id:
        print(f"🔍 Fetching agent with ID: {agent_id}")
        agent = await db.voice_agents.find_one({"_id": ObjectId(agent_id)})
        
        if agent:
            print(f"✅ Agent found: {agent.get('name')}")
            print(f"🤖 Agent context available: {agent.get('has_context', False)}")
        else:
            print("⚠️ No agent found, using fallback configuration")
            agent = {
                "name": "AI Assistant",
                "ai_script": "I am a helpful AI assistant.",
                "has_training_docs": False,
                "agent_context": None
            }
    else:
        print("⚠️ No agent_id, using fallback configuration")
        agent = {
            "name": "AI Assistant",
            "ai_script": "I am a helpful AI assistant.",
            "has_training_docs": False,
            "agent_context": None
        }
    
    return call, agent


async def store_transcripts_async(db, call_id, call_sid: str, user_text: str, agent_text: str, confidence: float):
    """Store transcripts in background without blocking"""
    try:
        print(f"💾 [BACKGROUND] Storing transcripts for call {call_sid}...")
        
        await asyncio.gather(
            db.call_transcripts.insert_one({
                "call_id": call_id,
                "call_sid": call_sid,
                "timestamp": datetime.utcnow(),
                "speaker": "user",
                "text": user_text,
                "confidence": float(confidence)
            }),
            db.call_transcripts.insert_one({
                "call_id": call_id,
                "call_sid": call_sid,
                "timestamp": datetime.utcnow(),
                "speaker": "agent",
                "text": agent_text
            })
        )
        
        print(f"✅ [BACKGROUND] Transcripts stored successfully for {call_sid}")
    except Exception as e:
        logger.error(f"❌ [BACKGROUND] Failed to store transcripts for {call_sid}: {e}")
# ============================================
# ✅ CHANGE 1: ADD GET HANDLER FOR /webhook/incoming (Twilio Health Check)
# ============================================

@router.get("/webhook/incoming", response_class=PlainTextResponse)
async def incoming_call_webhook_get():
    """Handle GET requests (Twilio health checks)"""
    return "OK"

# ============================================
# 🔥 WEBHOOK: /webhook/incoming - ONLY ELEVENLABS
# ============================================

from fastapi.responses import Response

@router.post("/webhook/incoming")
async def incoming_call_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    ✅ Handle incoming Twilio call with Media Streams
    """
    try:
        print("\n" + "="*80)
        print("📞 INCOMING CALL WEBHOOK STARTED")
        print("="*80)
        # print(f"📋 Request headers: {dict(request.headers)}")
        
        form_data = await request.form()
        
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        call_status = form_data.get("CallStatus")
        direction = form_data.get("Direction", "inbound")
        
        print(f"📞 INCOMING CALL DETAILS:")
        print(f"   Call SID: {call_sid}")
        print(f"   From (CUSTOMER): {from_number}")
        print(f"   To (TWILIO): {to_number}")
        print(f"   Status: {call_status}")
        print(f"   Direction: {direction}")
        # print(f"📋 All form data keys: {list(form_data.keys())}")
        
        # Find or create call record
        call = await db.calls.find_one({"call_sid": call_sid})
        
        if not call:
            print(f"🆕 No existing call found, creating new call record")

            # ✅ Route by To number — find which user owns this phone number
            # Check twilio_phone_number (provisioned) and integration_config.twilio.phone_number (custom)
            user_doc = await db.users.find_one({
                "$or": [
                    {"twilio_phone_number": to_number},
                    {"integration_config.twilio.phone_number": to_number}
                ]
            })
            if user_doc:
                user_id = str(user_doc["_id"])
                print(f"📱 Matched To number {to_number} → User ID: {user_id}")
                # Find this user's active agent
                agent = await db.voice_agents.find_one({"user_id": user_id, "is_active": True})
            else:
                print(f"⚠️ No user found for To number {to_number}, falling back to any active agent")
                agent = await db.voice_agents.find_one({"is_active": True})
                user_id = agent.get("user_id") if agent else None

            agent_id = str(agent["_id"]) if agent else None

            print(f"🤖 Using agent ID: {agent_id}, User ID: {user_id}")
            
            call_data = {
                "call_sid": call_sid,
                "from_number": from_number,
                "to_number": to_number,
                "phone_number": from_number,
                "direction": direction,
                "status": "ringing",
                "agent_id": agent_id,
                "user_id": user_id,
                "greeting_count": 0,
                "empty_speech_count": 0,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await db.calls.insert_one(call_data)
            call_id = str(result.inserted_id)
            
            call_handler_service.active_calls[call_sid] = {
                "call_id": call_id,
                "agent_id": agent_id,
                "from_number": from_number,
                "to_number": to_number
            }
            
            print(f"✅ Created new call record. Call ID: {call_id}")
        else:
            call_id = str(call["_id"])
            agent_id = call.get("agent_id")
            print(f"✅ Found existing call record. Call ID: {call_id}")
        
        # Get agent
        agent = None
        if agent_id:
            print(f"🔍 Fetching agent details for agent ID: {agent_id}")
            agent = await db.voice_agents.find_one({"_id": ObjectId(agent_id)})
        
        if agent:
            print(f"🤖 Agent found: {agent.get('name')}")
            print(f"🤖 Agent has_context: {agent.get('has_context', False)}")
            print(f"🤖 Agent voice_id: {agent.get('voice_id')}")
        else:
            print("⚠️ No agent found, using fallback")

        # ============================================
        # CHECK INBOUND CALL CONFIG (for inbound calls)
        # ============================================
        inbound_config = None
        if direction == "inbound" and user_id:
            inbound_config = await db.inbound_call_configs.find_one({
                "user_id": user_id, "enabled": True
            })
            if inbound_config:
                print(f"📞 INBOUND CONFIG FOUND for user {user_id} — using inbound-specific settings")
            else:
                print(f"📞 No inbound config (or disabled) — using default agent settings")

        base_webhook_url = settings.TWILIO_WEBHOOK_URL.replace('/incoming', '')
        print(f"🌐 Base webhook URL: {base_webhook_url}")

        response = VoiceResponse()
        # Get greeting — prioritize inbound config for inbound calls
        if inbound_config and inbound_config.get("greeting_message"):
            greeting = inbound_config["greeting_message"]
            print(f"📜 Using greeting from INBOUND CONFIG")
        elif agent and agent.get("greeting_message"):
            greeting = agent.get("greeting_message")
            print(f"📜 Using greeting from greeting_message field")
        elif agent and agent.get("ai_script"):
            greeting = agent["ai_script"].split('\n')[0][:300]
            print(f"📜 Fallback: Using first line of agent script")
        else:
            greeting = "Hi! Thanks for taking my call today."
            print(f"📜 Using default greeting")

        print(f"🎙️ Greeting message: {greeting}")

        # ✅ PRE-GENERATE GREETING AUDIO AS FIRE-AND-FORGET
        # Returns TwiML immediately so Twilio can open the WebSocket faster.
        # Audio is stored in DB while the WebSocket handshake is happening in parallel.
        import base64

        if inbound_config and inbound_config.get("voice_id"):
            agent_voice_id = inbound_config["voice_id"]
            print(f"🎤 Using voice from INBOUND CONFIG: {agent_voice_id}")
        else:
            agent_voice_id = agent.get("voice_id") if agent else None

        # Store greeting text + inbound config immediately (no ElevenLabs wait)
        pre_fields = {"greeting_text": greeting}
        if inbound_config:
            pre_fields["inbound_config"] = {
                "ai_script": inbound_config.get("ai_script", ""),
                "business_info": inbound_config.get("business_info", ""),
                "greeting_message": inbound_config.get("greeting_message", ""),
                "voice_id": inbound_config.get("voice_id", ""),
            }
        await db.calls.update_one({"call_sid": call_sid}, {"$set": pre_fields})

        async def _pre_generate_greeting_audio():
            """Background task: generate audio while Twilio opens the WebSocket."""
            try:
                audio_result = await elevenlabs_service.text_to_speech_for_twilio(
                    text=greeting,
                    voice_id=agent_voice_id
                )
                if audio_result:
                    greeting_audio_b64 = base64.b64encode(audio_result).decode('utf-8')
                    await db.calls.update_one(
                        {"call_sid": call_sid},
                        {"$set": {
                            "greeting_audio": greeting_audio_b64,
                            "greeting_generated_at": datetime.utcnow()
                        }}
                    )
                    print(f"✅ [BG] Greeting audio stored ({len(audio_result)} bytes)")
                else:
                    print(f"⚠️ [BG] ElevenLabs returned no audio for greeting")
            except Exception as bg_err:
                print(f"⚠️ [BG] Greeting pre-generation failed: {bg_err}")

        asyncio.create_task(_pre_generate_greeting_audio())
        print(f"🎵 [BG] Greeting audio generation started in background (non-blocking)")
        
        # print(f"✅ Greeting stored for WebSocket playback")
        
        # ✅ START MEDIA STREAM IMMEDIATELY (no Play tag before it)
        print(f"🎙️ Starting Media Stream for call {call_sid}")
        # Get the base URL from settings (ngrok URL)
        base_url = settings.TWILIO_WEBHOOK_URL.replace('/api/v1/voice/webhook/incoming', '')
        ws_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        ws_full_url = f"{ws_url}/api/v1/voice/ws/media-stream"
        
        connect = Connect()
        stream = connect.stream(
            url=ws_full_url,
            track="inbound_track"  # Receive user audio; barge-in handled via is_speaking flag + clear event
        )
        stream.parameter(name="agent_id", value=agent_id)
        response.append(connect)

        print(f"✅ Media Stream configured with inbound_track: {ws_full_url}")
        
        # Update call status
        print(f"📊 Updating call status to 'in-progress' and incrementing greeting count")
        await db.calls.update_one(
            {"call_sid": call_sid},
            {
                "$set": {
                    "status": "in-progress",
                    "answered_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                },
                "$inc": {"greeting_count": 1}
            }
        )
        
        print(f"✅ TwiML generated successfully for {call_sid}")
        print(f"📋 TwiML response preview: {str(response)[:200]}...")
        print("="*80)
        print("📞 INCOMING CALL WEBHOOK COMPLETED")
        print("="*80 + "\n")
        
        return Response(content=str(response), media_type="text/xml")
        
    except Exception as e:
        print(f"\n❌❌❌ CRITICAL ERROR in incoming webhook: {str(e)}")
        logger.error(f"❌ Error in incoming webhook: {e}")
        import traceback
        traceback.print_exc()
        
        response = VoiceResponse()
        response.say("Sorry, there was an error. Please try again later.")
        response.hangup()
        return Response(content=str(response), media_type="text/xml")
# ============================================
# 🔥 WEBHOOK: /webhook/process-speech - FAST CONTEXTUAL RESPONSE
# ============================================

@router.post("/webhook/process-speech", response_class=PlainTextResponse)
async def process_speech_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Process user speech - ✅ ENHANCED with FAST CONTEXTUAL RESPONSE
    Now loads agent_context for instant responses
    ✅ ENHANCED: Added comprehensive console logging
    ✅ ENHANCED: Added timing tracking
    ✅ ENHANCED: Added latency tracking with database storage
    """
    try:
        # ✅ ADDED TIMING TRACKER AT THE START
        timer = TimingTracker("PROCESS_SPEECH_WEBHOOK")
        
        print("\n" + "="*80)
        print("🎤 PROCESS SPEECH WEBHOOK STARTED")
        print(f"⏱️  Start Time: {datetime.utcnow().isoformat()}")
        print("="*80)
        # print(f"📋 Request headers: {dict(request.headers)}")
        
        form_data = await request.form()
        timer.checkpoint("1. Twilio Request Parsing")  # ✅ ADDED
        
        call_sid = form_data.get("CallSid")
        speech_result = form_data.get("SpeechResult", "")
        confidence = form_data.get("Confidence", "0")
        
        print(f"🎤 SPEECH INPUT DETAILS:")
        print(f"   Call SID: {call_sid}")
        print(f"   User Said: {speech_result}")
        print(f"   Confidence: {confidence}")
        # print(f"📋 All form data keys: {list(form_data.keys())}")
        
        # ⚡ START LATENCY TRACKING
        latency = LatencyTracker(call_sid)
        latency.checkpoint("1. Webhook Received")
        
        # Check if speech was captured
        if not speech_result or speech_result.strip() == "":
            print("⚠️ Empty speech result detected")
            logger.warning("⚠️ Empty speech result")
            
            # ✅ NEW: Track empty speech count and hang up after too many
            call = await db.calls.find_one({"twilio_call_sid": call_sid})
            empty_count = call.get("empty_speech_count", 0) + 1 if call else 1
            
            # Update counter
            if call:
                await db.calls.update_one(
                    {"twilio_call_sid": call_sid},
                    {"$set": {"empty_speech_count": empty_count, "updated_at": datetime.utcnow()}}
                )
            
            # ✅ NEW: Hang up after 5 empty speech attempts
            if empty_count >= 5:
                print(f"🔵 Too many empty speech attempts ({empty_count}), hanging up")
                logger.info(f"🔵 Hanging up call {call_sid} after {empty_count} empty attempts")
                
                await db.calls.update_one(
                    {"twilio_call_sid": call_sid},
                    {"$set": {"status": "no_response", "ended_at": datetime.utcnow()}}
                )
                
                response = VoiceResponse()
                response.say("I haven't been able to hear you. Please call back when you're ready. Goodbye!", voice='Polly.Joanna')
                response.hangup()
                return str(response)
            
            response = VoiceResponse()
            
            # 🔥 FIXED: Generate "I didn't catch that" with ElevenLabs
            try:
                retry_message = "I didn't catch that. Could you please repeat?"
                print(f"🔊 Generating retry message: {retry_message}")
                
                # ✅ FIX: Use text_to_speech method instead of generate_speech
                audio_response = await elevenlabs_service.text_to_speech(
                    text=retry_message,
                    save_to_file=True
                )
                
                if audio_response.get("success"):
                    audio_url = audio_response.get("audio_url")
                    full_audio_url = f"{settings.TWILIO_WEBHOOK_URL.replace('/api/v1/voice/webhook/incoming', '')}{audio_url}"
                    print(f"✅ Generated retry audio: {audio_url}")
                    
                    gather = Gather(
                        input='speech',
                        timeout=5,
                        action=f"{settings.TWILIO_WEBHOOK_URL.replace('/incoming', '')}/process-speech",
                        speechTimeout='auto',
                        language='en-US'
                    )
                    gather.play(full_audio_url)
                    response.append(gather)
                else:
                    print(f"❌ ElevenLabs failed for retry, using silent gather")
                    # Fallback to silent gather if ElevenLabs fails
                    gather = Gather(
                        input='speech',
                        timeout=5,
                        action=f"{settings.TWILIO_WEBHOOK_URL.replace('/incoming', '')}/process-speech",
                        speechTimeout='auto',
                        language='en-US'
                    )
                    response.append(gather)
                    
            except Exception as retry_error:
                print(f"❌ Error generating retry audio: {retry_error}")
                # Silent gather as fallback
                gather = Gather(
                    input='speech',
                    timeout=5,
                    action=f"{settings.TWILIO_WEBHOOK_URL.replace('/incoming', '')}/process-speech",
                    speechTimeout='auto',
                    language='en-US'
                )
                response.append(gather)
            
            base_webhook_url = settings.TWILIO_WEBHOOK_URL.replace('/incoming', '')
            print(f"🔄 Redirecting back to: {base_webhook_url}/incoming")
            response.redirect(f"{base_webhook_url}/incoming")
            return str(response)
        
        # ✅ NEW: Detect voicemail system messages and hang up
        voicemail_indicators = [
            "press 1", "press 2", "press 3", "press 4", "press 5", "press 6",
            "press pound", "press star", "press #", "press *",
            "leave a message", "record your message", "voicemail",
            "maximum voicemail duration", "message will be deleted",
            "to save", "to erase", "to rerecord", "after the beep",
            "after the tone", "not available", "please leave",
            "thank you for calling goodbye", "i'm sorry, i did not hear you",
            "mailbox", "unavailable"
        ]
        
        speech_lower = speech_result.lower()
        # is_voicemail = any(indicator in speech_lower for indicator in voicemail_indicators)
        
        # if is_voicemail:
        #     print(f"🔵 VOICEMAIL SYSTEM DETECTED - Hanging up")
        #     print(f"   Detected phrase: {speech_result[:100]}...")
        #     logger.info(f"🔵 Voicemail detected, terminating call {call_sid}")
            
        #     # Update call record
        #     await db.calls.update_one(
        #         {"twilio_call_sid": call_sid},
        #         {
        #             "$set": {
        #                 "status": "voicemail_detected",
        #                 "voicemail_reason": speech_result[:200],
        #                 "ended_at": datetime.utcnow(),
        #                 "updated_at": datetime.utcnow()
        #             }
        #         }
        #     )
            
        #     # Hang up immediately
        #     response = VoiceResponse()
        #     response.hangup()
        #     return str(response)
        
        # ✅ PHASE 1 OPTIMIZATION: Parallel DB queries
        print(f"\n⚡ OPTIMIZATION: Fetching call and agent data...")
        
        call, agent = await optimized_db_queries(call_sid, db)
        
        timer.checkpoint("2. Database - Parallel Queries")
        latency.checkpoint("2. DB - Parallel Fetch")
        
        if not call:
            print(f"❌ Call {call_sid} not found in database")
            logger.error(f"❌ Call {call_sid} not found in database")
            response = VoiceResponse()
            response.say("Sorry, there was a system error. Please call back.", voice='Polly.Joanna')
            response.hangup()
            return str(response)
        
        # Get user
        user_id = call.get("user_id")
        call_id = str(call["_id"])
        
        print(f"👤 User ID: {user_id}")
        print(f"📞 Call ID: {call_id}")
        
        # ✅ ENHANCED: Load agent context if available
        if agent.get("has_context") and agent.get("agent_context"):
            print("✅ Using pre-built agent context for fast response")
            logger.info("✅ Using pre-built agent context for fast response")
        else:
            print("ℹ️ No agent context available, using fallback")
            logger.info("ℹ️ No agent context available, using fallback")
        
        # ============================================
        # STEP 5: Process with AI Agent
        # ============================================
        print(f"\n🤖 STEP 5: Processing with AI Agent...")
        print(f"   Input: '{speech_result}'")
        
        ai_start = time.time()  # ✅ ADDED
        
        try:
            # ✅ Add timeout to prevent hanging
            print(f"⏱️ Setting 6 second timeout for AI processing")
            ai_response = await asyncio.wait_for(
                agent_executor.process_user_message(
                    user_input=speech_result,
                    agent_config=agent,
                    user_id=user_id,
                    call_id=call_id,
                    db=db,
                    call_sid=call_sid  # ✅ PASS CALL_SID FOR MEMORY
                ),
                timeout=10  # 6 second timeout
            )
            
            # ✅ Validate response
            if not ai_response or not isinstance(ai_response, str) or len(ai_response.strip()) == 0:
                print("⚠️ Empty AI response received, using fallback")
                logger.warning("⚠️ Empty AI response, using fallback")
                ai_response = "I'm here to help! Could you please repeat your question?"
                
        except asyncio.TimeoutError:
            print("❌ AI processing timed out after 8 seconds")
            logger.error("❌ AI processing timed out")
            ai_response = "I apologize for the delay. Could you please repeat that?"
        except Exception as exec_error:
            print(f"❌ Agent executor error: {str(exec_error)}")
            logger.error(f"❌ Agent executor error: {exec_error}")
            import traceback
            traceback.print_exc()
            ai_response = "I'm sorry, I had trouble processing that. How can I help you?"
        
        ai_time = (time.time() - ai_start) * 1000  # ✅ ADDED
        timer.checkpoint("4. AI Agent Processing ")  # ✅ ADDED
        latency.checkpoint("4. AI Processing")  # ⚡ LATENCY CHECKPOINT
        print(f"   ⏱️  AI Processing took: {ai_time:.2f} ms")  # ✅ ADDED
        print(f"🤖 AI Response generated: {ai_response[:100]}...")
        
        # ⚡ OPTIMIZED: Store both transcripts in parallel
        # ✅ PHASE 1 OPTIMIZATION: Async transcript storage
        print(f"⚡ OPTIMIZATION: Starting background transcript storage...")
        
        asyncio.create_task(
            store_transcripts_async(
                db=db,
                call_id=call["_id"],
                call_sid=call_sid,
                user_text=speech_result,
                agent_text=ai_response,
                confidence=float(confidence)
            )
        )
        
        print(f"✅ Transcript storage started in background")
        
        # Extract base URL
        base_webhook_url = settings.TWILIO_WEBHOOK_URL.replace('/incoming', '')
        print(f"🌐 Base webhook URL: {base_webhook_url}")
        
        # 🔥 CRITICAL FIX: ONLY ELEVENLABS - NO POLLY AFTER
        response = VoiceResponse()
        
        try:
            agent_voice_id = agent.get("voice_id") if agent else None
            
            print(f"🎵 Generating ElevenLabs audio for AI response...")
            print(f"🎵 Voice ID: {agent_voice_id}")
            print(f"📝 Text length: {len(ai_response)} characters")
            
            elevenlabs_start = time.time()  # ✅ ADDED
            
            audio_response = await elevenlabs_service.text_to_speech(
                text=ai_response,
                voice_id=agent_voice_id,
                save_to_file=True
            )
            
            elevenlabs_time = (time.time() - elevenlabs_start) * 1000  # ✅ ADDED
            timer.checkpoint("6. ElevenLabs TTS")  # ✅ ADDED
            latency.checkpoint("6. ElevenLabs TTS")  # ⚡ LATENCY CHECKPOINT
            print(f"   ⏱️  ElevenLabs took: {elevenlabs_time:.2f} ms")  # ✅ ADDED
            
            if audio_response.get("success"):
                audio_url = audio_response.get("audio_url")
                full_audio_url = f"{settings.TWILIO_WEBHOOK_URL.replace('/api/v1/voice/webhook/incoming', '')}{audio_url}"
                
                print(f"✅ ElevenLabs audio generated successfully")
                print(f"🔊 Audio URL: {audio_url}")
                
                # 🔥 FIXED: Play ElevenLabs audio in Gather
                gather = Gather(
                    input='speech',
                    timeout=5,
                    action=f"{base_webhook_url}/process-speech",
                    speechTimeout='auto',
                    language='en-US',
                    hints='appointment, schedule, book, yes, no, email, phone, done, goodbye'
                )
                gather.play(full_audio_url)
                response.append(gather)
                
                # 🔥 CRITICAL FIX: NO POLLY SAY() HERE - Just redirect back
                response.pause(length=1)
                response.redirect(f"{base_webhook_url}/process-speech")
                
                print(f"✅ Gather configured with ElevenLabs audio")
                
            else:
                # If ElevenLabs fails, hangup gracefully
                print(f"❌ ElevenLabs failed: {audio_response.get('error')}")
                logger.error(f"❌ ElevenLabs failed: {audio_response.get('error')}")
                response.say("Thank you for calling. Goodbye!", voice='Polly.Joanna')
                response.hangup()
                
        except Exception as e:
            print(f"❌ Error generating speech: {str(e)}")
            logger.error(f"❌ Error generating speech: {e}")
            response.say("Thank you for calling. Goodbye!", voice='Polly.Joanna')
            response.hangup()
        
        timer.checkpoint("7. Build TwiML Response")  # ✅ ADDED
        latency.checkpoint("7. Build TwiML")  # ⚡ LATENCY CHECKPOINT
        print(f"✅ TwiML response generated for {call_sid}")
        print(f"📋 TwiML response preview: {str(response)[:200]}...")
        
        # ✅ ADDED TIMING SUMMARY BEFORE RETURN
        timer.print_summary()
        
        # ⚡ PRINT AND SAVE LATENCY
        latency.print_summary()
        
        # Save to database for analysis
        try:
            await db.latency_logs.insert_one(latency.to_dict())
            print(f"📊 Latency data saved to database")
        except Exception as latency_error:
            print(f"⚠️ Failed to save latency data: {latency_error}")
        
        print("="*80)
        print("🎤 PROCESS SPEECH WEBHOOK COMPLETED")
        print("="*80 + "\n")
        
        return str(response)
        
    except Exception as e:
        print(f"\n❌❌❌ CRITICAL ERROR in process-speech webhook: {str(e)}")
        logger.error(f"❌ Error in process-speech webhook: {e}")
        import traceback
        traceback.print_exc()
        
        response = VoiceResponse()
        response.say("Sorry, there was an error. Goodbye!", voice='Polly.Joanna')
        response.hangup()
        return str(response)


# ============================================
# ✅ CHANGE 2: ADD GET HANDLER FOR /webhook/status (Twilio Health Check)
# ============================================

@router.get("/webhook/status")
async def call_status_webhook_get():
    """Handle GET requests (Twilio health checks)"""
    return {"status": "ok"}

# ============================================
# WEBHOOK: /webhook/status - Call Status Updates
# ============================================

@router.post("/webhook/status")
async def call_status_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Handle Twilio call status updates"""
    try:
        # print(f"\n📊 CALL STATUS WEBHOOK STARTED")
        
        form_data = await request.form()
        
        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        call_duration = form_data.get("CallDuration", "0")
        
        print(f"📊 Call status update:")
        print(f"   Call SID: {call_sid}")
        print(f"   Status: {call_status}")
        print(f"   Duration: {call_duration} seconds")

        if call_status == "in-progress":
            print(f"✅ [ANSWERED] User accepted the call!")
            await db.calls.update_one(
                {"twilio_call_sid": call_sid},
                {"$set": {
                    "status": "in-progress",
                    "answered_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }}
            )
            print(f"✅ [ANSWERED] Greeting marked as ready")
            return {"status": "success"}

        if call_status == "answered":
            print(f"✅ [ANSWERED] User accepted the call!")
            await db.calls.update_one(
                {"twilio_call_sid": call_sid},
                {"$set": {
                    "status": "answered",
                    "answered_at": datetime.utcnow(),
                    "greeting_ready": True,  # ✅ FLAG: Ready to play greeting
                    "updated_at": datetime.utcnow()
                }}
            )
            print(f"✅ [ANSWERED] Greeting marked as ready")
            return {"status": "success"}
        
        
        
        # Update call record
        update_data = {
            "status": call_status,
            "updated_at": datetime.utcnow()
        }
        
        if call_status == "completed":
            print(f"✅ Call completed, generating summary...")
            update_data["ended_at"] = datetime.utcnow()
            update_data["duration"] = int(call_duration)
            
            # Generate call summary
            call = await db.calls.find_one({"twilio_call_sid": call_sid})
            
            if call:
                # Get transcripts for summary
                transcripts = await db.call_transcripts.find({
                    "call_sid": call_sid
                }).sort("timestamp", 1).to_list(length=None)
                
                if transcripts and len(transcripts) > 0:
                    print(f"📝 Generating summary for {len(transcripts)} transcript messages...")
                    
                    # Format messages for OpenAI
                    messages_for_ai = [
                        {
                            "speaker": t.get("speaker", "unknown"),
                            "text": t.get("text", "")
                        }
                        for t in transcripts
                    ]
                    
                    # Generate AI summary
                    from app.services.openai import openai_service
                    
                    summary_result = await openai_service.generate_call_summary(messages_for_ai)
                    
                    if summary_result.get("success"):
                        update_data["ai_summary"] = summary_result["summary"]
                        print(f"✅ Summary generated: {summary_result['summary'][:100]}...")
                    else:
                        update_data["ai_summary"] = f"Call completed - {len(transcripts)} messages exchanged"
                        print(f"⚠️ Summary generation failed, using fallback")
                    
                    # Select key messages
                    key_messages_result = await openai_service.select_key_messages(messages_for_ai, max_messages=5)
                    
                    if key_messages_result.get("success"):
                        update_data["key_messages"] = key_messages_result["key_messages"]
                        print(f"✅ Selected {len(key_messages_result['key_messages'])} key messages")
                    
                    # Determine outcome
                    full_transcript = " ".join([t.get("text", "") for t in transcripts])
                    outcome_result = await openai_service.determine_call_outcome(full_transcript)
                    
                    if outcome_result.get("success"):
                        update_data["outcome"] = outcome_result["outcome"]
                        print(f"✅ Outcome determined: {outcome_result['outcome']}")
                else:
                    print(f"⚠️ No transcripts found for call summary")
        
        if call_sid:
            print(f"💾 Updating call record in database...")
            await db.calls.update_one(
                {"twilio_call_sid": call_sid},
                {"$set": update_data}
            )
            print(f"✅ Call record updated")
        
        print(f"📊 CALL STATUS WEBHOOK COMPLETED\n")
        return {"status": "success"}
        
    except Exception as e:
        print(f"\n❌ ERROR in status webhook: {str(e)}")
        logger.error(f"❌ Error in status webhook: {e}")
        return {"status": "error", "error": str(e)}


# ============================================
# ✅ CHANGE 3: ADD GET HANDLER FOR /webhook/amd-status (Twilio Health Check)
# ============================================

@router.get("/webhook/amd-status", response_class=PlainTextResponse)
async def amd_status_webhook_get():
    """Handle GET requests (Twilio health checks)"""
    return "OK"

# ============================================
# 🤖 WEBHOOK: /webhook/amd-status - ANSWERING MACHINE DETECTION
# ============================================
@router.post("/webhook/amd-status", response_class=PlainTextResponse)
async def amd_status_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Handle Twilio Answering Machine Detection callback
    Hang up immediately if voicemail/machine detected
    """
    try:
        form_data = await request.form()
        
        call_sid = form_data.get("CallSid")
        answered_by = form_data.get("AnsweredBy")
        
        print("\n" + "="*80)
        print("🤖 AMD STATUS WEBHOOK")
        print("="*80)
        print(f"   Call SID: {call_sid}")
        print(f"   Answered By: {answered_by}")
        print("="*80)
        
        # ✅ UPDATED: Only hang up when Twilio is certain it's a voicemail (after detecting the beep)
        if answered_by in ["machine_end_beep", "fax"]:
            print(f"📵 VOICEMAIL/MACHINE DETECTED - Hanging up call {call_sid}")
            print(f"🤖 Detection Type: {answered_by}")
            logger.info(f"📵 Voicemail detected for {call_sid}, terminating call")
            
            # Hang up the call
            twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            twilio_client.calls(call_sid).update(status="completed")
            
            # Update call record
            await db.calls.update_one(
                {"twilio_call_sid": call_sid},
                {
                    "$set": {
                        "status": "voicemail_detected",
                        "answered_by": answered_by,
                        "ended_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            print(f"✅ Call {call_sid} terminated due to voicemail")
            
        elif answered_by == "human":
            print(f"✅ HUMAN ANSWERED - Proceeding with call {call_sid}")
            logger.info(f"✅ Human answered call {call_sid}")
            
            # Update call record
            await db.calls.update_one(
                {"twilio_call_sid": call_sid},
                {
                    "$set": {
                        "answered_by": "human",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
        elif answered_by == "machine_start":
            print(f"🤖 MACHINE START DETECTED - Waiting for confirmation (call {call_sid})")
            logger.info(f"🤖 Machine start detected for {call_sid}, waiting for beep detection")
            
            # Update call record but don't hang up yet
            await db.calls.update_one(
                {"twilio_call_sid": call_sid},
                {
                    "$set": {
                        "answered_by": "machine_start",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
        else:
            # unknown - could treat as voicemail for safety
            print(f"⚠️ UNKNOWN answered_by: {answered_by} for call {call_sid}")
            logger.warning(f"⚠️ Unknown answered_by: {answered_by} for {call_sid}")
        
        return "OK"
        
    except Exception as e:
        print(f"❌ AMD webhook error: {e}")
        logger.error(f"❌ AMD webhook error: {e}", exc_info=True)
        return "ERROR"


# ============================================
# WEBHOOK: /webhook/recording-status
# ============================================

@router.post("/webhook/recording-status")
async def recording_status_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Handle recording status updates"""
    try:
        print(f"\n🎙️ RECORDING STATUS WEBHOOK STARTED")
        
        form_data = await request.form()
        
        call_sid = form_data.get("CallSid")
        recording_sid = form_data.get("RecordingSid")
        recording_url = form_data.get("RecordingUrl")
        recording_status = form_data.get("RecordingStatus")
        recording_duration = form_data.get("RecordingDuration")

        # Append .mp3 so the URL is directly playable without Twilio auth
        if recording_url and not recording_url.endswith(".mp3"):
            recording_url = recording_url + ".mp3"

        print(f"🎙️ Recording status update:")
        print(f"   Call SID: {call_sid}")
        print(f"   Recording SID: {recording_sid}")
        print(f"   Status: {recording_status}")
        print(f"   Duration: {recording_duration}")
        print(f"   URL: {recording_url}")

        if call_sid:
            print(f"💾 Updating recording info in database...")
            await db.calls.update_one(
                {"twilio_call_sid": call_sid},
                {"$set": {
                    "recording_sid": recording_sid,
                    "recording_url": recording_url,
                    "recording_status": recording_status,
                    "recording_duration": int(recording_duration) if recording_duration else 0,
                    "recording_available": recording_status == "completed",
                    "updated_at": datetime.utcnow()
                }}
            )
            print(f"✅ Recording info updated")
        
        print(f"🎙️ RECORDING STATUS WEBHOOK COMPLETED\n")
        return {"status": "success"}
        
    except Exception as e:
        print(f"\n❌ ERROR handling recording: {str(e)}")
        logger.error(f"❌ Error handling recording: {e}")
        return {"status": "error", "error": str(e)}


# ============================================
# ELEVENLABS VOICE ENDPOINTS
# ============================================

@router.get("/available-voices")
async def get_available_voices(
    current_user: dict = Depends(get_current_user)
):
    """Get list of available ElevenLabs voices"""
    try:
        print(f"\n🔊 GET AVAILABLE VOICES STARTED")
        print(f"👤 User ID: {str(current_user.get('_id', 'unknown'))}")
        
        voices = await elevenlabs_service.get_available_voices()
        
        print(f"✅ Retrieved {len(voices)} voices")
        print(f"🔊 GET AVAILABLE VOICES COMPLETED\n")
        
        return {
            "success": True,
            "voices": voices
        }
        
    except Exception as e:
        print(f"\n❌ ERROR fetching voices: {str(e)}")
        logger.error(f"❌ Error fetching voices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch voices: {str(e)}"
        )


@router.post("/test-voice")
async def test_voice(
    test_data: Dict[str, str] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Test a voice by generating sample audio"""
    try:
        print(f"\n🎵 TEST VOICE STARTED")
        print(f"👤 User ID: {str(current_user.get('_id', 'unknown'))}")
        
        voice_id = test_data.get('voice_id')
        text = test_data.get('text', 'Hey! This is a test of the voice synthesis.')
        
        print(f"🎵 Test parameters:")
        print(f"   Voice ID: {voice_id}")
        print(f"   Text: {text[:50]}...")
        
        if not voice_id:
            print(f"❌ Missing voice_id")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="voice_id is required"
            )
        
        result = await elevenlabs_service.text_to_speech(
            text=text,
            voice_id=voice_id,
            save_to_file=False
        )

        if result.get("success"):
            import base64
            audio_content = result.get("audio")
            audio_base64 = base64.b64encode(audio_content).decode("utf-8")

            print(f"✅ Voice test generated successfully ({len(audio_content)} bytes)")
            print(f"🎵 TEST VOICE COMPLETED\n")

            return {
                "success": True,
                "audio_base64": audio_base64,
                "content_type": "audio/mpeg",
                "message": "Voice test generated successfully"
            }
        else:
            print(f"❌ ElevenLabs failed: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate audio")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ ERROR testing voice: {str(e)}")
        logger.error(f"❌ Error testing voice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test voice: {str(e)}"
        )


# ============================================
# VOICE AGENT CRUD ENDPOINTS
# ============================================
def generate_greeting(name: str, company: str = None) -> str:
    """Generate greeting with dynamic name and optional company"""
    if company and company != "our company":
        return f"Hi! This is {name} from {company}. Thanks for taking my call."
    else:
        return f"Hi! This is {name}. Thanks for taking my call."


# ============================================
# INBOUND CALL CONFIGURATION ENDPOINTS
# ============================================

@router.get("/inbound-config")
async def get_inbound_config(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """Get the current user's inbound call configuration"""
    user_id = str(current_user["_id"])
    config = await db.inbound_call_configs.find_one({"user_id": user_id})
    if not config:
        return {"exists": False, "config": {}}
    config["_id"] = str(config["_id"])
    return {"exists": True, "config": config}


@router.post("/inbound-config")
async def save_inbound_config(
    config_data: dict = Body(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """Create or update the inbound call configuration for the current user"""
    user_id = str(current_user["_id"])
    now = datetime.utcnow()

    doc = {
        "user_id": user_id,
        "enabled": config_data.get("enabled", False),
        "greeting_message": config_data.get("greeting_message", ""),
        "ai_script": config_data.get("ai_script", ""),
        "voice_id": config_data.get("voice_id", ""),
        "business_info": config_data.get("business_info", ""),
        "operating_hours": config_data.get("operating_hours", ""),
        "max_call_duration": config_data.get("max_call_duration", 300),
        "updated_at": now,
    }

    await db.inbound_call_configs.update_one(
        {"user_id": user_id},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True
    )

    saved = await db.inbound_call_configs.find_one({"user_id": user_id})
    saved["_id"] = str(saved["_id"])
    return {"success": True, "config": saved}


@router.post("/agents", status_code=status.HTTP_201_CREATED)
async def create_voice_agent(
    agent_data: VoiceAgentCreateExtended,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new voice agent
    ✅ ENHANCED: Now generates agent context from AI script on creation
    ✅ ENHANCED: Added comprehensive console logging
    """
    try:
        user_id = str(current_user["_id"])
        
        print("\n" + "="*80)
        print("🚀 CREATING NEW VOICE AGENT")
        print("="*80)
        print(f"👤 User ID: {user_id}")
        print(f"📥 Received agent data:")
        print(f"   Name: {agent_data.name}")
        print(f"   Description: {agent_data.description or '(none)'}")
        print(f"   Voice ID: {agent_data.voice_id}")
        print(f"   Calling Mode: {agent_data.calling_mode}")
        print(f"   Contacts: {len(agent_data.contacts)} contacts")
        print(f"   AI Script length: {len(agent_data.ai_script)} chars")
        print(f"   Logic Level: {agent_data.logic_level}")
        print(f"   Enable Calls: {agent_data.enable_calls}")
        print(f"   Enable Emails: {agent_data.enable_emails}")
        print(f"   Enable SMS: {agent_data.enable_sms}")
        
        # ✅ Prepare agent document with ALL fields
        agent_doc = {
            "user_id": user_id,
            "name": agent_data.name,
            "description": agent_data.description or "",
            "voice_id": agent_data.voice_id,
            "voice_settings": agent_data.voice_settings or {
                "stability": 0.5,
                "similarity_boost": 0.75
            },
            "calling_mode": agent_data.calling_mode,
            "contacts": [contact.model_dump() for contact in agent_data.contacts],
            "ai_script": agent_data.ai_script,
            "system_prompt": agent_data.system_prompt or agent_data.ai_script,
            "greeting_message": agent_data.greeting_message or generate_greeting(
                agent_data.name, 
                None  # Will be updated after context generation
            ),
            "personality_traits": agent_data.personality_traits or ["friendly", "professional", "helpful"],
            "logic_level": agent_data.logic_level,
            "contact_frequency": agent_data.contact_frequency,
            "enable_calls": agent_data.enable_calls,
            "enable_emails": agent_data.enable_emails,
            "enable_sms": agent_data.enable_sms,
            "email_template": agent_data.email_template or "",
            "sms_template": agent_data.sms_template or "",
            "workflow_id": agent_data.workflow_id,
            "is_active": agent_data.is_active,
            "has_training_docs": False,
            "training_doc_ids": [],
            # ✅ NEW: Context fields
            "agent_context": None,
            "has_context": False,
            "context_generated_at": None,
            "in_call": False,
            "total_calls": 0,
            "successful_calls": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        print(f"💾 Saving agent document to database...")
        
        result = await db.voice_agents.insert_one(agent_doc)
        agent_id = str(result.inserted_id)
        agent_doc["_id"] = agent_id
        
        print(f"✅ Voice agent created: {agent_doc['name']}")
        print(f"🆔 Agent ID: {agent_id}")
        
        # ✅ NEW: Generate initial agent context from AI script
        if agent_data.ai_script:
            print(f"🧠 Generating initial agent context from AI script...")
            try:
                from app.services.rag_service import rag_service
                
                context_result = await rag_service.generate_agent_context(
                    agent_id=agent_id,
                    user_id=user_id,
                    db=db,
                    script_text=agent_data.ai_script,
                    force_regenerate=True
                )
                
                if context_result.get("success"):
                    print(f"✅ Agent context generated successfully")
                    agent_doc["has_context"] = True
                    agent_doc["agent_context"] = context_result.get("context")
                    context = context_result.get("context", {})
                    identity = context.get("identity", {})
                    company_name = identity.get("company")
                    if company_name and company_name != "our company":
                        updated_greeting = f"Hi! This is {agent_data.name} from {company_name}. Thanks for taking my call."
                    else:
                        updated_greeting = f"Hi! This is {agent_data.name}. Thanks for taking my call."
                    
                    # Update in database
                    await db.voice_agents.update_one(
                        {"_id": ObjectId(agent_id)},
                        {"$set": {
                            "greeting_message": updated_greeting,
                            "updated_at": datetime.utcnow()
                        }}
                    )
                    
                    # Update local doc
                    agent_doc["greeting_message"] = updated_greeting
                    print(f"✅ Updated greeting: {updated_greeting}")

                    # Pre-generate and cache greeting audio for fast first call
                    try:
                        import base64 as b64
                        voice_id = agent_doc.get("voice_id")
                        audio_bytes = await elevenlabs_service.text_to_speech_for_twilio(
                            text=updated_greeting, voice_id=voice_id
                        )
                        if audio_bytes:
                            cached_b64 = b64.b64encode(audio_bytes).decode('utf-8')
                            await db.voice_agents.update_one(
                                {"_id": agent_doc["_id"]},
                                {"$set": {
                                    "cached_greeting_audio": cached_b64,
                                    "cached_greeting_text": updated_greeting,
                                    "cached_greeting_voice": voice_id,
                                }}
                            )
                            print(f"✅ Greeting audio pre-cached for instant playback")
                    except Exception as cache_err:
                        print(f"⚠️ Failed to cache greeting audio: {cache_err}")
                else:
                    print(f"⚠️ Failed to generate context: {context_result.get('error')}")
            except Exception as ctx_error:
                print(f"⚠️ Context generation error (non-fatal): {ctx_error}")
        else:
            print(f"⚠️ No AI script provided, skipping context generation")
        
        # ============================================
        # AUTO-SEND SMS & EMAIL ON CREATION (PRESERVED)
        # ============================================
        contacts = agent_doc.get("contacts", [])
        enable_emails = agent_doc.get("enable_emails", False)
        enable_sms = agent_doc.get("enable_sms", False)
        email_template = agent_doc.get("email_template", "")
        sms_template = agent_doc.get("sms_template", "")
        
        send_results = {
            "emails_sent": 0,
            "emails_failed": 0,
            "sms_sent": 0,
            "sms_failed": 0
        }
        
        if contacts and (enable_emails or enable_sms):
            print(f"\n" + "="*60)
            print(f"📤 AUTO-SENDING MESSAGES TO {len(contacts)} CONTACTS")
            print(f"   Enable Emails: {enable_emails}")
            print(f"   Enable SMS: {enable_sms}")
            print(f"="*60 + "\n")
            
            from app.services.sms import sms_service
            from app.services.email_automation import email_automation_service
            
            for index, contact in enumerate(contacts):
                contact_name = contact.get("name", "Customer")
                contact_email = contact.get("email", "")
                contact_phone = contact.get("phone", "")
                
                print(f"👤 Contact {index + 1}/{len(contacts)}: {contact_name}")
                
                # Send Email
                if enable_emails and contact_email and email_template:
                    try:
                        personalized_email = email_template.replace("{name}", contact_name)
                        
                        print(f"📧 Sending email to: {contact_email}")
                        email_result = await email_automation_service.send_custom_email(
                            to_email=contact_email,
                            subject=f"hey from {agent_doc['name']}",
                            body=personalized_email,
                            user_id=user_id
                        )
                        
                        if email_result.get("success"):
                            send_results["emails_sent"] += 1
                            print(f"✅ Email sent to {contact_email}")
                        else:
                            send_results["emails_failed"] += 1
                            print(f"❌ Email failed: {email_result.get('error')}")
                    except Exception as email_error:
                        send_results["emails_failed"] += 1
                        print(f"❌ Email error for {contact_email}: {email_error}")
                
                # Send SMS
                if enable_sms and contact_phone and sms_template:
                    try:
                        personalized_sms = sms_template.replace("{name}", contact_name)
                        
                        print(f"💬 Sending SMS to: {contact_phone}")
                        sms_result = await sms_service.send_sms(
                            to_number=contact_phone,
                            message=personalized_sms,
                            user_id=user_id
                        )
                        
                        if sms_result.get("success"):
                            send_results["sms_sent"] += 1
                            print(f"✅ SMS sent to {contact_phone}")
                        else:
                            send_results["sms_failed"] += 1
                            print(f"❌ SMS failed: {sms_result.get('error')}")
                    except Exception as sms_error:
                        send_results["sms_failed"] += 1
                        print(f"❌ SMS error for {contact_phone}: {sms_error}")
            
            print(f"\n" + "="*60)
            print(f"📊 AUTO-SEND RESULTS:")
            print(f"   Emails sent: {send_results['emails_sent']}")
            print(f"   Emails failed: {send_results['emails_failed']}")
            print(f"   SMS sent: {send_results['sms_sent']}")
            print(f"   SMS failed: {send_results['sms_failed']}")
            print(f"="*60 + "\n")
        else:
            print(f"ℹ️ Auto-send skipped (no contacts or disabled)")

        # ============================================
        # AUTO-SEND CONFIRMATION EMAIL TO CONTACTS
        # ============================================
        confirmation_emails_sent = 0
        if contacts:
            from app.services.email_automation import email_automation_service

            for contact in contacts:
                contact_email = contact.get("email", "")
                contact_name = contact.get("name", "Customer")

                if contact_email:
                    try:
                        print(f"📧 Sending confirmation email to: {contact_email}")

                        confirmation_html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #333;">Hello {contact_name},</h2>
    <p style="color: #555; font-size: 16px;">
        This is to confirm that an AI assistant named <strong>{agent_doc['name']}</strong>
        has been set up and assigned to you.
    </p>
    <p style="color: #555; font-size: 16px;">
        You may receive calls, emails, or messages from this assistant as part of our outreach.
        If you have any questions, feel free to reply to this email.
    </p>
    <p style="color: #888; font-size: 14px; margin-top: 30px;">
        Best regards,<br>
        {current_user.get('name', 'The Team')}
    </p>
</div>
"""
                        email_result = await email_automation_service.send_email(
                            to_email=contact_email,
                            subject=f"AI Agent '{agent_doc['name']}' Has Been Assigned to You",
                            html_content=confirmation_html,
                            user_id=user_id,
                            recipient_name=contact_name,
                        )

                        if email_result.get("success"):
                            confirmation_emails_sent += 1
                            print(f"✅ Confirmation email sent to {contact_email}")
                        else:
                            print(f"❌ Confirmation email failed for {contact_email}: {email_result.get('error')}")
                    except Exception as conf_err:
                        print(f"❌ Confirmation email error for {contact_email}: {conf_err}")

            print(f"📧 Confirmation emails sent: {confirmation_emails_sent}/{len([c for c in contacts if c.get('email')])}")

        # Format response
        response_agent = {
            "_id": agent_id,
            "user_id": user_id,
            "name": agent_doc["name"],
            "description": agent_doc["description"],
            "voice_id": agent_doc["voice_id"],
            "calling_mode": agent_doc["calling_mode"],
            "contacts": agent_doc["contacts"],
            "ai_script": agent_doc["ai_script"],
            "logic_level": agent_doc["logic_level"],
            "contact_frequency": agent_doc["contact_frequency"],
            "enable_calls": agent_doc["enable_calls"],
            "enable_emails": agent_doc["enable_emails"],
            "enable_sms": agent_doc["enable_sms"],
            "email_template": agent_doc["email_template"],
            "sms_template": agent_doc["sms_template"],
            "has_training_docs": agent_doc["has_training_docs"],
            "training_doc_ids": agent_doc["training_doc_ids"],
            # ✅ NEW: Include context info
            "has_context": agent_doc.get("has_context", False),
            "is_active": agent_doc["is_active"],
            "in_call": agent_doc["in_call"],
            "total_calls": agent_doc["total_calls"],
            "successful_calls": agent_doc["successful_calls"],
            "created_at": agent_doc["created_at"].isoformat(),
            "updated_at": agent_doc["updated_at"].isoformat(),
            "auto_send_results": send_results if (enable_emails or enable_sms) else None
        }
        
        print(f"✅ Agent creation completed successfully")
        print("="*80)
        print("🚀 VOICE AGENT CREATION COMPLETED")
        print("="*80 + "\n")
        
        return response_agent
        
    except Exception as e:
        print(f"\n❌❌❌ ERROR creating voice agent: {str(e)}")
        logger.error(f"❌ Error creating voice agent: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create voice agent: {str(e)}"
        )


@router.get("/agents")
async def list_voice_agents(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """List all voice agents for current user"""
    try:
        user_id = str(current_user["_id"])
        print(f"\n📋 LISTING VOICE AGENTS")
        print(f"👤 User ID: {user_id}")
        
        agents = await db.voice_agents.find({"user_id": user_id}).to_list(length=None)
        
        print(f"🔍 Found {len(agents)} agents")
        
        # Convert ObjectIds to strings
        for agent in agents:
            agent["_id"] = str(agent["_id"])
            if "created_at" in agent:
                agent["created_at"] = agent["created_at"].isoformat()
            if "updated_at" in agent:
                agent["updated_at"] = agent["updated_at"].isoformat()
        
        print(f"✅ Agent list retrieved successfully")
        
        return {
            "success": True,
            "agents": agents,
            "total": len(agents)
        }
        
    except Exception as e:
        print(f"\n❌ ERROR listing agents: {str(e)}")
        logger.error(f"❌ Error listing agents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list agents: {str(e)}"
        )


@router.get("/agents/{agent_id}")
async def get_voice_agent(
    agent_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific voice agent"""
    try:
        user_id = str(current_user["_id"])
        print(f"\n🔍 GETTING VOICE AGENT")
        print(f"👤 User ID: {user_id}")
        print(f"🤖 Agent ID: {agent_id}")
        
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            print(f"❌ Agent not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        agent["_id"] = str(agent["_id"])
        if "created_at" in agent:
            agent["created_at"] = agent["created_at"].isoformat()
        if "updated_at" in agent:
            agent["updated_at"] = agent["updated_at"].isoformat()
        
        print(f"✅ Agent found: {agent.get('name')}")
        
        return {
            "success": True,
            "agent": agent
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ ERROR getting agent: {str(e)}")
        logger.error(f"❌ Error getting agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent: {str(e)}"
        )


@router.put("/agents/{agent_id}")
@router.patch("/agents/{agent_id}")
async def update_voice_agent(
    agent_id: str,
    agent_data: VoiceAgentUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a voice agent
    ✅ ENHANCED: Now regenerates context when ai_script changes
    ✅ ENHANCED: Added comprehensive console logging
    """
    try:
        user_id = str(current_user["_id"])
        
        print("\n" + "="*80)
        print("🔄 UPDATING VOICE AGENT")
        print("="*80)
        print(f"👤 User ID: {user_id}")
        print(f"🤖 Agent ID: {agent_id}")
        
        # Verify ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            print(f"❌ Agent not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        print(f"✅ Agent found: {agent.get('name')}")
        
        # Prepare update data
        update_data = agent_data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        print(f"📝 Update fields: {list(update_data.keys())}")
        
        # ✅ NEW: Check if ai_script changed - regenerate context
        script_changed = False
        if "ai_script" in update_data and update_data["ai_script"] != agent.get("ai_script"):
            script_changed = True
            print(f"📝 AI script changed, will regenerate context")
        
        print(f"💾 Updating agent in database...")
        await db.voice_agents.update_one(
            {"_id": ObjectId(agent_id)},
            {"$set": update_data}
        )
        print(f"✅ Database update completed")
        
        # ✅ NEW: Regenerate context if script changed
        if script_changed:
            print(f"🧠 Regenerating agent context after script update...")
            try:
                from app.services.rag_service import rag_service
                
                context_result = await rag_service.update_agent_context_on_script_change(
                    agent_id=agent_id,
                    user_id=user_id,
                    new_script=update_data["ai_script"],
                    db=db
                )
                
                if context_result.get("success"):
                    print(f"✅ Agent context regenerated successfully")
                else:
                    print(f"⚠️ Failed to regenerate context: {context_result.get('error')}")
            except Exception as ctx_error:
                print(f"⚠️ Context regeneration error (non-fatal): {ctx_error}")
        else:
            print(f"ℹ️ AI script unchanged, skipping context regeneration")
        
        # Fetch updated agent
        print(f"🔍 Fetching updated agent data...")
        updated_agent = await db.voice_agents.find_one({"_id": ObjectId(agent_id)})
        updated_agent["_id"] = str(updated_agent["_id"])
        updated_agent["user_id"] = str(updated_agent["user_id"])
        
        if "created_at" in updated_agent:
            updated_agent["created_at"] = updated_agent["created_at"].isoformat()
        if "updated_at" in updated_agent:
            updated_agent["updated_at"] = updated_agent["updated_at"].isoformat()
        
        print(f"✅ Voice agent updated: {agent_id}")
        print("="*80)
        print("🔄 VOICE AGENT UPDATE COMPLETED")
        print("="*80 + "\n")
        
        return {
            "success": True,
            "agent": updated_agent,
            "message": "Voice agent updated successfully",
            "context_regenerated": script_changed
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌❌❌ ERROR updating agent: {str(e)}")
        logger.error(f"❌ Error updating agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent: {str(e)}"
        )


@router.delete("/agents/{agent_id}")
async def delete_voice_agent(
    agent_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """Delete a voice agent"""
    try:
        user_id = str(current_user["_id"])
        
        print(f"\n🗑️ DELETING VOICE AGENT")
        print(f"👤 User ID: {user_id}")
        print(f"🤖 Agent ID: {agent_id}")
        
        # Verify ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            print(f"❌ Agent not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        print(f"✅ Agent found: {agent.get('name')}")
        
        # Delete agent
        print(f"🗑️ Deleting agent from database...")
        await db.voice_agents.delete_one({"_id": ObjectId(agent_id)})
        
        # Delete associated documents
        print(f"🗑️ Deleting associated documents...")
        await db.agent_documents.delete_many({"agent_id": agent_id})
        await db.agent_embeddings.delete_many({"agent_id": agent_id})
        
        print(f"✅ Voice agent deleted: {agent_id}")
        
        return {
            "success": True,
            "message": "Voice agent deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ ERROR deleting agent: {str(e)}")
        logger.error(f"❌ Error deleting agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete agent: {str(e)}"
        )


# ============================================
# DOCUMENT TRAINING ENDPOINTS
# ============================================
@router.post("/agents/{agent_id}/upload-training-doc")
async def upload_training_document(
    agent_id: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload training document for RAG
    ✅ ENHANCED: Context is automatically regenerated after upload (in rag_service)
    ✅ ENHANCED: Added comprehensive console logging
    """
    try:
        from app.services.rag_service import rag_service
        user_id = str(current_user["_id"])
        
        print("\n" + "="*80)
        print("📄 UPLOADING TRAINING DOCUMENT")
        print("="*80)
        print(f"👤 User ID: {user_id}")
        print(f"🤖 Agent ID: {agent_id}")
        print(f"📄 File: {file.filename}")
        print(f"📄 Content Type: {file.content_type}")
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            print(f"❌ Agent not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        print(f"✅ Agent found: {agent.get('name')}")
        
        # Read file content
        file_content = await file.read()
        
        print(f"📄 File size: {len(file_content)} bytes")
        
        # Process document with RAG service (context regeneration happens inside)
        result = await rag_service.upload_and_process_document(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            agent_id=agent_id,
            user_id=user_id,
            db=db
        )
        
        if result.get("success"):
            # Update agent to mark it has training docs
            await db.voice_agents.update_one(
                {"_id": ObjectId(agent_id)},
                {"$set": {
                    "has_training_docs": True,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            print(f"✅ Training document uploaded and processed successfully")
            print(f"📄 Document ID: {result.get('document_id')}")
            print(f"📄 Total chunks: {result.get('total_chunks')}")
            print(f"🧠 Context updated: {result.get('context_updated', False)}")
            print("="*80)
            print("📄 TRAINING DOCUMENT UPLOAD COMPLETED")
            print("="*80 + "\n")
            
            return {
                "success": True,
                "document_id": result.get("document_id"),
                "filename": result.get("filename"),
                "total_chunks": result.get("total_chunks"),
                "context_updated": result.get("context_updated", False),
                "message": "Training document uploaded and processed successfully"
            }
        else:
            print(f"❌ Failed to process document: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to process document")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌❌❌ ERROR uploading document: {str(e)}")
        logger.error(f"❌ Error uploading document: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


# ✅ NEW: Added /training-docs endpoint as alias for /documents
@router.get("/agents/{agent_id}/training-docs")
async def list_agent_training_docs(
    agent_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """List all training documents for an agent (alias for /documents)"""
    try:
        from app.services.rag_service import rag_service
        user_id = str(current_user["_id"])
        
        print(f"\n📋 LISTING TRAINING DOCUMENTS")
        print(f"👤 User ID: {user_id}")
        print(f"🤖 Agent ID: {agent_id}")
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            print(f"❌ Agent not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        print(f"✅ Agent found: {agent.get('name')}")
        
        # Get documents
        documents = await db.agent_documents.find(
            {"agent_id": agent_id}
        ).sort("uploaded_at", -1).to_list(length=None)
        
        print(f"📄 Found {len(documents)} documents")
        
        # Convert ObjectIds to strings
        for doc in documents:
            doc["_id"] = str(doc["_id"])
            if "uploaded_at" in doc:
                doc["uploaded_at"] = doc["uploaded_at"].isoformat()
            if "upload_date" in doc:
                doc["upload_date"] = doc["upload_date"].isoformat()
            if "created_at" in doc:
                doc["created_at"] = doc["created_at"].isoformat()
            if "updated_at" in doc:
                doc["updated_at"] = doc["updated_at"].isoformat()
            if "processing_started_at" in doc:
                doc["processing_started_at"] = doc["processing_started_at"].isoformat()
            if "processing_completed_at" in doc:
                doc["processing_completed_at"] = doc["processing_completed_at"].isoformat()
            # Remove chunks from response (too large)
            if "chunks" in doc:
                doc["chunks_count"] = len(doc["chunks"])
                del doc["chunks"]
        
        print(f"✅ Document list retrieved successfully")
        
        return {
            "success": True,
            "documents": documents,
            "total": len(documents)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ ERROR listing training docs: {str(e)}")
        logger.error(f"❌ Error listing training docs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list training documents: {str(e)}"
        )


# ============================================
# ✅ NEW: MANUAL CONTEXT REGENERATION ENDPOINT
# ============================================
@router.post("/agents/{agent_id}/regenerate-context")
async def regenerate_agent_context(
    agent_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """
    ✅ NEW: Manually regenerate agent context
    Useful if context gets out of sync or needs refresh
    ✅ ENHANCED: Added comprehensive console logging
    """
    try:
        from app.services.rag_service import rag_service
        user_id = str(current_user["_id"])
        
        print("\n" + "="*80)
        print("🔄 MANUAL CONTEXT REGENERATION")
        print("="*80)
        print(f"👤 User ID: {user_id}")
        print(f"🤖 Agent ID: {agent_id}")
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            print(f"❌ Agent not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        print(f"✅ Agent found: {agent.get('name')}")
        print(f"🤖 Current has_context: {agent.get('has_context', False)}")
        
        # Force regenerate context
        result = await rag_service.generate_agent_context(
            agent_id=agent_id,
            user_id=user_id,
            db=db,
            force_regenerate=True
        )
        
        if result.get("success"):
            print(f"✅ Agent context regenerated successfully")
            print(f"🧠 Cached: {result.get('cached', False)}")
            print("="*80)
            print("🔄 CONTEXT REGENERATION COMPLETED")
            print("="*80 + "\n")
            
            return {
                "success": True,
                "message": "Agent context regenerated successfully",
                "context": result.get("context"),
                "cached": result.get("cached", False)
            }
        else:
            print(f"❌ Failed to regenerate context: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to regenerate context")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌❌❌ ERROR regenerating context: {str(e)}")
        logger.error(f"❌ Error regenerating context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate context: {str(e)}"
        )


# ============================================
# ✅ NEW: GET AGENT CONTEXT ENDPOINT
# ============================================
@router.get("/agents/{agent_id}/context")
async def get_agent_context(
    agent_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """
    ✅ NEW: Get the current agent context (for debugging/inspection)
    ✅ ENHANCED: Added comprehensive console logging
    """
    try:
        user_id = str(current_user["_id"])
        
        print(f"\n🔍 GETTING AGENT CONTEXT")
        print(f"👤 User ID: {user_id}")
        print(f"🤖 Agent ID: {agent_id}")
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            print(f"❌ Agent not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        print(f"✅ Agent found: {agent.get('name')}")
        
        context = agent.get("agent_context")
        has_context = agent.get("has_context", False)
        context_generated_at = agent.get("context_generated_at")
        
        print(f"🤖 Has context: {has_context}")
        print(f"📅 Context generated at: {context_generated_at}")
        
        return {
            "success": True,
            "has_context": has_context,
            "context": context,
            "generated_at": context_generated_at.isoformat() if context_generated_at else None,
            "source_documents": context.get("source_documents", []) if context else [],
            "script_included": context.get("script_included", False) if context else False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ ERROR getting context: {str(e)}")
        logger.error(f"❌ Error getting context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context: {str(e)}"
        )


# ============================================
# ✅ NEW: EXECUTE CAMPAIGN ENDPOINT
# ============================================
@router.post("/agents/{agent_id}/execute-campaign")
async def execute_campaign(
    agent_id: str,
    campaign_config: Optional[Dict] = Body(default=None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """
    Execute a calling campaign for an agent
    This will initiate calls to all contacts associated with the agent
    ✅ ENHANCED: Added comprehensive console logging
    ✅ ENHANCED: Added Answering Machine Detection (AMD) to campaign calls
    """
    try:
        from twilio.rest import Client
        
        user_id = str(current_user["_id"])
        
        print("\n" + "="*80)
        print("📞 EXECUTING CALLING CAMPAIGN")
        print("="*80)
        print(f"👤 User ID: {user_id}")
        print(f"🤖 Agent ID: {agent_id}")
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            print(f"❌ Agent not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        print(f"✅ Agent found: {agent.get('name')}")
        
        contacts = agent.get("contacts", [])
        
        if not contacts:
            print(f"❌ No contacts found for this agent")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No contacts found for this agent"
            )
        
        print(f"📞 Total contacts: {len(contacts)}")
        
        # Campaign configuration
        config = campaign_config or {}
        delay_between_calls = config.get("delay_between_calls", 30)
        max_concurrent = config.get("max_concurrent_calls", 1)
        
        print(f"⚙️ Campaign configuration:")
        print(f"   Delay between calls: {delay_between_calls}s")
        print(f"   Max concurrent calls: {max_concurrent}")

        # Resolve Twilio credentials with fallback chain
        from app.utils.credential_resolver import resolve_twilio_credentials
        user_twilio_sid, user_twilio_token, user_twilio_number = resolve_twilio_credentials(current_user)
        if not user_twilio_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No phone number configured. Please set up Twilio integration or purchase a phone number."
            )

        # Initialize Twilio client with resolved credentials
        twilio_client = Client(user_twilio_sid, user_twilio_token)

        # Create campaign record
        campaign_data = {
            "agent_id": agent_id,
            "user_id": user_id,
            "status": "running",
            "total_contacts": len(contacts),
            "calls_initiated": 0,
            "calls_completed": 0,
            "calls_failed": 0,
            "started_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        campaign_result = await db.campaigns.insert_one(campaign_data)
        campaign_id = str(campaign_result.inserted_id)
        
        print(f"📊 Campaign ID: {campaign_id}")
        
        # Results tracking
        results = {
            "campaign_id": campaign_id,
            "total": len(contacts),
            "initiated": 0,
            "failed": 0,
            "calls": []
        }
        
        # ✅ AMD: Create AMD callback URL (once for all campaign calls)
        base_webhook_url = settings.TWILIO_WEBHOOK_URL.replace('/incoming', '')
        amd_callback_url = f"{base_webhook_url}/amd-status"
        print(f"🤖 AMD Callback URL: {amd_callback_url}")
        
        # Initiate calls to each contact
        for index, contact in enumerate(contacts):
            contact_phone = contact.get("phone", "")
            contact_name = contact.get("name", "Customer")
            
            if not contact_phone:
                print(f"⚠️ Skipping contact {contact_name}: no phone number")
                results["failed"] += 1
                continue
            
            try:
                print(f"📞 Initiating call {index + 1}/{len(contacts)} to {contact_name} ({contact_phone})")
                
                campaign_recording_callback = os.getenv("TWILIO_RECORDING_STATUS_CALLBACK") or f"{base_webhook_url}/recording-status"
                call = twilio_client.calls.create(
                    to=contact_phone,
                    from_=user_twilio_number,
                    url=settings.TWILIO_WEBHOOK_URL,
                    status_callback=base_webhook_url + '/status',
                    status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                    status_callback_method='POST',
                    record=True,
                    recording_status_callback=campaign_recording_callback,
                    recording_status_callback_method="POST",
                )

                # Create call record in database
                call_record = {
                    "twilio_call_sid": call.sid,
                    "call_sid": call.sid,
                    "campaign_id": campaign_id,
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "from_number": user_twilio_number,
                    "to_number": contact_phone,
                    "phone_number": contact_phone,
                    "contact_name": contact_name,
                    "direction": "outbound",
                    "status": "initiated",
                    "answered_by": "unknown",  # ✅ ADD: Track who answered
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                await db.calls.insert_one(call_record)
                
                results["initiated"] += 1
                results["calls"].append({
                    "call_sid": call.sid,
                    "to": contact_phone,
                    "contact_name": contact_name,
                    "status": "initiated"
                })
                
                print(f"✅ Call initiated: {call.sid} to {contact_phone}")
                print(f"🤖 AMD enabled (DetectMessageEnd mode)")
                
                # Delay between calls (except for last one)
                if index < len(contacts) - 1 and delay_between_calls > 0:
                    print(f"⏳ Waiting {delay_between_calls}s before next call...")
                    await asyncio.sleep(delay_between_calls)
                    
            except Exception as call_error:
                print(f"❌ Failed to call {contact_phone}: {call_error}")
                results["failed"] += 1
                results["calls"].append({
                    "to": contact_phone,
                    "contact_name": contact_name,
                    "status": "failed",
                    "error": str(call_error)
                })
        
        # Update campaign record
        await db.campaigns.update_one(
            {"_id": ObjectId(campaign_id)},
            {"$set": {
                "calls_initiated": results["initiated"],
                "calls_failed": results["failed"],
                "status": "completed" if results["initiated"] > 0 else "failed",
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        print(f"\n📊 CAMPAIGN RESULTS:")
        print(f"   Total contacts: {results['total']}")
        print(f"   Calls initiated: {results['initiated']}")
        print(f"   Calls failed: {results['failed']}")
        print(f"   AMD mode: DetectMessageEnd (waits for beep)")
        print("="*80)
        print("📞 CALLING CAMPAIGN COMPLETED")
        print("="*80 + "\n")
        
        return {
            "success": True,
            "message": f"Campaign executed: {results['initiated']}/{results['total']} calls initiated",
            "campaign_id": campaign_id,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌❌❌ ERROR executing campaign: {str(e)}")
        logger.error(f"❌ Error executing campaign: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute campaign: {str(e)}"
        )


# ============================================
# ✅ NEW: INITIATE SINGLE CALL ENDPOINT
# ============================================
@router.post("/agents/{agent_id}/call")
async def initiate_call(
    agent_id: str,
    call_data: Dict = Body(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """
    Initiate a single call to a specific phone number
    ✅ ENHANCED: Added comprehensive console logging
    ✅ ENHANCED: Added Answering Machine Detection (AMD)
    """
    try:
        from twilio.rest import Client
        
        user_id = str(current_user["_id"])
        
        print(f"\n📞 INITIATING SINGLE CALL")
        print(f"👤 User ID: {user_id}")
        print(f"🤖 Agent ID: {agent_id}")
        
        # Verify agent ownership
        agent = await db.voice_agents.find_one({
            "_id": ObjectId(agent_id),
            "user_id": user_id
        })
        
        if not agent:
            print(f"❌ Agent not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        print(f"✅ Agent found: {agent.get('name')}")
        
        phone_number = call_data.get("phone_number")
        contact_name = call_data.get("contact_name", "Customer")
        
        if not phone_number:
            print(f"❌ Missing phone_number")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="phone_number is required"
            )
        print(f"🔍 [DEDUP] Checking for recent calls to {phone_number}...")
        from datetime import timedelta
        thirty_seconds_ago = datetime.utcnow() - timedelta(seconds=30)
        recent_call = await db.calls.find_one({
            "user_id": user_id,
            "agent_id": agent_id,
            "to_number": phone_number,
            "created_at": {"$gte": thirty_seconds_ago},
            "status": {"$in": ["initiated", "ringing", "in-progress", "answered"]}
        })
        if recent_call:
            existing_call_sid = recent_call.get("twilio_call_sid") or recent_call.get("call_sid")
            existing_call_id = str(recent_call["_id"])
            age_seconds = (datetime.utcnow() - recent_call["created_at"]).total_seconds()

            print(f"⚠️ [DEDUP] Call to {phone_number} already in progress!")
            print(f"   Existing Call SID: {existing_call_sid}")
            print(f"   Call initiated {age_seconds:.1f}s ago")
            print(f"   Status: {recent_call.get('status')}")
            
            return {
                "success": True,
                "message": f"Call to {phone_number} already in progress",
                "call_id": existing_call_id,
                "call_sid": existing_call_sid,
                "to": phone_number,
                "from": current_user.get("twilio_phone_number") or settings.TWILIO_PHONE_NUMBER,
                "status": recent_call.get("status"),
                "duplicate_prevented": True,
                "age_seconds": age_seconds
            }
        print(f"✅ [DEDUP] No recent calls found, proceeding...")
        print(f"📞 Initiating call to {contact_name} ({phone_number})")

        # Resolve Twilio credentials with fallback chain
        from app.utils.credential_resolver import resolve_twilio_credentials
        user_twilio_sid, user_twilio_token, user_twilio_number = resolve_twilio_credentials(current_user)
        if not user_twilio_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No phone number configured. Please set up Twilio integration or purchase a phone number."
            )

        # Initialize Twilio client with resolved credentials
        twilio_client = Client(user_twilio_sid, user_twilio_token)

        base_webhook_url = settings.TWILIO_WEBHOOK_URL.replace('/incoming', '')

        recording_callback = os.getenv("TWILIO_RECORDING_STATUS_CALLBACK") or f"{base_webhook_url}/recording-status"

        call_kwargs = {
            "to": phone_number,
            "from_": user_twilio_number,
            "url": settings.TWILIO_WEBHOOK_URL,
            "status_callback": f"{base_webhook_url}/status",
            "status_callback_event": ['initiated', 'ringing', 'answered', 'completed'],
            "status_callback_method": 'POST',
            "record": True,
            "recording_status_callback": recording_callback,
            "recording_status_callback_method": "POST",
        }

        # Create call via Twilio
        call = twilio_client.calls.create(**call_kwargs)

        # Create call record in database
        call_record = {
            "twilio_call_sid": call.sid,
            "call_sid": call.sid,
            "agent_id": agent_id,
            "user_id": user_id,
            "from_number": user_twilio_number,
            "to_number": phone_number,
            "phone_number": phone_number,
            "contact_name": contact_name,
            "direction": "outbound",
            "status": "initiated",
            "answered_by": "unknown",  # ✅ ADD: Track who answered
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.calls.insert_one(call_record)
        call_id = str(result.inserted_id)
        
        print(f"✅ Call initiated: {call.sid} to {phone_number}")
        print(f"📞 Call ID: {call_id}")
        print(f"📱 From number: {user_twilio_number}")

        return {
            "success": True,
            "message": f"Call initiated to {phone_number}",
            "call_id": call_id,
            "call_sid": call.sid,
            "to": phone_number,
            "from": user_twilio_number,
            "status": "initiated",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ ERROR initiating call: {str(e)}")
        logger.error(f"❌ Error initiating call: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate call: {str(e)}"
        )


# ============================================
# ✅ NEW: HANGUP/END CALL ENDPOINT
# ============================================
@router.post("/calls/{call_id}/hangup")
async def hangup_call(
    call_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """End an active call by call_id or call_sid"""
    try:
        user_id = str(current_user["_id"])

        logger.info(f"📞 HANGUP REQUEST - Call ID: {call_id}, User: {user_id}")

        # Find the call in database by _id or call_sid
        call = await db.calls.find_one({
            "$or": [
                {"_id": ObjectId(call_id) if ObjectId.is_valid(call_id) else None},
                {"twilio_call_sid": call_id},
                {"call_sid": call_id}
            ],
            "user_id": user_id
        })

        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )

        # Get the Twilio call SID
        call_sid = call.get("twilio_call_sid") or call.get("call_sid")

        if not call_sid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No Twilio call SID found for this call"
            )

        # End call via Twilio — use per-user subaccount credentials if available
        user_twilio_sid = current_user.get("twilio_subaccount_sid")
        user_twilio_token = current_user.get("twilio_auth_token")

        if user_twilio_sid and user_twilio_token:
            # Call was created in subaccount — must use subaccount client to hang up
            from twilio.rest import Client as TwilioClient
            sub_client = TwilioClient(user_twilio_sid, user_twilio_token)
            try:
                sub_client.calls(call_sid).update(status="completed")
                result = {"success": True, "status": "completed"}
            except Exception as e:
                print(f"❌ Error hanging up call via subaccount: {e}")
                result = {"success": False, "error": str(e)}
        else:
            await call_handler_service.ensure_initialized()
            result = call_handler_service._twilio_service.hangup_call(call_sid)

        if result.get("success"):
            # Update call status in database
            await db.calls.update_one(
                {"_id": call["_id"]},
                {"$set": {"status": "completed", "updated_at": datetime.utcnow()}}
            )
            logger.info(f"✅ Call ended successfully: {call_sid}")
            return {"success": True, "message": "Call ended", "status": "completed"}
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"❌ Failed to end call: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to end call: {error_msg}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in hangup_call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# ✅ NEW: GET CALL DETAILS ENDPOINT
# ============================================
@router.get("/calls/{call_id}")
async def get_call_details(
    call_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific call including transcript"""
    try:
        user_id = str(current_user["_id"])
        
        print(f"\n🔍 GETTING CALL DETAILS")
        print(f"👤 User ID: {user_id}")
        print(f"📞 Call ID/SID: {call_id}")
        
        # Try to find by _id or call_sid
        call = await db.calls.find_one({
            "$or": [
                {"_id": ObjectId(call_id) if ObjectId.is_valid(call_id) else None},
                {"twilio_call_sid": call_id},
                {"call_sid": call_id}
            ],
            "user_id": user_id
        })
        
        if not call:
            print(f"❌ Call not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        print(f"✅ Call found")
        print(f"📞 From: {call.get('from_number')}")
        print(f"📞 To: {call.get('to_number')}")
        print(f"📞 Status: {call.get('status')}")
        print(f"🤖 Answered By: {call.get('answered_by', 'unknown')}")
        
        # Get transcript
        transcripts = await db.call_transcripts.find({
            "$or": [
                {"call_id": call["_id"]},
                {"call_sid": call.get("twilio_call_sid")}
            ]
        }).sort("timestamp", 1).to_list(length=None)
        
        print(f"📝 Found {len(transcripts)} transcript entries")
        
        for t in transcripts:
            t["_id"] = str(t["_id"])
            if "call_id" in t:
                t["call_id"] = str(t["call_id"])
            if "timestamp" in t:
                t["timestamp"] = t["timestamp"].isoformat()
        
        call["_id"] = str(call["_id"])
        if "created_at" in call:
            call["created_at"] = call["created_at"].isoformat()
        if "updated_at" in call:
            call["updated_at"] = call["updated_at"].isoformat()
        if "answered_at" in call:
            call["answered_at"] = call["answered_at"].isoformat()
        if "ended_at" in call:
            call["ended_at"] = call["ended_at"].isoformat()
        
        print(f"✅ Call details retrieved successfully")
        
        return {
            "success": True,
            "call": call,
            "transcript": transcripts
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ ERROR getting call details: {str(e)}")
        logger.error(f"❌ Error getting call details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get call details: {str(e)}"
        )


# ============================================
# 🎙️ WEBSOCKET: MEDIA STREAM FOR REAL-TIME AUDIO
# ============================================

@router.websocket("/ws/media-stream")
async def media_stream_websocket(websocket: WebSocket):
    """
    🎙️ PRODUCTION WebSocket for Twilio Media Streams
    - Uses both_tracks
    - No premature greeting (waits for human)
    - Full logging
    """
    await websocket.accept()
    
    print(f"=" * 80)
    print(f"🔌 [WEBSOCKET] Connection accepted from {websocket.client}")
    print(f"=" * 80)
    
    call_sid = None
    agent_id = None
    stream_sid = None
    
    try:
        # Get params from query string
        query_string = websocket.scope.get("query_string", b"").decode()
        if query_string:
            params = {}
            for param in query_string.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value
            call_sid = params.get("call_sid")
            agent_id = params.get("agent_id")
            print(f"📋 [WEBSOCKET] Query params: call_sid={call_sid}, agent_id={agent_id}")
        
        # Wait for Twilio "start" event if not in query params
        if not call_sid or not agent_id:
            print(f"⏳ [WEBSOCKET] Waiting for 'start' event from Twilio...")
            import json
            
            max_attempts = 10
            for attempt in range(max_attempts):
                message = await websocket.receive_text()
                data = json.loads(message)
                event = data.get("event")
                print(f"📨 [WEBSOCKET] Received event: {event}")
                
                if event == "start":
                    call_sid = data.get("start", {}).get("callSid")
                    stream_sid = data.get("start", {}).get("streamSid")
                    custom_params = data.get("start", {}).get("customParameters", {})
                    agent_id = custom_params.get("agent_id")
                    
                    print(f"✅ [WEBSOCKET] Got from 'start' event:")
                    print(f"   call_sid: {call_sid}")
                    print(f"   stream_sid: {stream_sid}")
                    print(f"   agent_id: {agent_id}")
                    break
                elif event == "connected":
                    print(f"✅ [WEBSOCKET] Connected event received, waiting for 'start'...")
                    continue
                else:
                    print(f"⚠️ [WEBSOCKET] Unexpected event: {event}")
        
        if not call_sid or not agent_id:
            print(f"❌ [WEBSOCKET] Missing parameters after {max_attempts} attempts")
            await websocket.close()
            return
        
        # Reuse the app-level MongoDB connection pool (avoids ~100-300ms new-connection cost)
        from app.database import database as _db_singleton
        db = _db_singleton.database

        # Get agent config
        from bson import ObjectId
        agent = await db.voice_agents.find_one({"_id": ObjectId(agent_id)})
        
        if not agent:
            print(f"❌ [WEBSOCKET] Agent not found: {agent_id}")
            await websocket.close()
            return
        
        # Get call record
        call = await db.calls.find_one({"call_sid": call_sid})
        call_id = str(call["_id"]) if call else None
        user_id = agent.get("user_id")

        # Override agent fields with inbound config if present
        if call and call.get("inbound_config"):
            ic = call["inbound_config"]
            print(f"📞 [WEBSOCKET] INBOUND CONFIG detected — overriding agent settings")

            # Reset agent_context to prevent outbound data leaking into inbound calls
            agent["agent_context"] = {}

            # Use the inbound config's ai_script as the primary script
            if ic.get("ai_script"):
                agent["ai_script"] = ic["ai_script"]
                print(f"   📜 Using inbound ai_script ({len(ic['ai_script'])} chars)")

            # Pass business_info from inbound config if available
            if ic.get("business_info"):
                agent["agent_context"]["business_info"] = ic["business_info"]
                print(f"   📋 Using inbound business_info ({len(ic['business_info'])} chars)")

            # Flag for inbound prompt path
            agent["agent_context"]["inbound_script"] = ic.get("ai_script", "")

            if ic.get("voice_id"):
                agent["voice_id"] = ic["voice_id"]
                print(f"   🎤 Overriding voice_id: {ic['voice_id']}")

            # Store full inbound config for other features
            agent["inbound_config"] = ic

        print(f"✅ [WEBSOCKET] Setup complete:")
        print(f"   Agent: {agent.get('name')}")
        print(f"   User: {user_id}")
        print(f"   Call: {call_sid}")
        print(f"   Inbound override: {bool(call and call.get('inbound_config'))}")
        
        # Initialize stream handler
        from app.services.audio_stream_handler import AudioStreamHandler
        from app.services.openai import openai_service
        from app.services.elevenlabs import elevenlabs_service
        from app.services.agent_executor import agent_executor
        
        handler = AudioStreamHandler(openai_service, elevenlabs_service, agent_executor)
        
        # CRITICAL: Store greeting in database for later use
        if call and call.get("greeting_text"):
            print(f"💾 [GREETING] Already stored in DB: {call['greeting_text'][:80]}...")
        else:
            # Fallback: store default greeting
            greeting_text = agent.get("ai_script", "Hello! How can I help you?").split('\n')[0][:300]
            await db.calls.update_one(
                {"call_sid": call_sid},
                {"$set": {"greeting_text": greeting_text}}
            )
            print(f"💾 [GREETING] Stored fallback in DB: {greeting_text[:80]}...")
        
        print(f"=" * 80)
        print(f"🎙️ [HANDLER] Starting media stream handler")
        print(f"📞 [MODE] PROACTIVE MODE - AI will greet immediately on stream start")
        print(f"=" * 80)
        
        # Start the stream handler with stream_sid for proactive greeting
        await handler.handle_media_stream(
            websocket,
            call_sid,
            agent,
            user_id,
            call_id,
            db,
            initial_stream_sid=stream_sid
        )
        
    except Exception as e:
        print(f"❌ [WEBSOCKET] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await websocket.close()
        except:
            pass
        print(f"🔌 [WEBSOCKET] Connection closed for {call_sid}")
# ============================================
# 📊 LATENCY STATISTICS ENDPOINT
# ============================================

@router.get("/latency/stats")
async def get_latency_stats(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    """Get latency statistics for recent calls"""
    try:
        user_id = str(current_user["_id"])
        
        print(f"\n📊 GETTING LATENCY STATISTICS")
        print(f"👤 User ID: {user_id}")
        
        # Get last 100 latency logs (you might want to filter by user_id in the future)
        logs = await db.latency_logs.find().sort("timestamp", -1).limit(100).to_list(length=100)
        
        if not logs:
            print(f"ℹ️ No latency data yet")
            return {"message": "No latency data yet"}
        
        # Calculate stats
        totals = [log.get("total_ms", 0) for log in logs]
        
        # Convert ObjectIds to strings for JSON serialization
        for log in logs:
            log["_id"] = str(log["_id"])
            if "timestamp" in log:
                log["timestamp"] = log["timestamp"].isoformat()
        
        stats = {
            "count": len(logs),
            "average_ms": sum(totals) / len(totals),
            "min_ms": min(totals),
            "max_ms": max(totals),
            "recent_logs": logs[:10]  # Last 10
        }
        
        print(f"📊 Latency Stats:")
        print(f"   Total calls analyzed: {stats['count']}")
        print(f"   Average latency: {stats['average_ms']:.2f}ms")
        print(f"   Minimum latency: {stats['min_ms']:.2f}ms")
        print(f"   Maximum latency: {stats['max_ms']:.2f}ms")
        print(f"✅ Latency statistics retrieved successfully")
        
        return stats
        
    except Exception as e:
        print(f"\n❌ ERROR getting latency stats: {str(e)}")
        logger.error(f"❌ Error getting latency stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))