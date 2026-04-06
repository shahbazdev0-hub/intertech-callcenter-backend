
# backend/app/services/agent_executor.py appointment booking flow testing 
"""
Agent Response Executor - ✅ MAJOR REWRITE FOR FAST CONTEXTUAL RESPONSES

✅ NEW APPROACH: Dynamic Summary Context System
- Pre-generated context injected into every call
- No more 5-step sequential checking
- Response time: 1-2 seconds instead of 4-7 seconds

✅ SALES FOCUS: Always bring conversation back to company services
- End responses with engagement questions
- Subtle marketing in every response
- Always try to convert/close the customer

✅ PRESERVED FUNCTIONALITY:
- Appointment booking flow (full conversation state)
- Follow-up/callback detection
- Email/phone extraction helpers
- Google Calendar integration
- Confirmation emails

✅ NEW PRIORITY SYSTEM:
1. Check if appointment booking in progress → Continue booking flow
2. Check if user wants to book appointment → Start booking flow
3. Use pre-built context + OpenAI → Fast contextual response with SALES FOCUS
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from .rag_service import rag_service
from .openai import openai_service
from .call_memory import call_memory_service  # ✅ NEW IMPORT
from .appointment import appointment_service
from .google_calendar import google_calendar_service
from .email import email_service
from .time_parser import time_parser_service
from .card_validator import validate_card_number, validate_expiry, validate_cvc, lookup_bin
from app.config import settings

logger = logging.getLogger(__name__)


# ============================================
# ✅ NEW: VALIDATION LAYER FOR APPOINTMENT BOOKING
# ============================================

def validate_booking_data(collected_data: dict) -> tuple:
    """
    Validate booking data before creating appointment
    Returns: (is_valid: bool, errors: list, cleaned_data: dict)
    """
    errors = []
    cleaned_data = collected_data.copy()
    
    # Validate name (should be 2+ characters)
    if collected_data.get("name"):
        name = collected_data["name"].strip()
        if len(name) < 2:
            errors.append(f"Name too short: {name}")
            cleaned_data["name"] = None
    else:
        errors.append("Name is required")
    
    # Validate email
    if collected_data.get("email"):
        email = collected_data["email"].strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append(f"Invalid email format: {email}")
            cleaned_data["email"] = None
        else:
            cleaned_data["email"] = email
    else:
        errors.append("Email is required")
    
    # Validate phone
    if collected_data.get("phone"):
        phone = re.sub(r'\D', '', collected_data["phone"])
        if len(phone) < 10:
            errors.append(f"Invalid phone (need 10+ digits): {collected_data['phone']}")
            cleaned_data["phone"] = None
        else:
            # Format phone with country code
            if len(phone) == 10:
                cleaned_data["phone"] = f"+1{phone}"
            elif len(phone) == 11 and phone.startswith('1'):
                cleaned_data["phone"] = f"+{phone}"
            else:
                cleaned_data["phone"] = f"+{phone[:11]}"
    else:
        errors.append("Phone is required")
    
    # Validate date
    if collected_data.get("date"):
        if not isinstance(collected_data["date"], datetime):
            errors.append(f"Invalid date format: {collected_data['date']}")
            cleaned_data["date"] = None
    else:
        errors.append("Date is required")
    
    # Validate time
    if collected_data.get("time"):
        try:
            # Try to parse the time to validate format
            datetime.strptime(collected_data["time"], "%I:%M %p")
        except ValueError:
            errors.append(f"Invalid time format: {collected_data['time']}")
            cleaned_data["time"] = None
    else:
        errors.append("Time is required")
    
    # Check if we have all required fields
    has_name = cleaned_data.get("name") is not None
    has_email = cleaned_data.get("email") is not None
    has_phone = cleaned_data.get("phone") is not None
    has_date = cleaned_data.get("date") is not None
    has_time = cleaned_data.get("time") is not None
    
    is_valid = has_name and has_email and has_phone and has_date and has_time
    
    return is_valid, errors, cleaned_data


class AgentExecutor:
    """
    Agent Response Executor - ✅ FAST CONTEXTUAL RESPONSE SYSTEM WITH SALES FOCUS
    
    NEW APPROACH:
    - Uses pre-generated agent context (summary) for instant responses
    - No real-time RAG search during calls
    - Appointment booking preserved with full conversation state
    - ✅ SALES FOCUS: Always brings conversation back to company services
    
    RESPONSE TIME: 1-2 seconds (down from 4-7 seconds)
    """
    
    def __init__(self):
        self.rag = rag_service
        self.openai = openai_service
        self.appointment_service = appointment_service
        self.calendar_service = google_calendar_service
        self.email_service = email_service
        
        # Appointment booking keywords
        self.appointment_keywords = [
            "appointment", "schedule", "booking", "book", "meeting",
            "reservation", "slot", "available", "time", "date",
            "calendar", "schedule me", "set up", "arrange"
        ]
        
        # Conversation state tracking for appointments
        self.active_bookings = {}  # {call_id: booking_state}

        # ✅ Payment collection state
        self.active_payments = {}  # {call_id: payment_state}
        self.PAYMENT_INTENT_PHRASES = [
            # ── Direct purchase / payment intent ────────────────────────────
            "i want to buy", "i'll buy", "i want to purchase", "i'll purchase",
            "sign me up", "i'll take it", "i want the plan", "i'll take the plan",
            "i'm interested in buying", "i want to sign up",
            "i'd like to buy", "i'd like to purchase", "i want to get the plan",
            "yes i'll buy", "yes sign me up", "i'll go with", "i want to pay",
            "take my payment", "i want to order",
            "ready to buy", "ready to pay", "process my payment", "take payment",
            "i'll take the package", "i want the package",
            "i want to get started", "let's get started",
            # ── Service / slot booking with purchase intent ──────────────────
            "book my service", "book the service", "book this service",
            "book my slot", "book a slot", "book the slot",
            "book me in", "book me for the service",
            "i want to book the service", "i'd like to book the service",
            "please book my service", "please book my slot", "please book the service",
            "schedule my service", "schedule the service",
            "i want to take the service", "i'll take the service",
            "i want to get the service", "i'd like to get the service",
            # ── Affirmative confirmations of purchase (used after AI pitches) ─
            "yes i want to proceed", "yes please proceed",
            "go ahead and book", "yes let's proceed", "i want to go ahead",
            "yes i'll take it", "yes book me", "i'll go ahead",
            "let's do this", "yes that's fine let's proceed",
            "i want it", "i'll take that", "i want to confirm",
            "yes i want to buy", "yes i want the service",
            "i want to confirm my order", "confirm my booking",
        ]

        logger.info("✅ AgentExecutor initialized with FAST CONTEXTUAL RESPONSE + SALES FOCUS system")
    
    
    # ============================================
    # ✅ NEW: MAIN PROCESSING METHOD - FAST RESPONSE
    # ============================================
    
    async def process_user_message(
        self,
        user_input: str,
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db: AsyncIOMotorDatabase,
        call_sid: str = None  # ✅ NEW PARAMETER
    ) -> str:
        """
        ✅ NEW: Fast contextual response system with SALES FOCUS
        
        PRIORITY ORDER:
        1. Active appointment booking → Continue booking flow
        2. New appointment request → Start booking flow  
        3. Follow-up/callback request → Schedule callback
        4. General question → Use pre-built context + OpenAI (FAST!) + SALES REDIRECT
        
        Response time target: 1-2 seconds
        """
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"⚡ FAST CONTEXTUAL RESPONSE SYSTEM (SALES FOCUS)")
            logger.info(f"{'='*80}")
            logger.info(f"🔍 User input: '{user_input}'")
            logger.info(f"🤖 Agent: {agent_config.get('name')}")
            logger.info(f"📞 Call ID: {call_id}")
            logger.info(f"{'='*80}\n")
            
            user_input_lower = user_input.lower().strip()

            # ============================================
            # ✅ SMART INTENT DETECTION
            # ============================================

            # Check if user is asking a QUESTION (not ready to book)
            is_question = "?" in user_input or any(q in user_input_lower for q in [
                "what", "how", "why", "when", "where", "which", "do you", 
                "is there", "are there", "tell me", "explain", "discount", "price", 
                "cost", "offer", "provide", "service", "about"
            ])

            # Check if user wants to CANCEL/STOP
            wants_cancel = any(word in user_input_lower for word in [
                "cancel", "don't want", "no thanks", "not interested", "stop", 
                "forget", "never mind", "no appointment", "busy"
            ])

            # ✅ FIXED: Check if user wants a CALLBACK - MORE SPECIFIC PATTERNS
            callback_patterns = [
                "call me back", "call back", "callback", "call me later", "call tomorrow",
                "call next", "ring me", "phone me", "call me in", "can you call me",
                "could you call me", "please call me", "call me after", "call me again"
            ]
            wants_callback = any(phrase in user_input_lower for phrase in callback_patterns)

            # ✅ Also detect callback by time patterns like "call me 3 minutes" or "in 2 hours"
            has_callback_time_pattern = bool(re.search(r'call.*\d+\s*(?:minute|min|hour|hr)', user_input_lower))
            if has_callback_time_pattern:
                wants_callback = True
                logger.info(f"📞 Detected callback with time pattern: '{user_input}'")

            # ============================================
            # ✅ PRIORITY -1: Handle HANGUP / BUSY — end gracefully, NEVER re-pitch
            # ============================================
            hangup_phrases = [
                "hang up", "hangup", "end the call", "end call", "stop the call",
                "please hang up", "please end", "cut the call", "disconnect",
                "don't call me", "do not call me", "stop calling", "remove me",
                "do not disturb", "not interested", "goodbye", "good bye",
                "bye bye", "i have to go", "i need to go", "i got to go", "i gotta go",
            ]
            wants_to_end = any(phrase in user_input_lower for phrase in hangup_phrases)
            if wants_to_end:
                logger.info("📞 [HANGUP-INTENT] Customer wants to end call — returning goodbye")
                if call_id in self.active_bookings:
                    del self.active_bookings[call_id]
                if call_id in self.active_payments:
                    del self.active_payments[call_id]
                return "It was nice speaking with you, have a great day!"

            # ============================================
            # ✅ PRIORITY 0: Handle CANCEL first
            # ============================================
            if wants_cancel:
                logger.info("🚫 User wants to cancel/stop")
                if call_id in self.active_bookings:
                    del self.active_bookings[call_id]
                if call_id in self.active_payments:
                    del self.active_payments[call_id]

                if wants_callback:
                    return "No problem! When would be a good time to call you back?"
                else:
                    return "No problem at all! Is there anything else I can help you with today?"

            # ============================================
            # ✅ PRIORITY 0.5: Handle CALLBACK request BEFORE questions
            # ============================================
            if wants_callback:
                logger.info("📞 PRIORITY 0.5: User wants a callback")
                try:
                    follow_up_response = await self._handle_follow_up_request(
                        user_input=user_input,
                        agent_config=agent_config,
                        user_id=user_id,
                        call_id=call_id,
                        db=db
                    )
                    if follow_up_response:
                        logger.info(f"✅ Follow-up scheduled: {follow_up_response[:100]}...")
                        return follow_up_response
                    else:
                        logger.warning("⚠️ Follow-up handler returned None, asking for time")
                        return "Sure! When would be a good time to call you back?"
                except Exception as e:
                    logger.error(f"❌ Follow-up error: {e}")
                    import traceback
                    traceback.print_exc()
                    return "Sure! When would be a good time to call you back?"

            # ============================================
            # ✅ CHECK: Does the question also contain booking intent?
            # If so, skip question handler and let booking logic handle it
            # ============================================
            explicit_booking_phrases = [
                "book an appointment", "schedule an appointment", "make an appointment",
                "i want to book", "i'd like to book", "can i book", "book a meeting",
                "schedule a call", "set up a meeting", "i want to schedule",
                "booking my appointment", "book appointment", "make appointment",
                "schedule appointment", "book me", "can you book"
            ]
            wants_to_book = any(phrase in user_input_lower for phrase in explicit_booking_phrases)

            # ============================================
            # ✅ PRIORITY 0.7: Answer QUESTIONS (but NOT if in active booking or wants to book)
            # ============================================
            if is_question and not (call_id in self.active_bookings) and not wants_to_book and not (call_id in self.active_payments):
                logger.info("❓ User asking a question - answering first like a salesman")
                # Let OpenAI answer the question naturally, don't force booking
                response = await self._generate_contextual_response(
                    user_input=user_input,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db,
                    call_sid=call_sid  # ✅ PASS CALL_SID
                )
                return response

            # ============================================
            # PRIORITY 1: ACTIVE APPOINTMENT BOOKING
            # ============================================
            if call_id in self.active_bookings:
                logger.info("📅 PRIORITY 1: Active appointment booking in progress...")
                
                # ✅ Check if user is asking a question instead of providing data
                question_words = ["what", "how", "why", "which", "can you", "do you", 
                                 "tell me", "explain", "before", "first", "?"]
                is_question = any(q in user_input_lower for q in question_words)
                
                if is_question:
                    logger.info("❓ User asking question during booking - answering first")
                    # Answer the question using OpenAI, but keep booking state
                    response = await self._generate_contextual_response(
                        user_input=user_input,
                        agent_config=agent_config,
                        user_id=user_id,
                        call_id=call_id,
                        db=db,
                        call_sid=call_sid  # ✅ PASS CALL_SID
                    )
                    # Add a gentle nudge back to booking
                    booking_state = self.active_bookings[call_id]
                    current_step = booking_state.get("step", "name")
                    
                    if current_step == "email":
                        response += " Now, what's your email address?"
                    elif current_step == "phone":
                        response += " So, what's your phone number?"
                    elif current_step == "date":
                        response += " What date works best for you?"
                    elif current_step == "time":
                        response += " And what time would you prefer?"
                    
                    return response
                
                # Continue with normal booking flow
                logger.info("📅 Continuing active appointment booking...")
                
                booking_response = await self._handle_appointment_booking(
                    user_input=user_input,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db
                )
                
                if booking_response:
                    logger.info(f"✅ Appointment booking response: {booking_response[:100]}...")
                    return booking_response
            
            # ============================================
            # ✅ PRIORITY 1.5: PAYMENT COLLECTION
            # ============================================
            has_active_payment = call_id in self.active_payments
            wants_to_pay = any(phrase in user_input_lower for phrase in self.PAYMENT_INTENT_PHRASES)

            if has_active_payment or wants_to_pay:
                logger.info(f"💳 PRIORITY 1.5: {'Continuing' if has_active_payment else 'Starting'} payment collection...")
                payment_response = await self._handle_payment_collection(
                    user_input=user_input,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db,
                    call_sid=call_sid
                )
                if payment_response:
                    logger.info(f"💳 Payment collection response: {payment_response[:100]}...")
                    return payment_response

            # ============================================
            # PRIORITY 2: NEW APPOINTMENT REQUEST
            # ============================================
            has_appointment_keyword = any(kw in user_input_lower for kw in self.appointment_keywords)

            # ✅ Also detect if user is providing appointment details
            has_time_reference = any(word in user_input_lower for word in [
                "tomorrow", "today", "monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday", "next week", "pm", "am", "o'clock"
            ])
            has_appointment_context = has_appointment_keyword and has_time_reference

            # ✅ FIXED: Remove `not is_question` — booking intent should always take priority
            # wants_to_book is already computed above PRIORITY 0.7
            if wants_to_book or has_appointment_context:
                logger.info("📅 PRIORITY 2: User wants to book appointment...")
                
                booking_response = await self._handle_appointment_booking(
                    user_input=user_input,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db
                )
                
                if booking_response:
                    logger.info(f"✅ Started/continued appointment booking: {booking_response[:100]}...")
                    return booking_response
            
            # ============================================
            # PRIORITY 3: FOLLOW-UP/CALLBACK REQUEST
            # ============================================
            try:
                follow_up_detected = await time_parser_service.detect_follow_up_intent(user_input)
                
                if follow_up_detected:
                    logger.info("📞 PRIORITY 3: Follow-up request detected...")
                    
                    follow_up_response = await self._handle_follow_up_request(
                        user_input=user_input,
                        agent_config=agent_config,
                        user_id=user_id,
                        call_id=call_id,
                        db=db
                    )
                    
                    if follow_up_response:
                        logger.info(f"✅ Follow-up scheduled: {follow_up_response[:100]}...")
                        return follow_up_response
            except Exception as follow_up_error:
                logger.warning(f"⚠️ Follow-up detection error (continuing): {follow_up_error}")
            
            # ============================================
            # PRIORITY 3.5: MID-CALL RECONNECT ("hello", "are you there?")
            # ============================================
            # When the user says a reconnect phrase mid-call, do NOT re-pitch.
            # Just acknowledge and resume from the last question/topic.
            _reconnect_phrases = [
                "hello", "hey", "hi", "are you there", "can you hear me",
                "hello?", "hey?", "you there", "still there", "anyone there",
                "hello hello", "hellooo", "is anyone there", "hello are you there",
            ]
            is_reconnect = user_input_lower.strip().rstrip("?!.") in _reconnect_phrases or \
                           user_input_lower.strip() in _reconnect_phrases

            if is_reconnect:
                memory_key = call_sid or call_id
                memory = await call_memory_service.get_memory(memory_key, db)
                if memory.get("turn_count", 0) > 0:
                    logger.info("📞 PRIORITY 3.5: Mid-call reconnect — resuming conversation")
                    # Resume from the last assistant question/topic
                    history = memory.get("history", [])
                    last_agent_msg = next(
                        (m["content"] for m in reversed(history) if m.get("role") == "assistant"),
                        None
                    )
                    if last_agent_msg:
                        # Trim to the first sentence so we don't repeat a long message
                        first_sentence = last_agent_msg.split(".")[0].strip()
                        return f"Yes, I'm still here! {first_sentence}?"
                    return "Yes, I'm still here! Could you repeat what you were saying?"

            # ============================================
            # PRIORITY 4: FAST CONTEXTUAL RESPONSE (SALES FOCUS!)
            # ============================================
            logger.info("⚡ PRIORITY 4: Using FAST contextual response with SALES FOCUS...")
            
            response = await self._generate_contextual_response(
                user_input=user_input,
                agent_config=agent_config,
                user_id=user_id,
                call_id=call_id,
                db=db,
                call_sid=call_sid  # ✅ PASS CALL_SID
            )
            
            logger.info(f"✅ Response generated: {response[:100]}...")
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in process_user_message: {e}")
            import traceback
            traceback.print_exc()
            return "I apologize, but I had trouble processing that. Could you please repeat your question?"
    
    """
    Add this method to your AgentExecutor class in agent_executor.py
    This enables VAPI-style sentence-by-sentence streaming for ultra-low latency
    """
    # async def generate_streaming_response(
    #     self,
    #     user_input: str,  # ← Parameter name is 'user_input'
    #     agent_config: Dict[str, Any],
    #     user_id: str,
    #     call_id: str,
    #     db,
    #     call_sid: str,
    #     websocket,
    #     stream_sid: str,
    # ):
    #     """
    #     ✅ ENHANCED: Generate streaming response WITH CONVERSATION HISTORY
    #     This enables proper rebuttals, objection handling, and natural flow
    #     """
    #     import time
    #     start_time = time.time()
    #     try:
    #         agent_context = agent_config.get("context", {})
    #         system_prompt = self.openai.build_contextual_system_prompt(
    #             agent_context=agent_context,
    #             agent_name=agent_config.get("name", "AI Assistant")
    #         )
    #         self.conversation_history.append({
    #             "role": "user",
    #             "content": user_input
    #         })
    #         if len(self.conversation_history) > (self.max_history_messages * 2):
    #             self.conversation_history = self.conversation_history[-(self.max_history_messages * 2):]
    #         print(f"⏱️  [AI-DETAIL] Memory loaded")
    #         print(f"⏱️  [CONTEXT] Sending {len(self.conversation_history)} messages (limited from {len(self.conversation_history)} total)")
    #         print("🚀 Starting streaming response...")
        
    #         full_response = ""
    #         current_sentence = ""
    #         sentence_count = 0
        
    #         print(f"🚀 STREAMING chat response with {self.openai.provider} ({self.openai.model})")
        
    #         async for chunk in self.openai.generate_chat_response_stream(
    #             messages=self.conversation_history,  # ✅ FULL HISTORY
    #             system_prompt=system_prompt,
    #             max_tokens=150,  # ✅ Increased for better responses
    #             temperature=0.8   # ✅ Slightly higher for more natural variation
    #         ):
    #             if chunk.get("error"):
    #                 print(f"❌ Streaming error: {chunk['error']}")
    #                 break
                    
    #             if chunk.get("done"):
    #                 # Process any remaining text as final fragment
    #                 if current_sentence.strip():
    #                     sentence_count += 1
    #                     elapsed = time.time() - start_time
    #                     print(f"🎵 [FINAL-FRAGMENT] '{current_sentence.strip()}' (after {elapsed:.2f}s)")
                        
    #                     # Generate and send final audio
    #                     asyncio.create_task(
    #                         self.stream_elevenlabs_audio(current_sentence.strip(), websocket, stream_sid)
    #                     )
    #                 break
                
    #             token = chunk.get("token", "")
    #             if not token:
    #                 continue
                    
    #             full_response += token
    #             current_sentence += token
                
    #             # ✅ Sentence boundary detection (., !, ?)
    #             if token in ".!?":
    #                 sentence = current_sentence.strip()
                    
    #                 # Only process if sentence is substantial (not just "Ok." or "Yes.")
    #                 if len(sentence) > 15:  # ✅ Minimum sentence length
    #                     sentence_count += 1
    #                     elapsed = time.time() - start_time
                        
    #                     print(f"🎵 [SENTENCE-{sentence_count}] '{sentence}' (after {elapsed:.2f}s)")
                        
    #                     # ✅ Generate and send audio for this sentence
    #                     asyncio.create_task(
    #                         self.stream_elevenlabs_audio(sentence, websocket, stream_sid)
    #                     )
                        
    #                     current_sentence = ""
            
    #         total_time = time.time() - start_time
    #         print(f"⏱️ [LLM-STREAM] Completed in {total_time:.2f}s ({sentence_count} sentences)")
            
    #         # ✅ NEW: Add AI response to conversation history
    #         self.conversation_history.append({
    #             "role": "assistant",
    #             "content": full_response.strip()
    #         })
            
    #         print(f"🤖 [AI-REPLY] '{full_response.strip()}'")
            
    #         return full_response.strip()
            
    #     except Exception as e:
    #         print(f"❌ [STREAMING-ERROR] {e}")
    #         import traceback
    #         traceback.print_exc()
            
    #         # ✅ Fallback response
    #         fallback = "I apologize, I didn't catch that. Could you please repeat?"
    #         await self.stream_elevenlabs_audio(fallback, websocket, stream_sid)
    #         return fallback

    # ============================================
    # ✅ NEW: FAST CONTEXTUAL RESPONSE GENERATOR (SALES FOCUS) - REPLACED
    # ============================================
    
    """
COMPLETE REPLACEMENT FOR _generate_contextual_response METHOD
Copy this entire function and replace the existing one in agent_executor.py
"""

    async def _generate_contextual_response(
        self,
        user_input: str,
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db: AsyncIOMotorDatabase,
        call_sid: str = None
    ) -> str:
        """
        ✅ UPDATED: Generate contextual response WITH AGGRESSIVE 40-CHAR LIMIT
        
        Uses per-call memory to maintain context:
        1. Load conversation memory for this CallSid
        2. Build full context (system + summary + history + current)
        3. Send to LLM with complete context
        4. AGGRESSIVELY truncate to 40 characters max
        5. Store turn in memory
        6. Return response
        """
        try:
            logger.info("🧠 Generating contextual response WITH MEMORY...")
            
            # ============================================
            # STEP 1: Get call memory (use call_sid if available)
            # ============================================
            memory_key = call_sid or call_id
            memory = await call_memory_service.get_memory(memory_key, db)
            print(f"⏱️  [AI-DETAIL] Memory loaded")
            
            logger.info(f"📝 Memory loaded - Turn: {memory['turn_count']}, Stage: {memory['stage']}")
            logger.info(f"📝 Has introduced: {memory['has_introduced']}")
            logger.info(f"📝 History length: {len(memory['history'])} messages")
            
            # ============================================
            # STEP 2: Build base system prompt
            # ============================================
            agent_context = agent_config.get("agent_context")
            agent_id = str(agent_config.get("_id", ""))
            
            # Get base system prompt
            if agent_context:
                logger.info("✅ Using pre-built agent context")
                base_system_prompt = self.openai.build_contextual_system_prompt(
                    agent_context=agent_context,
                    agent_name=agent_config.get("name"),
                    ai_script=agent_config.get("ai_script", "")
                )
            else:
                logger.info("⚠️ No agent context, using fallback prompt")
                base_system_prompt = self._build_fallback_system_prompt(agent_config)
            
            # ============================================
            # STEP 3: Build full context with memory
            # ============================================
            messages = call_memory_service.build_context_messages(
                memory=memory,
                system_prompt=base_system_prompt,
                current_user_input=user_input
            )
            
            logger.info(f"📨 Built {len(messages)} messages for LLM")
            
            # ============================================
            # STEP 4: Generate response (STREAMING)
            # ============================================
            print("🚀 Starting streaming response...")
            full_response = ""
            first_token_received = False
        
            async for chunk in self.openai.generate_chat_response_stream(
                messages=messages,
                max_tokens=50,
                temperature=0.7
            ):
                if chunk.get("error"):
                    logger.error(f"Stream error: {chunk['error']}")
                    break 
                
                if chunk.get("token"):
                    if not first_token_received:
                        print("✅ First token received - streaming started!")
                        first_token_received = True
                    full_response += chunk["token"]
                
                if chunk.get("done"):
                    print(f"✅ Stream complete - total response: {len(full_response)} chars")
                    break
        
            response = full_response.strip()
        
            
        
            # Validate response
            if response and len(response) > 3:
                logger.info(f"✅ Response received ({len(response)} chars)")   
                
                # ============================================
                # STEP 6: Store turn in memory
                # ============================================
                await call_memory_service.add_turn(
                    call_sid=memory_key,
                    user_message=user_input,
                    assistant_message=response,
                    db=db
                )
                
                return response
            else:
                logger.warning("⚠️ Empty response from LLM")
                return self._get_sales_fallback_response(agent_config)
            
        except Exception as e:
            logger.error(f"❌ Error generating contextual response: {e}")
            import traceback
            traceback.print_exc()
            return self._get_sales_fallback_response(agent_config)
    


    def _get_sales_fallback_response(self, agent_config: Dict[str, Any]) -> str:
        """
        ✅ NEW: Get a sales-focused fallback response
        Used when OpenAI fails or returns empty response
        """
        company_name = "our company"
        
        # Try to extract company name from agent context or script
        agent_context = agent_config.get("agent_context", {})
        if agent_context:
            identity = agent_context.get("identity", {})
            company_name = identity.get("company", "our company")
        
        fallback_responses = [
            f"I'd love to tell you more about how {company_name} can help you. What specific challenges are you facing that we might be able to solve?",
f"Great question! Let me share how {company_name}'s services could benefit you. What's your biggest priority right now?",
            f"I'm here to help! {company_name} has helped many customers like you. Would you like to hear about our most popular solutions?",
        ]
        
        import random
        return random.choice(fallback_responses)
    
    
    # ============================================
    # PATCH FOR agent_executor.py - ADD STRICT CHARACTER LIMIT
    # ============================================
    
    """
    Replace the _build_fallback_system_prompt method in agent_executor.py
    with this version that enforces 80-character limit
    """
    
    def _build_fallback_system_prompt(self, agent_config: Dict[str, Any]) -> str:
        """
        ✅ ULTRA-SHORT RESPONSES - 30 characters max for sub-1s latency
        """
        agent_name = agent_config.get("name", "AI Assistant")
        agent_context = agent_config.get("agent_context", {})
        company_name = "our company"
        
        if agent_context:
            identity = agent_context.get("identity", {})
            company_name = identity.get("company", "our company")
        
        prompt = f"""You are {agent_name} calling from {company_name}.
    
    🚨 CRITICAL PHONE RULES:
    ━━━━━━━━━━━━━━━━━━━━━━
    MAXIMUM 30 CHARACTERS PER RESPONSE
    ONE short sentence only
    End with brief question
    ━━━━━━━━━━━━━━━━━━━━━━
    
    EXAMPLES (all under 30 chars):
    
    User: "Hello?"
    You: "Hi! What's your main need?" (28 chars) ✅
    
    User: "What services?"
    You: "Sales help. Interested?" (24 chars) ✅
    
    User: "How much?"
    You: "From $99. Want details?" (24 chars) ✅
    
    User: "Tell me more"
    You: "We boost sales. Curious?" (25 chars) ✅
    
    RULES:
    - Drop ALL filler words
    - Use "?" to engage
    - Be direct
    - 30 chars MAX"""
        
        return prompt
        # ============================================
        # FOLLOW-UP/CALLBACK HANDLING (PRESERVED) - ✅ FIXED VERSION
        # ============================================
        
    async def _handle_follow_up_request(
            self,
            user_input: str,
            agent_config: Dict[str, Any],
            user_id: str,
            call_id: str,
            db: AsyncIOMotorDatabase
        ) -> Optional[str]:
            """Handle follow-up/callback requests - CREATES CALENDAR EVENT + DATABASE RECORD"""
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"📞 PROCESSING FOLLOW-UP REQUEST")
                logger.info(f"{'='*60}")
                logger.info(f"   User input: '{user_input}'")
                logger.info(f"   Call ID: {call_id}")
                
                # Parse the follow-up time
                parsed_time = await time_parser_service.parse_follow_up_time(user_input)
                
                logger.info(f"   Parsed time result: {parsed_time}")
                
                # Check if parsed_time is dict with success key
                if not parsed_time:
                    logger.warning("⚠️ Could not parse follow-up time - returning None")
                    return None
                
                # Handle both dict format (new) and datetime format (fallback)
                if isinstance(parsed_time, dict):
                    if not parsed_time.get("success"):
                        logger.warning(f"⚠️ Parse failed: {parsed_time}")
                        return None
                    follow_up_datetime = parsed_time.get("datetime")
                    confidence = parsed_time.get("confidence", "low")
                elif isinstance(parsed_time, datetime):
                    follow_up_datetime = parsed_time
                    confidence = "medium"
                else:
                    logger.warning(f"⚠️ Unknown parsed_time type: {type(parsed_time)}")
                    return None
                
                if not follow_up_datetime:
                    logger.warning("⚠️ No datetime in parsed result")
                    return None
                
                logger.info(f"✅ Follow-up datetime: {follow_up_datetime}")
                logger.info(f"   Confidence: {confidence}")
                
                # Get customer phone from call record
                call = await db.calls.find_one({"_id": ObjectId(call_id)})
                
                if not call:
                    logger.warning(f"⚠️ Call record not found for {call_id}")
                    return None
                
                # Determine customer phone based on call direction
                call_direction = call.get("direction", "inbound")
                if call_direction == "inbound":
                    customer_phone = call.get("from_number") or call.get("phone_number")
                else:
                    customer_phone = call.get("to_number") or call.get("phone_number")
                
                if not customer_phone:
                    logger.warning("⚠️ No customer phone found for follow-up")
                    return None
                
                logger.info(f"📞 Scheduling follow-up call to {customer_phone} at {follow_up_datetime}")
                
                # Get customer name
                customer_name = call.get("contact_name", "Customer")
                customer_email = call.get("contact_email", "")
                
                # ✅ Create follow-up record in database FIRST
                follow_up_data = {
                    "user_id": user_id,
                    "agent_id": str(agent_config.get("_id")),
                    "customer_phone": customer_phone,
                    "customer_name": customer_name,
                    "original_call_id": call_id,
                    "scheduled_time": follow_up_datetime,
                    "status": "scheduled",
                    "confidence": confidence,
                    "original_request": user_input,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                result = await db.follow_ups.insert_one(follow_up_data)
                follow_up_id = str(result.inserted_id)
                logger.info(f"✅ Follow-up saved to database: {follow_up_id}")
                
                # ✅ Create Google Calendar event for follow-up
                calendar_event_id = None
                try:
                    logger.info("📆 Creating Google Calendar event...")
                    calendar_result = await self.calendar_service.create_event(
                        customer_name=customer_name,
                        customer_email=customer_email,
                        customer_phone=customer_phone,
                        appointment_date=follow_up_datetime,
                        appointment_time=follow_up_datetime.strftime("%H:%M"),
                        duration_minutes=15,
                        service_type="Follow-up Call",
                        notes=f"Follow-up callback requested: {user_input}\nOriginal Call ID: {call_id}\nFollow-up ID: {follow_up_id}",
                        event_type="follow_up_call",
                        action_type="call",
                        original_request=user_input,           # ✅ ADD THIS
                        user_id=user_id,                       # ✅ ADD THIS
                      agent_id=str(agent_config.get("_id")) if agent_config else None  # ✅ ADD THIS
                    )
                    
                    logger.info(f"   Calendar result: {calendar_result}")
                    
                    if calendar_result.get("success"):
                        calendar_event_id = calendar_result.get("event_id")
                        logger.info(f"✅ Follow-up calendar event created: {calendar_event_id}")
                        
                        # Update follow-up record with calendar event ID
                        await db.follow_ups.update_one(
                            {"_id": ObjectId(follow_up_id)},
                            {"$set": {
                                "google_calendar_event_id": calendar_event_id,
                                "google_calendar_link": calendar_result.get("html_link")
                            }}
                        )
                    else:
                        logger.warning(f"⚠️ Calendar event creation failed: {calendar_result.get('error')}")
                except Exception as cal_error:
                    logger.error(f"❌ Calendar error: {cal_error}")
                    import traceback
                    traceback.print_exc()
                
                # Format response
                formatted_time = follow_up_datetime.strftime("%A, %B %d at %I:%M %p")
                
                # Get company name
                agent_context = agent_config.get("agent_context", {})
                company_name = "our team"
                if agent_context:
                    identity = agent_context.get("identity", {})
                    company_name = identity.get("company", "our team")
                
                response = f"Perfect! I've scheduled a follow-up call for {formatted_time}. I'll call you back then to discuss how {company_name} can help you. Is there anything specific you'd like me to prepare for our next conversation?"
                
                logger.info(f"✅ Follow-up response: {response[:100]}...")
                logger.info(f"{'='*60}\n")
                
                return response
                
            except Exception as e:
                logger.error(f"❌ Error handling follow-up: {e}")
                import traceback
                traceback.print_exc()
                return None

    # ============================================
    # APPOINTMENT BOOKING (FULLY PRESERVED)
    # ============================================
    
    def _is_appointment_request(self, user_input: str) -> bool:
        """Check if user is requesting an appointment"""
        user_input_lower = user_input.lower()
        for keyword in self.appointment_keywords:
            if keyword in user_input_lower:
                return True
            return False
    
    
    async def _handle_appointment_booking(
        self,
        user_input: str,
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db: AsyncIOMotorDatabase
    ) -> Optional[str]:
        """Handle appointment booking conversation - FIXED VERSION WITH PROPER EXTRACTION"""
        try:
            user_input_lower = user_input.lower().strip()
            
            # ✅ STEP 0: Check for CANCEL/EXIT intent FIRST
            cancel_keywords = ["cancel", "don't want", "no thanks", "not interested", 
                                  "stop", "quit", "exit", "goodbye", "bye", "no appointment",
                                  "never mind", "forget it", "changed my mind", "no longer"]
            
            if any(keyword in user_input_lower for keyword in cancel_keywords):
                logger.info("🚫 User wants to cancel appointment booking")
                if call_id in self.active_bookings:
                    del self.active_bookings[call_id]
                return "No problem! I've cancelled the booking. Is there anything else I can help you with today?"
            
            # Get company name for personalized responses
            agent_context = agent_config.get("agent_context", {})
            company_name = "our team"
            if agent_context:
                identity = agent_context.get("identity", {})
                company_name = identity.get("company", "our team")
            
            # ✅ Initialize booking state if needed
            if call_id not in self.active_bookings:
                logger.info("📅 Starting NEW appointment booking flow")
                self.active_bookings[call_id] = {
                    "step": "name",
                    "collected_data": {},
                    "started_at": datetime.utcnow()
                }
                
                # ✅ Try to extract data from initial request
                # Check if user provided date/time in initial request
                date = self._extract_date(user_input)
                time_str = self._extract_time(user_input)
                
                if date:
                    self.active_bookings[call_id]["collected_data"]["date"] = date
                    logger.info(f"✅ Pre-extracted date: {date}")
                if time_str:
                    self.active_bookings[call_id]["collected_data"]["time"] = time_str
                    logger.info(f"✅ Pre-extracted time: {time_str}")
            
            booking_state = self.active_bookings[call_id]
            current_step = booking_state["step"]
            collected_data = booking_state["collected_data"]
            
            logger.info(f"📋 Appointment booking step: {current_step}")
            logger.info(f"   Collected data: {collected_data}")
            
            # Step: Get Name
            if current_step == "name":
                name = self._extract_name(user_input)
                if name:
                    collected_data["name"] = name
                    booking_state["step"] = "email"
                    self.active_bookings[call_id] = booking_state
                    logger.info(f"✅ Name extracted: {name}")
                    return f"Nice to meet you, {name}! What's the best email to reach you at?"
                else:
                    # Be more lenient - accept the input as name if it's reasonable
                    clean_input = user_input.strip()
                    # ✅ FIX: Reject sentences that are booking commands, not names
                    booking_noise = ["book", "appointment", "schedule", "meeting", "yes", "sure",
                                     "want to", "can you", "please", "i'd like", "i want", "set up"]
                    is_booking_phrase = any(word in clean_input.lower() for word in booking_noise)
                    word_count = len(clean_input.split())

                    if (len(clean_input) >= 2 and len(clean_input) <= 30
                        and word_count <= 4
                        and not any(c.isdigit() for c in clean_input[:3])
                        and not is_booking_phrase):
                        # Accept it as a name
                        name = clean_input.title()
                        collected_data["name"] = name
                        booking_state["step"] = "email"
                        self.active_bookings[call_id] = booking_state
                        logger.info(f"✅ Name accepted (lenient): {name}")
                        return f"Nice to meet you, {name}! What's the best email to reach you at?"
                    return "Sure, I'd be happy to help with that! May I get your name first?"
            
            # Step: Get Email  (uses AI for accurate voice-to-email conversion)
            elif current_step == "email":
                # Handle "same email" / "the one I gave" by searching call transcript
                same_patterns = ["same email", "same one", "the one i gave", "already gave",
                                 "previous email", "that email", "use that email", "use that one"]
                if any(p in user_input_lower for p in same_patterns):
                    found_email = None
                    try:
                        call = await db.calls.find_one({"_id": ObjectId(call_id)})
                        if call and call.get("transcripts"):
                            for t in reversed(call["transcripts"]):
                                user_text = t.get("user", "")
                                email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', user_text.lower())
                                if email_match:
                                    found_email = email_match.group(0)
                                    logger.info(f"Found previous email from transcript: {found_email}")
                                    break
                    except Exception as e:
                        logger.error(f"Error searching transcript for email: {e}")

                    if found_email:
                        collected_data["email"] = found_email
                        booking_state["step"] = "date" if not collected_data.get("date") else "time"
                        booking_state["pending_email_confirm"] = found_email
                        self.active_bookings[call_id] = booking_state
                        if collected_data.get("date"):
                            return f"I have your email as {found_email}. Is that correct?"
                        return f"I have your email as {found_email}. Is that correct?"
                    else:
                        name = collected_data.get("name", "")
                        return f"I couldn't find a previous email. {name}, could you please tell me your email address?"

                # Use AI-powered extraction to handle STT mishearings correctly
                email = await self._extract_email_enhanced_ai(user_input)
                if email:
                    collected_data["email"] = email
                    booking_state["step"] = "date" if not collected_data.get("date") else "time"
                    # \u2705 FIX: Read the email back to the user so they can confirm / correct it
                    booking_state["pending_email_confirm"] = email
                    self.active_bookings[call_id] = booking_state
                    logger.info(f"\u2705 Email extracted (AI): {email}")
                    
                    if collected_data.get("date"):
                        return f"I have your email as {email}. Is that correct?"
                    return f"I have your email as {email}. Is that correct?"
                else:
                    name = collected_data.get("name", "")
                    return f"I didn't quite catch that email, {name}. Could you spell it out slowly? For example: 'john, at, gmail, dot, com'"
            
            # Step: Get Date
            elif current_step == "date":
                # Check if this is a response to email confirmation ("Is that correct?")
                if booking_state.get("pending_email_confirm"):
                    confirm_no = any(w in user_input_lower for w in ["no", "wrong", "incorrect", "not correct", "nope", "update"])
                    confirm_yes = any(w in user_input_lower for w in ["yes", "yeah", "correct", "right", "yep", "that's right"])

                    if confirm_no:
                        # Go back to email step
                        booking_state["step"] = "email"
                        del booking_state["pending_email_confirm"]
                        collected_data.pop("email", None)
                        self.active_bookings[call_id] = booking_state
                        logger.info("Email rejected by user, asking again")
                        return "No problem! What's the correct email address?"

                    if confirm_yes:
                        # Email confirmed, continue
                        del booking_state["pending_email_confirm"]
                        self.active_bookings[call_id] = booking_state
                        logger.info(f"Email confirmed: {collected_data.get('email')}")
                        if collected_data.get("date"):
                            return f"Great! And what time works best for you on {collected_data['date'].strftime('%B %d, %Y')}?"
                        return "Great! What date works best for you?"

                    # If user gave an email instead of yes/no, try to extract it
                    new_email = await self._extract_email_enhanced_ai(user_input)
                    if new_email:
                        collected_data["email"] = new_email
                        booking_state["pending_email_confirm"] = new_email
                        self.active_bookings[call_id] = booking_state
                        return f"I have your email as {new_email}. Is that correct?"

                date = self._extract_date(user_input)
                if date:
                    collected_data["date"] = date
                    booking_state["step"] = "time" if not collected_data.get("time") else "confirm"
                    self.active_bookings[call_id] = booking_state
                    logger.info(f"✅ Date extracted: {date}")
                    
                    if collected_data.get("time"):
                        # We have all data, create appointment
                        return await self._finalize_appointment(collected_data, agent_config, user_id, call_id, db, company_name)
                    return f"Perfect! And what time would work for you on {date.strftime('%B %d, %Y')}?"
                else:
                    return "I didn't catch that date. Could you say it again? Like 'tomorrow' or 'next Friday' would work."
            
            # Step: Get Time and Create Appointment
            elif current_step == "time":
                time_str = self._extract_time(user_input)
                if time_str:
                    collected_data["time"] = time_str
                    self.active_bookings[call_id] = booking_state
                    logger.info(f"✅ Time extracted: {time_str}")
                    
                    # ✅ CREATE THE APPOINTMENT NOW!
                    return await self._finalize_appointment(collected_data, agent_config, user_id, call_id, db, company_name)
                else:
                    return "I didn't quite catch that time. Could you say it again? Like '2 PM' or '10:30 AM' would work."
            
            return None
            
        except Exception as e:
            logger.error(f"Error in appointment booking: {e}", exc_info=True)
            if call_id in self.active_bookings:
                del self.active_bookings[call_id]
            return "I apologize, but there was an error with the booking. Let's start over. Would you like to schedule an appointment?"
    
    
    async def _finalize_appointment(
        self,
        collected_data: Dict[str, Any],
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db: AsyncIOMotorDatabase,
        company_name: str
    ) -> str:
        """Finalize and create the appointment"""
        try:
            # Check if we have all required data
            has_name = collected_data.get("name")
            has_email = collected_data.get("email")
            has_date = collected_data.get("date")
            has_time = collected_data.get("time")
            
            logger.info(f"📅 Finalizing appointment:")
            logger.info(f"   Name: {has_name}")
            logger.info(f"   Email: {has_email}")
            logger.info(f"   Date: {has_date}")
            logger.info(f"   Time: {has_time}")
            
            if has_name and has_email and has_date and has_time:
                logger.info("✅ All appointment data collected, creating appointment...")
                
                # CREATE THE APPOINTMENT
                result = await self._create_appointment(
                    collected_data=collected_data,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db
                )
                
                # Clear booking state
                if call_id in self.active_bookings:
                    del self.active_bookings[call_id]
                
                if result.get("success"):
                    formatted_date = collected_data["date"].strftime("%A, %B %d")
                    # ✅ Auto-transition to payment after booking is confirmed
                    self.active_payments[call_id] = {
                        "step": "cardholder_name",
                        "collected": {},
                        "started_at": datetime.utcnow()
                    }
                    return (
                        f"Perfect! Your appointment is confirmed for {formatted_date} at {collected_data['time']}. "
                        f"I've sent a confirmation email to {collected_data['email']}. "
                        f"To complete your booking, I'll need your payment details. "
                        f"Could you please tell me the name as it appears on your card?"
                    )
                else:
                    return f"I apologize, but there was an issue booking your appointment: {result.get('error', 'Unknown error')}. Would you like to try again?"
            else:
                # Ask for missing data
                missing = []
                if not has_name: missing.append("name")
                if not has_email: missing.append("email")
                if not has_date: missing.append("preferred date")
                if not has_time: missing.append("preferred time")
                
                return f"I still need your {missing[0]}. Could you provide that?"
                
        except Exception as e:
            logger.error(f"❌ Error finalizing appointment: {e}")
            import traceback
            traceback.print_exc()
            return "I apologize, there was an error creating your appointment. Would you like to try again?"
    
    
    # ============================================
    # ✅ PAYMENT COLLECTION STATE MACHINE
    # ============================================

    # Spoken digit words → actual digit characters
    _DIGIT_WORDS = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'oh': '0', 'o': '0',
    }

    def _spoken_to_digits(self, text: str) -> str:
        """Replace spoken digit words with actual digit characters."""
        result = text.lower()
        for word, digit in self._DIGIT_WORDS.items():
            result = re.sub(r'\b' + word + r'\b', digit, result)
        return result

    # Map spoken number words to their integer values (for expiry date parsing)
    _SPOKEN_NUMBERS = {
        # Teens and above — must come BEFORE single-digit words to avoid partial matches
        'twenty-nine': 29, 'twenty-eight': 28, 'twenty-seven': 27, 'twenty-six': 26,
        'twenty-five': 25, 'twenty-four': 24, 'twenty-three': 23, 'twenty-two': 22,
        'twenty-one': 21, 'thirty-one': 31, 'thirty': 30, 'twenty': 20,
        'nineteen': 19, 'eighteen': 18, 'seventeen': 17, 'sixteen': 16,
        'fifteen': 15, 'fourteen': 14, 'thirteen': 13, 'twelve': 12,
        'eleven': 11, 'ten': 10,
        # Spaced variants (two-word forms)
        'twenty nine': 29, 'twenty eight': 28, 'twenty seven': 27, 'twenty six': 26,
        'twenty five': 25, 'twenty four': 24, 'twenty three': 23, 'twenty two': 22,
        'twenty one': 21, 'thirty one': 31,
        # Single digits
        'nine': 9, 'eight': 8, 'seven': 7, 'six': 6, 'five': 5,
        'four': 4, 'three': 3, 'two': 2, 'one': 1,
    }

    # Month name → numeric string
    _MONTH_NAMES = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12',
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
        'oct': '10', 'nov': '11', 'dec': '12',
    }

    def _spoken_number_to_int(self, text: str) -> Optional[int]:
        """Convert a spoken number word/phrase to an integer (1-31 range)."""
        t = text.lower().strip()
        # Try longest matches first (multi-word like "twenty six")
        for phrase, value in sorted(self._SPOKEN_NUMBERS.items(), key=lambda x: -len(x[0])):
            if t == phrase:
                return value
        # Try converting via single-digit words
        normalized = self._spoken_to_digits(t)
        digits = re.sub(r'\D', '', normalized)
        if digits and len(digits) <= 2:
            val = int(digits)
            if 1 <= val <= 31:
                return val
        return None

    def _extract_card_number(self, text: str) -> Optional[str]:
        """Extract 16-digit card number from spoken text."""
        normalized = self._spoken_to_digits(text)
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', normalized)
        if len(digits) == 16:
            return digits
        # If more digits present, return None — don't guess which 16 are correct
        if len(digits) > 16:
            return None
        return None

    def _extract_expiry_date(self, text: str) -> Optional[str]:
        """Extract expiry date as MM/YY from spoken text.

        Handles all common formats:
          - '12/26', '12/2026'          (slash notation)
          - '12 26', '12 2026'          (space-separated digits)
          - 'December 2026', 'Dec 26'   (month name + digits)
          - 'twelve twenty six'         (spoken month + spoken year)
          - 'twelve 26', '12 twenty-six'(mixed spoken/digit)
          - 'one two two six'           (all single digits → 1226 → 12/26)
        """
        text_lower = text.lower().strip()

        # ── 1. Slash notation: "12/26" or "12/2026" ──────────────────────────
        m = re.search(r'\b(0?[1-9]|1[0-2])\s*/\s*(2\d|20[2-9]\d)\b', text_lower)
        if m:
            month = m.group(1).zfill(2)
            year = m.group(2)[-2:]
            return f"{month}/{year}"

        # ── 2. Space-separated numeric digits: "12 26" or "12 2026" ──────────
        m = re.search(r'\b(0?[1-9]|1[0-2])\s+(2\d|20[2-9]\d)\b', text_lower)
        if m:
            month = m.group(1).zfill(2)
            year = m.group(2)[-2:]
            return f"{month}/{year}"

        # ── 3. Month name + numeric year: "December 2026", "Dec 26" ──────────
        for name, num in self._MONTH_NAMES.items():
            m = re.search(rf'\b{name}\b.*?\b(2\d|20[2-9]\d)\b', text_lower)
            if m:
                year = m.group(1)[-2:]
                return f"{num}/{year}"

        # ── 4. Month name + spoken year: "December twenty six" ───────────────
        for name, num in self._MONTH_NAMES.items():
            if name in text_lower:
                # Everything after the month name is the year part
                after = text_lower.split(name, 1)[1].strip(' ,-')
                year_val = None
                # Try multi-word spoken number first (e.g. "twenty six")
                for phrase, val in sorted(self._SPOKEN_NUMBERS.items(), key=lambda x: -len(x[0])):
                    if after.startswith(phrase) or after == phrase:
                        year_val = val
                        break
                # Try single spoken digit words via _spoken_to_digits
                if year_val is None:
                    norm = re.sub(r'\D', '', self._spoken_to_digits(after))
                    if norm and len(norm) <= 4:
                        year_val = int(norm[-2:]) if len(norm) >= 2 else int(norm)
                if year_val is not None and 20 <= year_val <= 99:
                    return f"{num}/{str(year_val).zfill(2)}"
                if year_val is not None and 2020 <= year_val <= 2099:
                    return f"{num}/{str(year_val)[-2:]}"

        # ── 5. Spoken month number + spoken/digit year: "twelve twenty six" ──
        # Longest spoken-number phrases first to avoid premature partial matches
        for phrase, month_val in sorted(self._SPOKEN_NUMBERS.items(), key=lambda x: -len(x[0])):
            if not (1 <= month_val <= 12):
                continue
            # Build regex that allows optional separator between month and year
            pattern = re.compile(
                r'\b' + re.escape(phrase) + r'\b[,\s]*(.*)',
                re.IGNORECASE
            )
            pm = pattern.search(text_lower)
            if not pm:
                continue
            remainder = pm.group(1).strip()
            if not remainder:
                continue

            year_val = None

            # Try spoken year words in remainder (e.g. "twenty six", "twenty-six")
            for yr_phrase, yr_val in sorted(self._SPOKEN_NUMBERS.items(), key=lambda x: -len(x[0])):
                if remainder.startswith(yr_phrase) or remainder == yr_phrase:
                    year_val = yr_val
                    break

            # Try numeric year in remainder (e.g. "26", "2026")
            if year_val is None:
                nm = re.search(r'\b(2\d|20[2-9]\d)\b', remainder)
                if nm:
                    year_val = int(nm.group(1)[-2:])

            # Try single-digit spoken words in remainder (e.g. "two six")
            if year_val is None:
                norm = re.sub(r'\D', '', self._spoken_to_digits(remainder))
                if norm and 1 <= len(norm) <= 2:
                    year_val = int(norm)

            if year_val is not None and 20 <= year_val <= 99:
                return f"{str(month_val).zfill(2)}/{str(year_val).zfill(2)}"

        # ── 6. All single-digit spoken words → MMYY: "one two two six" → 1226 ─
        normalized = self._spoken_to_digits(text_lower)
        digits = re.sub(r'\D', '', normalized)
        if len(digits) == 4:
            month = int(digits[:2])
            year = digits[2:]
            if 1 <= month <= 12:
                return f"{str(month).zfill(2)}/{year}"

        return None

    def _extract_cvc(self, text: str) -> Optional[str]:
        """Extract 3 or 4 digit CVC from spoken text."""
        normalized = self._spoken_to_digits(text)
        digits = re.sub(r'\D', '', normalized)
        if len(digits) in (3, 4):
            return digits
        # If more digits, try to find 3-4 consecutive
        m = re.search(r'\b(\d{3,4})\b', normalized)
        if m:
            return m.group(1)
        return None

    async def _handle_payment_collection(
        self,
        user_input: str,
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db: AsyncIOMotorDatabase,
        call_sid: str = None
    ) -> Optional[str]:
        """
        Collect payment details from user via voice — step-by-step state machine.
        Steps: cardholder_name → card_number → expiry → cvc → confirm → saved
        """
        try:
            user_input_lower = user_input.lower().strip()

            # Cancel intent — exit payment flow
            cancel_keywords = [
                "cancel", "stop", "don't want", "no thanks", "not interested",
                "quit", "exit", "forget it", "never mind", "changed my mind",
            ]
            if any(kw in user_input_lower for kw in cancel_keywords):
                if call_id in self.active_payments:
                    del self.active_payments[call_id]
                return "No problem! I've cancelled the payment process. Is there anything else I can help you with?"

            # Initialize payment state on first call
            if call_id not in self.active_payments:
                logger.info("💳 Starting NEW payment collection flow")
                self.active_payments[call_id] = {
                    "step": "cardholder_name",
                    "collected": {},
                    "started_at": datetime.utcnow()
                }
                return (
                    "Great! I'll need a few payment details to get you started. "
                    "First, could you please tell me the name on your card?"
                )

            state = self.active_payments[call_id]
            step = state["step"]
            collected = state["collected"]

            logger.info(f"💳 Payment step: {step} | Collected: {list(collected.keys())}")

            # ── Step: Cardholder Name ─────────────────────────────────────────
            if step == "cardholder_name":
                # Pre-clean the input: strip leading filler words/phrases including
                # punctuation variants like "yes, " or "yes," before any extraction.
                _leading_fillers = [
                    "my name is", "the name is", "name is", "it's", "its",
                    "it is", "this is", "i am", "i'm", "call me",
                    "yes", "yeah", "sure", "ok", "okay", "um", "uh",
                    "so", "well", "right", "hello", "hi",
                ]
                cleaned_input = user_input.strip()
                cleaned_lower = cleaned_input.lower()
                # Strip one leading filler (handles "yes, my name is..." or "yes my name is...")
                for filler in sorted(_leading_fillers, key=len, reverse=True):
                    if cleaned_lower.startswith(filler):
                        after = cleaned_input[len(filler):].lstrip(" ,.")
                        if after:  # only strip if something remains
                            cleaned_input = after.strip()
                            cleaned_lower = cleaned_input.lower()
                            break

                # Try structured extraction first (handles "my name is X" patterns)
                name = self._extract_name(cleaned_input)

                if not name:
                    # Fallback: accept anything that looks like a name after cleaning
                    # Allow up to 4 words to handle "First Middle Last" or names with Jr/Sr
                    words = cleaned_input.split()
                    if (2 <= len(cleaned_input) <= 50
                            and not any(c.isdigit() for c in cleaned_input)
                            and 1 <= len(words) <= 4):
                        name = cleaned_input.title()

                if name:
                    collected["cardholder_name"] = name
                    state["step"] = "card_number"
                    return f"Thank you, {name}. Now, could you please read me your 16-digit card number, one digit at a time?"
                return "I didn't catch that. Could you please tell me the name as it appears on your card?"

            # ── Step: Card Number ─────────────────────────────────────────────
            elif step == "card_number":
                card_number = self._extract_card_number(user_input)
                if card_number:
                    # ✅ Validate via Luhn algorithm + card type detection
                    validation = validate_card_number(card_number)
                    if not validation["valid"]:
                        logger.info(f"💳 [CARD-INVALID] {validation['error']} for input: {user_input[:40]}")
                        return validation["voice_message"]

                    # Store card number and detected card type
                    collected["card_number"] = card_number
                    collected["card_type"] = validation["card_type"]["type"]
                    collected["card_type_name"] = validation["card_type"]["name"]
                    state["step"] = "confirm_card"

                    # Read back all digits in groups of 4 for user to verify
                    groups = [card_number[i:i+4] for i in range(0, len(card_number), 4)]
                    groups_spoken = ", ".join([" ".join(g) for g in groups])
                    return (
                        f"I have your {validation['card_type']['name']} card number as {groups_spoken}. "
                        f"Is that correct?"
                    )
                return (
                    "I didn't quite catch all 16 digits. Could you read your card number again, "
                    "one digit at a time? For example: one, two, three, four..."
                )

            # ── Step: Confirm Card Number ─────────────────────────────────────
            elif step == "confirm_card":
                confirmed = any(w in user_input_lower for w in [
                    "yes", "yeah", "correct", "right", "yep", "that's right",
                    "that is correct", "confirm", "confirmed", "go ahead",
                ])
                rejected = any(w in user_input_lower for w in [
                    "no", "nope", "wrong", "incorrect", "not right", "that's wrong",
                ])
                if confirmed:
                    state["step"] = "expiry"
                    return "Great! What is the expiry date on your card? For example, say 'twelve twenty six' for December 2026."
                if rejected:
                    del collected["card_number"]
                    state["step"] = "card_number"
                    return "No problem! Could you please read me your card number again, one digit at a time?"
                return "Could you say 'yes' if the card number is correct, or 'no' to re-enter it?"

            # ── Step: Expiry Date ─────────────────────────────────────────────
            elif step == "expiry":
                expiry = self._extract_expiry_date(user_input)
                if expiry:
                    # ✅ Validate expiry is not in the past
                    expiry_check = validate_expiry(expiry)
                    if not expiry_check["valid"]:
                        logger.info(f"💳 [EXPIRY-INVALID] {expiry_check['error']} for '{expiry}'")
                        return expiry_check["voice_message"]

                    collected["expiry_date"] = expiry
                    state["step"] = "cvc"
                    cvc_digits = "4" if collected.get("card_type") == "amex" else "3"
                    return (
                        f"Expiry {expiry} noted. "
                        f"And finally, what is the {cvc_digits}-digit security code on the back of your card?"
                    )
                return "I didn't catch that. Could you say the expiry date again? For example: 'twelve twenty six' for December 2026."

            # ── Step: CVC ─────────────────────────────────────────────────────
            elif step == "cvc":
                cvc = self._extract_cvc(user_input)
                if cvc:
                    # ✅ Validate CVC length against detected card type (Amex = 4, others = 3)
                    card_type = collected.get("card_type", "unknown")
                    cvc_check = validate_cvc(cvc, card_type)
                    if not cvc_check["valid"]:
                        logger.info(f"💳 [CVC-INVALID] {cvc_check['error']}")
                        return cvc_check["voice_message"]

                    collected["cvc"] = cvc_check["cvc"]
                    state["step"] = "confirm"
                    name = collected.get("cardholder_name", "")
                    last4 = collected.get("card_number", "")[-4:]
                    expiry = collected.get("expiry_date", "")
                    return (
                        f"Perfect! Let me confirm your details. "
                        f"Card holder: {name}. "
                        f"Card ending in {' '.join(last4)}. "
                        f"Expiry: {expiry}. "
                        f"Is that all correct?"
                    )
                return "I didn't catch that. Could you say your security code again, one digit at a time?"

            # ── Step: Confirm ─────────────────────────────────────────────────
            elif step == "confirm":
                confirmed = any(w in user_input_lower for w in [
                    "yes", "yeah", "correct", "right", "yep", "that's right",
                    "that is correct", "confirm", "confirmed", "go ahead", "proceed",
                ])
                rejected = any(w in user_input_lower for w in [
                    "no", "nope", "wrong", "incorrect", "not right", "that's wrong",
                ])

                if rejected:
                    # Restart from beginning
                    self.active_payments[call_id] = {
                        "step": "cardholder_name",
                        "collected": {},
                        "started_at": datetime.utcnow()
                    }
                    return "No problem! Let's start over. What is the name on your card?"

                if confirmed:
                    # Save payment details to database
                    result = await self._save_payment_details(
                        collected=collected,
                        agent_config=agent_config,
                        user_id=user_id,
                        call_id=call_id,
                        call_sid=call_sid,
                        db=db
                    )
                    del self.active_payments[call_id]

                    if result.get("success"):
                        return (
                            "Your payment details have been securely recorded. "
                            "Our team will process your order and reach out shortly. "
                            "Is there anything else I can help you with today?"
                        )
                    else:
                        return "I'm sorry, there was an issue saving your details. Please call back and we'll try again."

                return "I didn't catch that. Could you say 'yes' to confirm or 'no' to re-enter your card details?"

            return None

        except Exception as e:
            logger.error(f"❌ Error in payment collection: {e}", exc_info=True)
            if call_id in self.active_payments:
                del self.active_payments[call_id]
            return "I apologize, there was an issue processing your payment details. Please try again."

    async def _save_payment_details(
        self,
        collected: Dict[str, Any],
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        call_sid: str,
        db: AsyncIOMotorDatabase
    ) -> Dict[str, Any]:
        """Save collected payment details to the call_payment_details collection."""
        try:
            agent_name = agent_config.get("name", "AI Agent")
            record = {
                "user_id": user_id,
                "call_id": call_id,
                "call_sid": call_sid,
                "agent_name": agent_name,
                "cardholder_name": collected.get("cardholder_name", ""),
                "card_number": collected.get("card_number", ""),   # last 4 stored for display
                "card_last4": collected.get("card_number", "")[-4:] if collected.get("card_number") else "",
                "expiry_date": collected.get("expiry_date", ""),
                "cvc": collected.get("cvc", ""),
                "collected_at": datetime.utcnow(),
                "status": "collected",
            }
            result = await db.call_payment_details.insert_one(record)
            logger.info(f"✅ Payment details saved: {result.inserted_id}")
            return {"success": True, "payment_id": str(result.inserted_id)}
        except Exception as e:
            logger.error(f"❌ Failed to save payment details: {e}")
            return {"success": False, "error": str(e)}

    async def _continue_appointment_booking(
        self,
        user_input: str,
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db: AsyncIOMotorDatabase
    ) -> Optional[str]:
        """Continue existing appointment booking conversation"""
        return await self._handle_appointment_booking(
            user_input=user_input,
            agent_config=agent_config,
            user_id=user_id,
            call_id=call_id,
            db=db
        )
    
    
    async def _create_appointment(
        self,
        collected_data: Dict[str, Any],
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db: AsyncIOMotorDatabase
    ) -> Dict[str, Any]:
        """Create appointment in Google Calendar and send email - FIXED VERSION"""
        try:
            logger.info("📅 Creating appointment in Google Calendar")
            logger.info(f"   Name: {collected_data.get('name')}")
            logger.info(f"   Email: {collected_data.get('email')}")
            logger.info(f"   Date: {collected_data.get('date')}")
            logger.info(f"   Time: {collected_data.get('time')}")
            
            # Get company name
            agent_context = agent_config.get("agent_context", {})
            company_name = "our team"
            if agent_context:
                identity = agent_context.get("identity", {})
                company_name = identity.get("company", "our team")
            
            # Combine date and time
            appointment_date = collected_data["date"]
            appointment_time_str = collected_data["time"]
            
            # Parse time string to datetime
            try:
                time_obj = datetime.strptime(appointment_time_str, "%I:%M %p").time()
            except:
                try:
                    time_obj = datetime.strptime(appointment_time_str, "%H:%M").time()
                except:
                    # Default to 10 AM if parsing fails
                    time_obj = datetime.strptime("10:00 AM", "%I:%M %p").time()
            
            appointment_datetime = datetime.combine(appointment_date, time_obj)
            appointment_time = appointment_datetime.strftime("%H:%M")
            
            logger.info(f"   Combined datetime: {appointment_datetime}")
            
            # Get customer phone from call record
            call = await db.calls.find_one({"_id": ObjectId(call_id)})
            customer_phone = ""
            if call:
                call_direction = call.get("direction", "inbound")
                if call_direction == "inbound":
                    customer_phone = call.get("from_number") or call.get("phone_number", "")
                else:
                    customer_phone = call.get("to_number") or call.get("phone_number", "")
            
            # Use collected phone if available
            if collected_data.get("phone"):
                customer_phone = collected_data["phone"]
            
            # ✅ Create Google Calendar event
            logger.info("📆 Calling Google Calendar API...")
            calendar_result = await self.calendar_service.create_event(
                customer_name=collected_data["name"],
                customer_email=collected_data["email"],
                customer_phone=customer_phone,
                appointment_date=appointment_datetime,
                appointment_time=appointment_time,
                duration_minutes=60,
                service_type=collected_data.get("service", "Consultation"),
                notes=f"Booked via voice call.\nCall ID: {call_id}"
            )
            
            if calendar_result.get("success"):
                logger.info(f"✅ Google Calendar event created: {calendar_result.get('event_id')}")
            else:
                logger.error(f"❌ Google Calendar error: {calendar_result.get('error')}")
            
            # Save to database
            appointment_data = {
                "customer_name": collected_data["name"],
                "customer_email": collected_data["email"],
                "customer_phone": customer_phone,
                "appointment_date": appointment_datetime,
                "appointment_time": collected_data["time"],
                "service_type": collected_data.get("service", "Consultation"),
                "call_id": call_id,
                "user_id": user_id,
                "agent_id": str(agent_config.get("_id")),
                "status": "scheduled",
                "google_calendar_event_id": calendar_result.get("event_id") if calendar_result.get("success") else None,
                "google_calendar_link": calendar_result.get("html_link") if calendar_result.get("success") else None,
                "booking_source": "voice_call",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await db.appointments.insert_one(appointment_data)
            appointment_id = str(result.inserted_id)
            
            logger.info(f"✅ Appointment saved to database: {appointment_id}")
            
            # Send confirmation email
            try:
                from app.services.email_automation import email_automation_service

                formatted_date = appointment_datetime.strftime("%A, %B %d, %Y at %I:%M %p")

                print(f"📧 [EMAIL] Sending confirmation email to {collected_data['email']}...")

                email_result = await email_automation_service.send_appointment_confirmation(
                    to_email=collected_data["email"],
                    customer_name=collected_data["name"],
                    customer_phone=customer_phone,
                    service_type=collected_data.get("service", "Consultation"),
                    appointment_date=formatted_date,
                    user_id=user_id,
                    appointment_id=appointment_id,
                    call_id=call_id
                )

                if email_result and email_result.get("success"):
                    print(f"✅ [EMAIL] Confirmation email sent successfully to {collected_data['email']}")
                    logger.info(f"✅ Confirmation email sent to {collected_data['email']}")
                else:
                    print(f"❌ [EMAIL] Confirmation email failed: {email_result}")
                    logger.error(f"❌ Confirmation email failed: {email_result}")

            except Exception as email_error:
                print(f"❌ [EMAIL] Exception sending confirmation email: {email_error}")
                logger.error(f"⚠️ Failed to send confirmation email: {email_error}")
                import traceback
                traceback.print_exc()

            # Schedule reminder email (1 hour before appointment)
            try:
                reminder_time = appointment_datetime - timedelta(hours=1)
                # Only schedule if reminder time is in the future
                if reminder_time > datetime.utcnow():
                    reminder_doc = {
                        "user_id": user_id,
                        "customer_name": collected_data["name"],
                        "customer_email": collected_data["email"],
                        "customer_phone": customer_phone,
                        "reminder_message": f"This is a reminder that your {collected_data.get('service', 'Consultation')} appointment is in 1 hour at {collected_data['time']}.",
                        "reminder_type": "email",
                        "scheduled_time": reminder_time,
                        "appointment_id": appointment_id,
                        "status": "scheduled",
                        "sent": False,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                    await db.reminders.insert_one(reminder_doc)
                    print(f"⏰ [REMINDER] Email reminder scheduled for {reminder_time} (1hr before appointment)")
                    logger.info(f"✅ Reminder email scheduled for {reminder_time} (1hr before appointment)")

                    # Also schedule the reminder via background task
                    delay_seconds = (reminder_time - datetime.utcnow()).total_seconds()
                    print(f"⏰ [REMINDER] Background task will send in {delay_seconds:.0f}s")
                    asyncio.create_task(self._send_delayed_reminder_email(
                        delay_seconds=delay_seconds,
                        to_email=collected_data["email"],
                        customer_name=collected_data["name"],
                        customer_phone=customer_phone,
                        service_type=collected_data.get("service", "Consultation"),
                        appointment_time=collected_data["time"],
                        appointment_date=appointment_datetime,
                        user_id=user_id,
                        appointment_id=appointment_id
                    ))
                else:
                    logger.info("⏭️ Appointment is less than 1 hour away, skipping reminder")
            except Exception as reminder_error:
                logger.error(f"⚠️ Failed to schedule reminder: {reminder_error}")

            return {
                "success": True,
                "appointment_id": appointment_id,
                "google_calendar_event_id": calendar_result.get("event_id"),
                "google_calendar_link": calendar_result.get("html_link")
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating appointment: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    
    async def _send_delayed_reminder_email(
        self,
        delay_seconds: float,
        to_email: str,
        customer_name: str,
        customer_phone: str,
        service_type: str,
        appointment_time: str,
        appointment_date: datetime,
        user_id: str,
        appointment_id: str
    ):
        """Send a reminder email after a delay (background task)"""
        try:
            logger.info(f"⏰ Reminder email scheduled in {delay_seconds:.0f}s for {to_email}")
            await asyncio.sleep(delay_seconds)

            from app.services.email_automation import email_automation_service
            from app.database import get_database

            formatted_date = appointment_date.strftime("%A, %B %d, %Y at %I:%M %p")

            # Build reminder email HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #F59E0B; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 20px; }}
                    .appointment-details {{ background-color: white; padding: 15px; margin: 20px 0; border-left: 4px solid #F59E0B; }}
                    .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Appointment Reminder</h1>
                    </div>
                    <div class="content">
                        <p>Dear {customer_name},</p>
                        <p>This is a friendly reminder that your appointment is coming up in <strong>1 hour</strong>!</p>

                        <div class="appointment-details">
                            <h3>Appointment Details:</h3>
                            <p><strong>Service:</strong> {service_type}</p>
                            <p><strong>Date & Time:</strong> {formatted_date}</p>
                            <p><strong>Contact:</strong> {customer_phone}</p>
                        </div>

                        <p>We look forward to seeing you!</p>
                        <p>If you need to reschedule or cancel, please contact us as soon as possible.</p>
                    </div>
                    <div class="footer">
                        <p>This is an automated reminder. Please do not reply to this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            result = await email_automation_service.send_email(
                to_email=to_email,
                subject=f"Reminder: Your {service_type} Appointment in 1 Hour",
                html_content=html_content,
                text_content=f"Hi {customer_name}, reminder: your {service_type} appointment is in 1 hour at {appointment_time}.",
                user_id=user_id,
                recipient_name=customer_name,
                recipient_phone=customer_phone,
                appointment_id=appointment_id
            )

            if result.get("success"):
                logger.info(f"✅ Reminder email sent to {to_email}")
                # Mark reminder as sent in DB
                db = await get_database()
                await db.reminders.update_one(
                    {"appointment_id": appointment_id, "reminder_type": "email", "sent": False},
                    {"$set": {"sent": True, "sent_at": datetime.utcnow(), "status": "sent"}}
                )
            else:
                logger.error(f"❌ Reminder email failed: {result.get('error')}")

        except asyncio.CancelledError:
            logger.info(f"⏰ Reminder task cancelled for {to_email}")
        except Exception as e:
            logger.error(f"❌ Error sending reminder email: {e}")

    # ============================================
    # EXTRACTION HELPERS (FULLY PRESERVED)
    # ============================================
    
    def _extract_name(self, user_input: str) -> Optional[str]:
        """Extract name ONLY when user explicitly provides it - FIXED VERSION"""
        try:
            user_input_lower = user_input.lower().strip()
            user_input_clean = user_input.strip()
            
            logger.info(f"🔍 Extracting name from: '{user_input_clean}'")
            
            # ✅ CRITICAL: Reject common filler phrases FIRST
            filler_phrases = [
                "i mean", "you know", "like i said", "well um", "uh well",
                "um", "uh", "like", "so", "well", "actually", "basically",
                "literally", "obviously", "wait", "sorry", "hold on"
            ]
            # Check if entire input is just a filler phrase
            if user_input_lower in filler_phrases:
                logger.info(f"⚠️ Filler phrase detected: '{user_input_lower}' - NOT a name")
                return None
            
            # Check if input STARTS with filler phrase
            for filler in filler_phrases:
                if user_input_lower.startswith(filler + " ") or user_input_lower.startswith(filler + ","):
                    logger.info(f"⚠️ Starts with filler '{filler}' - NOT a name")
                    return None
            
            # ✅ NEVER extract name from these patterns (booking requests)
            never_extract_patterns = [
                "book", "appointment", "schedule", "want to", "i want", 
                "okay", "ok", "yes", "sure", "please", "can you", "could you",
                "help", "need", "looking", "interested", "i need", "i'd like",
                "i would", "looking for", "trying to", "let me", "let's"
            ]
            
            # If the message starts with any of these, it's NOT a name
            for pattern in never_extract_patterns:
                if user_input_lower.startswith(pattern):
                    logger.info(f"⚠️ Starts with '{pattern}', not a name")
                    return None
            
            # ✅ NEVER extract name if user is asking a question
            if "?" in user_input or any(q in user_input_lower for q in [
                "what", "how", "why", "can you", "do you", "is there", 
                "discount", "price", "service", "tell me", "about", "when",
                "where", "which", "who"
            ]):
                logger.info("⚠️ User asking question, not providing name")
                return None
            
            # ✅ Words that are NEVER names - EXPANDED LIST
            not_names = [
                # Time words
                "tomorrow", "today", "yesterday", "later", "now", "soon", "morning", "afternoon", "evening", "night",
                # Common responses
                "please", "sure", "yes", "no", "ok", "okay", "thanks", "thank", "hello", "hi", "hey", "bye", "goodbye",
                # Booking words  
                "appointment", "book", "schedule", "call", "busy", "service", "serve", "consultation",
                # Business words
                "discount", "price", "help", "want", "need", "your", "you", "the", "services", "product", "products",
                # Grammar words
                "can", "will", "would", "could", "should", "about", "i", "an", "a", "to", "for", "at", "in", "on", "of",
                # Filler words - CRITICAL
                "mean", "like", "just", "well", "so", "um", "uh", "actually", "basically", "literally", "really",
                # Other common non-names
                "maybe", "perhaps", "probably", "definitely", "absolutely", "certainly"
            ]
            
            # ✅ Check if the ENTIRE input is a non-name word
            if user_input_lower in not_names:
                logger.info(f"⚠️ '{user_input_lower}' is in not_names list")
                return None
            
            # ✅ Check for two-word filler phrases like "i mean"
            words = user_input_lower.split()
            if len(words) == 2:
                # Check common two-word fillers
                two_word_fillers = ["i mean", "you know", "i think", "i guess", "i suppose", "i said"]
                if user_input_lower in two_word_fillers:
                    logger.info(f"⚠️ Two-word filler detected: '{user_input_lower}'")
                    return None
            
            # ✅ Only extract if user explicitly says their name
            import re
            name_patterns = [
                r"(?:my name is|i am|i'm|this is|call me|it's|its|name's)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)",
                r"^([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)$"  # Standalone capitalized name (min 3 chars)
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    name = match.group(1).strip().title()
                    
                    # Validate extracted name - check each word
                    name_words = name.lower().split()
                    
                    # Reject if ANY word is in not_names
                    if any(word in not_names for word in name_words):
                        logger.info(f"⚠️ Extracted '{name}' but contains invalid word")
                        continue
                    
                    # Reject if name is too short (less than 2 chars) or too long
                    if len(name) < 2 or len(name) > 50:
                        logger.info(f"⚠️ Name '{name}' is too short or too long")
                        continue
                    
                    # Reject single character names
                    if len(name_words) == 1 and len(name_words[0]) < 2:
                        logger.info(f"⚠️ Single char name rejected: '{name}'")
                        continue
                    
                    logger.info(f"✅ Name extracted: '{name}'")
                    return name
            
            # ✅ FALLBACK: If no pattern matched but it looks like a standalone name
            # Only accept if it's a clean, capitalized name without filler words
            if len(words) <= 3:  # Max 3 words for a name
                # Check if all words are potentially valid name parts
                potential_name_parts = []
                for word in words:
                    word_clean = re.sub(r'[^\w]', '', word)  # Remove punctuation
                    # Skip if it's a filler/not-name word
                    if word_clean.lower() in not_names:
                        logger.info(f"⚠️ Word '{word_clean}' is not a valid name part")
                        return None
                    if len(word_clean) >= 2:  # Min 2 chars per word
                        potential_name_parts.append(word_clean.title())
                
                if potential_name_parts and len(potential_name_parts) <= 3:
                    final_name = " ".join(potential_name_parts)
                    # Final validation - must be at least 2 characters
                    if len(final_name) >= 2:
                        logger.info(f"✅ Fallback name extracted: '{final_name}'")
                        return final_name
            
            logger.info(f"⚠️ No valid name found in: '{user_input[:50]}'")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting name: {e}")
            return None
    
    
    async def _extract_email_enhanced_ai(self, user_input: str) -> Optional[str]:
        """
        ✅ AI-POWERED: Extract email from voice input using the LLM.
        Handles mishearings like: 'infohamzeda.2@gmail.com' → 'infohamza2@gmail.com'
        Falls back to regex/heuristic if AI fails.
        """
        try:
            user_input_clean = user_input.strip()
            logger.info(f"📧 [EMAIL-AI] Extracting email from: '{user_input_clean}'")

            if not self.openai.configured:
                logger.warning("⚠️ [EMAIL-AI] AI not configured, falling back to regex")
                return self._extract_email_enhanced(user_input)

            prompt = f"""The user is speaking their email address aloud on a phone call.

Raw spoken text: "{user_input_clean}"

Common STT (speech-to-text) mistakes to watch for:
- Extra characters inserted (e.g., "infohamzeda" when they said "infohamza")
- Numbers spoken as words (e.g., "two" -> 2)
- Domain said as separate words (e.g., "gmail dot com" -> gmail.com)
- Confusing letters (e.g., "see" -> c, "are" -> r, "you" -> u, "why" -> y)
- AT said as "at" or "@" or "at the rate"
- Dot said as "dot" or "."

Please extract the EXACT email address the user intended.
If you cannot determine a valid email, reply with NONE.
Reply with ONLY the email address or NONE. No explanation."""

            response = await self.openai.client.chat.completions.create(
                model=self.openai.model,
                messages=[
                    {"role": "system", "content": "You extract email addresses from spoken telephone transcripts. Be precise."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=60,
                temperature=0.1
            )
            result = response.choices[0].message.content.strip().lower()

            if result == "none" or not result:
                logger.warning(f"⚠️ [EMAIL-AI] AI could not extract email from: '{user_input_clean}'")
                return self._extract_email_enhanced(user_input)  # fallback

            # Validate it looks like an email
            import re
            if re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$', result):
                logger.info(f"✅ [EMAIL-AI] Extracted: {result}")
                return result
            else:
                logger.warning(f"⚠️ [EMAIL-AI] AI result not valid email: '{result}', trying fallback")
                return self._extract_email_enhanced(user_input)

        except Exception as e:
            logger.error(f"❌ [EMAIL-AI] Error: {e}")
            return self._extract_email_enhanced(user_input)

    def _extract_email_enhanced(self, user_input: str) -> Optional[str]:
        """Extract email from voice input with spoken format handling (regex fallback)"""
        try:
            user_input_clean = user_input.lower().strip()
            logger.info(f"📧 Extracting email from: '{user_input_clean}'")
            
            # Method 1: Standard email format already present
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            match = re.search(email_pattern, user_input, re.IGNORECASE)
            if match:
                email = match.group(0).lower()
                logger.info(f"✅ Extracted email (standard): {email}")
                return email
            
            # Method 2: Convert spoken format
            converted = user_input_clean
            converted = re.sub(r'\s+at\s+the\s+', '@', converted)
            converted = re.sub(r'\s+at\s+', '@', converted)
            converted = re.sub(r'\s+dot\s+', '.', converted)
            
            match = re.search(email_pattern, converted, re.IGNORECASE)
            if match:
                email = match.group(0).lower()
                logger.info(f"✅ Extracted email (converted): {email}")
                return email
            
            # Method 3: Build from parts
            domain_map = {
                'gmail': 'gmail.com', 'g mail': 'gmail.com', 'gee mail': 'gmail.com',
                'hotmail': 'hotmail.com', 'hot mail': 'hotmail.com',
                'yahoo': 'yahoo.com', 'outlook': 'outlook.com',
                'icloud': 'icloud.com', 'aol': 'aol.com',
            }
            
            domain = None
            for provider, full_domain in domain_map.items():
                if provider in user_input_clean:
                    domain = full_domain
                    break
            
            if not domain:
                domain = "gmail.com"
            
            filler_words = {
                'okay', 'ok', 'my', 'email', 'is', 'the', 'a', 'an', 'uh', 'um',
                'at', 'dot', 'com', 'gmail', 'hotmail', 'yahoo', 'outlook',
                'address', 'its', 'that', 'would', 'be', 'thank', 'you', 'thanks',
                'please', 'and', 'or', 'spell', 'icloud', 'aol', 'g', 'mail', 'hot'
            }
            
            words = re.split(r'[\s,.\?!]+', user_input_clean)
            username_parts = []
            
            for word in words:
                word_clean = word.strip().lower()
                if word_clean and word_clean not in filler_words:
                    if word_clean.isdigit():
                        username_parts.append(word_clean)
                    elif word_clean.isalpha() and len(word_clean) <= 20:
                        username_parts.append(word_clean)
            
            if username_parts:
                username = ''.join(username_parts)
                email = f"{username}@{domain}"
                logger.info(f"✅ Constructed email: {email}")
                return email
            
            logger.warning(f"❌ Could not extract email from: '{user_input_clean}'")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting email: {e}")
            return None

    def _extract_phone_enhanced(self, user_input: str) -> Optional[str]:
        """Extract phone number with spoken format handling"""
        try:
            user_input_clean = user_input.lower().strip()
            logger.info(f"📞 Extracting phone from: '{user_input_clean}'")
            
            # Word to digit mapping
            word_to_digit = {
                'zero': '0', 'oh': '0', 'o': '0',
                'one': '1', 'won': '1',
                'two': '2', 'to': '2', 'too': '2',
                'three': '3', 'tree': '3',
                'four': '4', 'for': '4', 'fore': '4',
                'five': '5', 'fife': '5',
                'six': '6', 'sax': '6',
                'seven': '7',
                'eight': '8', 'ate': '8',
                'nine': '9', 'niner': '9',
            }
            
            # Convert words to digits
            converted = user_input_clean
            for word, digit in word_to_digit.items():
                converted = re.sub(rf'\b{word}\b', digit, converted)
            
            # Extract all digits
            digits = re.sub(r'[^0-9]', '', converted)
            
            if len(digits) >= 10:
                # Format as phone number
                if len(digits) == 10:
                    phone = f"+1{digits}"
                elif len(digits) == 11 and digits.startswith('1'):
                    phone = f"+{digits}"
                else:
                    phone = f"+{digits[:11]}"
                
                logger.info(f"✅ Extracted phone: {phone}")
                return phone
            
            logger.warning(f"❌ Could not extract phone from: '{user_input_clean}'")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting phone: {e}")
            return None

    def _words_to_number(self, text: str) -> str:
        """Convert written-out numbers in text to digits (e.g., 'twenty two' -> '22')"""
        ones = {
            'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
            'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19
        }
        tens = {
            'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50
        }

        words = text.lower().split()
        result = []
        i = 0
        while i < len(words):
            word = words[i].rstrip('.,;:!?')
            if word in tens:
                val = tens[word]
                # Check if next word is a ones number
                if i + 1 < len(words) and words[i + 1].rstrip('.,;:!?') in ones:
                    val += ones[words[i + 1].rstrip('.,;:!?')]
                    i += 1
                result.append(str(val))
            elif word in ones:
                result.append(str(ones[word]))
            else:
                # Handle hyphenated like "twenty-two"
                if '-' in word:
                    parts = word.split('-')
                    if len(parts) == 2 and parts[0] in tens and parts[1] in ones:
                        result.append(str(tens[parts[0]] + ones[parts[1]]))
                    else:
                        result.append(words[i])
                else:
                    result.append(words[i])
            i += 1
        return ' '.join(result)

    def _extract_date(self, user_input: str) -> Optional[datetime]:
        """Extract date from user input — handles both digits and written-out numbers"""
        try:
            user_input_lower = user_input.lower().strip()
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # Convert written numbers to digits (e.g., "twenty two march" -> "22 march")
            user_input_converted = self._words_to_number(user_input_lower)
            logger.info(f"📅 [DATE] Input: '{user_input_lower}' → Converted: '{user_input_converted}'")

            # Relative dates
            if 'today' in user_input_lower:
                return today
            if 'tomorrow' in user_input_lower:
                return today + timedelta(days=1)
            if 'day after tomorrow' in user_input_lower:
                return today + timedelta(days=2)

            # Days of week
            days_of_week = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }

            for day_name, day_num in days_of_week.items():
                if day_name in user_input_lower:
                    days_ahead = day_num - today.weekday()
                    if 'next' in user_input_lower:
                        days_ahead += 7
                    if days_ahead <= 0:
                        days_ahead += 7
                    return today + timedelta(days=days_ahead)

            # Date patterns — try on both original and number-converted text
            date_patterns = [
                (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})', lambda m: datetime(
                    int(m.group(3)) if len(m.group(3)) == 4 else 2000 + int(m.group(3)),
                    int(m.group(1)), int(m.group(2))
                )),
                (r'(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?', self._parse_month_day),
                (r'(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(\w+)(?:\s*,?\s*(\d{4}))?', self._parse_day_month),
            ]

            # Try converted text first (handles "twenty two march" -> "22 march")
            for text_to_try in [user_input_converted, user_input_lower]:
                for pattern, parser in date_patterns:
                    match = re.search(pattern, text_to_try)
                    if match:
                        try:
                            parsed = parser(match)
                            if parsed:
                                return parsed
                        except:
                            continue

            return None

        except Exception as e:
            logger.error(f"Error extracting date: {e}")
            return None

    def _parse_month_day(self, match) -> Optional[datetime]:
        """Parse month day format"""
        months = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
            'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
            'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
}        
        month_str = match.group(1).lower()
        if month_str not in months:
            return None
        
        month = months[month_str]
        day = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else datetime.now().year
        
        return datetime(year, month, day)

    def _parse_day_month(self, match) -> Optional[datetime]:
        """Parse day month format"""
        months = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
            'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
            'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
        }
        
        day = int(match.group(1))
        month_str = match.group(2).lower()
        if month_str not in months:
            return None
        
        month = months[month_str]
        year = int(match.group(3)) if match.group(3) else datetime.now().year
        
        return datetime(year, month, day)

    def _extract_time(self, user_input: str) -> Optional[str]:
        """Extract time from user input - ENHANCED for speed"""
        try:
            import re
            user_input_lower = user_input.lower().strip()
            
            # ✅ ADD: Quick regex patterns for common formats (FAST!)
            # Matches: "10 pm", "2:30 am", "10:00 p.m.", "3pm"
            time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)'
            match = re.search(time_pattern, user_input_lower)
            
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) else 0
                period = match.group(3).replace('.', '').upper()
                
                # Format as "HH:MM AM/PM"
                if period == 'PM' and hour != 12:
                    display_hour = hour
                elif period == 'AM' and hour == 12:
                    display_hour = 12
                else:
                    display_hour = hour
                    
                return f"{display_hour}:{minute:02d} {period}"
            
            # ✅ Handle "o'clock" format
            oclock_pattern = r'(\d{1,2})\s*o\'?clock'
            match = re.search(oclock_pattern, user_input_lower)
            if match:
                hour = int(match.group(1))
                # Assume PM if hour is 1-6, AM if 7-12
                period = "PM" if 1 <= hour <= 6 else "AM"
                return f"{hour}:00 {period}"
            
            # Continue with existing dateparser logic
            # Time patterns (existing code - kept as fallback)
            patterns = [
                (r'(\d{1,2}):(\d{2})\s*(am|pm|a\.m\.|p\.m\.)?', self._format_time_match),
                (r'(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)', self._format_simple_time),
                (r"(\d{1,2})\s*o['\s]?clock", lambda m: f"{int(m.group(1)):d}:00 AM" if int(m.group(1)) < 12 else f"{int(m.group(1)):d}:00 PM"),
            ]
            
            for pattern, formatter in patterns:
                match = re.search(pattern, user_input_lower)
                if match:
                    try:
                        time_str = formatter(match)
                        if time_str:
                            logger.info(f"✅ Extracted time: {time_str}")
                            return time_str
                    except:
                        continue
            
            # Word-based times
            word_times = {
                'noon': '12:00 PM',
                'midnight': '12:00 AM',
                'morning': '9:00 AM',
                'afternoon': '2:00 PM',
                'evening': '6:00 PM',
            }
            
            for word, time_val in word_times.items():
                if word in user_input_lower:
                    return time_val
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting time: {e}")
            return None

    def _format_time_match(self, match) -> str:
        """Format time from regex match"""
        hour = int(match.group(1))
        minute = int(match.group(2))
        period = match.group(3) or ''
        
        if 'p' in period.lower() and hour < 12:
            hour += 12
        elif 'a' in period.lower() and hour == 12:
            hour = 0
        
        if hour >= 12:
            return f"{hour if hour <= 12 else hour - 12}:{minute:02d} PM"
        else:
            return f"{hour if hour > 0 else 12}:{minute:02d} AM"

    def _format_simple_time(self, match) -> str:
        """Format simple time (e.g., '2 pm')"""
        hour = int(match.group(1))
        period = match.group(2).lower()
        
        if 'p' in period:
            return f"{hour}:00 PM"
        else:
            return f"{hour}:00 AM"
        # Create singleton instance
agent_executor = AgentExecutor()











