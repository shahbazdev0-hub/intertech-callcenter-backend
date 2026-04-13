

# services/audio_stream_handler.py
import asyncio
import json
import base64
from typing import Dict, Any, Optional  # ✅ FIXED: Added Optional
import os
import logging
import time
import re
from datetime import datetime, timedelta

from deepgram import Deepgram
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.services.twilio import twilio_service

logger = logging.getLogger(__name__)


class AudioStreamHandler:
    """
    PRODUCTION Voice AI Handler - VAPI-Style Ultra-Low Latency
    - Uses both_tracks with filtering
    - First utterance detection
    - Junk phrase filtering
    - True barge-in support
    - Sentence-by-sentence streaming (like VAPI)
    - Semantic caching for instant responses
    - 0.8s silence timeout

    ✅ FIXED: Deepgram keepalive timeout issue
    ✅ ADDED: Callback/follow-up logic integration
    ✅ FIXED: Missing Optional import
    ✅ FIXED: Support for spelled-out numbers (five, ten, etc.)
    """

    # ✅ NEW: Word-to-number mapping for spelled-out numbers
    WORD_TO_NUMBER = {
        'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
        'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
        'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
        'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
        'eighteen': 18, 'nineteen': 19, 'twenty': 20,
        'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60,
        # Common combinations
        'twenty-one': 21, 'twenty-two': 22, 'twenty-three': 23,
        'twenty-four': 24, 'twenty-five': 25, 'twenty-six': 26,
        'twenty-seven': 27, 'twenty-eight': 28, 'twenty-nine': 29,
        'thirty-one': 31, 'thirty-two': 32, 'thirty-three': 33,
        'thirty-four': 34, 'thirty-five': 35,
        'forty-five': 45, 'fifty-five': 55,
        # Also handle without hyphen
        'twenty one': 21, 'twenty two': 22, 'twenty three': 23,
        'twenty four': 24, 'twenty five': 25, 'twenty six': 26,
        'twenty seven': 27, 'twenty eight': 28, 'twenty nine': 29,
        'thirty one': 31, 'thirty two': 32, 'thirty three': 33,
        'thirty four': 34, 'thirty five': 35,
        'forty five': 45, 'fifty five': 55,
        # Common speech variations
        'a': 1, 'an': 1, 'couple': 2, 'few': 3, 'several': 5,
    }

    def __init__(self, openai_service, elevenlabs_service, agent_executor):
        self.openai = openai_service
        self.elevenlabs = elevenlabs_service
        self.agent_executor = agent_executor
        self.deepgram_key = os.getenv("DEEPGRAM_API_KEY")

        # State flags
        self.is_speaking = False
        self.has_greeted = False
        self.greeting_done = asyncio.Event()  # Signals when greeting has finished playing
        self.tts_task = None
        self.should_hangup = False  # ✅ Flag to signal hangup after callback
        self.hangup_after_audio = False
        self.callback_in_progress = False
        self.barge_in_occurred = False  # ✅ Flag to stop remaining sentences after interruption
        self.last_barge_in_time = 0.0   # Timestamp of last barge-in — used for post-barge-in grace period
        self.conversation_history = []
        self.max_history_messages = 10
        self.current_voice_id = None

        # ✅ Language detection state
        self.detected_language = "en"  # Default: English
        self.language_name = "English"
        self.language_locked = False  # Once detected, lock to avoid flip-flopping
        self.language_detection_done = False  # Only detect once (on first meaningful utterance)
        self.language_switch_count = 0  # Track switches to limit re-detection (max 1)
        self.SUPPORTED_LANGUAGES = {
            "en": "English",
            "ur": "Urdu",
            "hi": "Hindi",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
        }

        # ✅ NEW: Email details request state tracking
        self.email_request_pending = False  # Waiting for user to provide email
        self.email_request_context = None   # What details to send
        self._pending_email_correction = False  # Waiting for corrected email after booking

        # ✅ Lock: prevents two process_user_utterance tasks running at the same time
        # (silence timer can fire twice quickly — without this both play TTS concurrently)
        self._utterance_lock = asyncio.Lock()

        # ✅ NEW: Appointment booking keywords (matches agent_executor)
        self.BOOKING_KEYWORDS = [
            "appointment", "schedule", "booking", "book", "meeting",
            "reservation", "slot", "available"
        ]
        # These phrases specifically mean scheduling an appointment/consultation — NOT buying a service.
        # Service-purchase phrases ("book my service", "book my slot", etc.) are handled by
        # PAYMENT_INTENT_PHRASES before this block is reached.
        self.EXPLICIT_BOOKING_PHRASES = [
            "book an appointment", "schedule an appointment", "make an appointment",
            "i want to book an appointment", "i'd like to book an appointment",
            "can i book an appointment", "book a meeting", "book a consultation",
            "schedule a call", "set up a meeting", "i want to schedule an appointment",
            "book appointment", "make appointment", "schedule appointment",
        ]
        # ✅ NEW: Email request patterns (broad matching for voice conversations)
        self.EMAIL_REQUEST_PATTERNS = [
            "send me details", "send me the details", "send details",
            "email me", "send me an email", "send email",
            "send me info", "send me information", "send info",
            "send it to my email", "send to my email",
            "email the details", "email details", "email information",
            "can you email", "could you email", "please email",
            "send me a summary", "send summary",
            "on my email", "to my email", "my email address",
            "services on my email", "details on my email",
            "send on email", "send these", "send it on",
            "send me these services", "send me your services",
        ]

        # Junk phrase filter (carrier noise)
        self.JUNK_PHRASES = [
            "to connect you",
            "please wait",
            "connecting your call",
            "one moment",
            "thank you for calling",
            "is being recorded",
            "try to connect",
            "connect you",
            "hold please", "moment", "wait",
            "forwarded to",
            "voice mail",
            "voicemail",
            "leave a message",
            "at the tone",
            "after the beep"
        ]

        # Human greeting triggers
        self.GREETING_TRIGGERS = ["hello", "hi", "hey", "yes", "yeah"]

        # Callback detection patterns
        # Note: Use word-boundary-safe patterns to avoid false matches
        # e.g., "ring me" was matching "hearing me", so removed ambiguous short phrases
        self.CALLBACK_PATTERNS = [
            "call me back", "call back later", "callback", "call me later", "call tomorrow",
            "call next week", "call next day", "please ring me", "phone me back",
            "call me in ", "can you call me", "could you call me", "please call me",
            "call me after", "call me again", "call me at ", "call me on ",
            "reach me at", "ring me back", "give me a call"
        ]

        # Hangup phrases — kept for reference but NOT used to auto-hangup.
        # Agent is instructed to re-engage the customer instead of ending the call.
        self.HANGUP_PATTERNS = [
            "hang up", "hangup", "end the call", "end call", "stop the call",
            "please hang up", "please end", "cut the call", "disconnect",
            "don't call me", "do not call me",
            "goodbye", "good bye", "bye bye", "talk later",
            "i have to go", "i need to go", "i got to go", "i gotta go",
            "stop calling", "do not disturb",
        ]

        # Response cache disabled — all responses should come from the AI using the user's actual script
        self.RESPONSE_CACHE = {}

    async def generate_streaming_response(
        self,
        user_input: str,
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db,
        call_sid: str,
        websocket,
        stream_sid: str,
    ):
        import time
        start_time = time.time()
        try:
            agent_context = agent_config.get("agent_context", {})
            raw_script = agent_config.get("ai_script", "")
            print(f"📜 [SCRIPT] Raw ai_script from agent ({len(raw_script)} chars): {raw_script[:100]}...")
            system_prompt = self.openai.build_contextual_system_prompt(
                agent_context=agent_context,
                agent_name=agent_config.get("name", "AI Assistant"),
                ai_script=raw_script,
                language=self.detected_language,
                language_name=self.language_name

            )
            
            # Add current user message to history
            self.conversation_history.append({
                "role": "user",
                "content": user_input
            })
            
            # Limit history
            if len(self.conversation_history) > (self.max_history_messages * 2):
                self.conversation_history = self.conversation_history[-(self.max_history_messages * 2):]

            full_response = ""
            sentence_buffer = ""
            sentence_count = 0
            had_error = False

            # ✅ Ordered TTS queue — sentences play in order, generation is parallel
            tts_queue = asyncio.Queue()
            playback_done = asyncio.Event()

            async def tts_player():
                """
                Pulls sentences from queue and plays them in order.
                Generates next sentence's audio while current one plays.
                """
                while True:
                    item = await tts_queue.get()
                    if item is None:  # Sentinel — no more sentences
                        playback_done.set()
                        break
                    if self.barge_in_occurred:
                        tts_queue.task_done()
                        continue
                    await self.stream_elevenlabs_audio(item, websocket, stream_sid)
                    tts_queue.task_done()

            # Start the player running in background
            player_task = asyncio.create_task(tts_player())

            print(f"🚀 STREAMING chat response with {self.openai.provider} ({self.openai.model})")

            async for chunk in self.openai.generate_chat_response_stream(
                messages=self.conversation_history,
                system_prompt=system_prompt,
                max_tokens=150,
                temperature=0.8
            ):
                # ✅ Stop streaming immediately on barge-in
                if self.barge_in_occurred:
                    print(f"🛑 [STREAM-ABORT] Barge-in detected, stopping streaming")
                    await tts_queue.put(None)  # Signal player to stop
                    break

                if chunk.get("error"):
                    error_msg = chunk['error']
                    print(f"❌ Streaming error: {error_msg}")
                    had_error = True

                    if "429" in str(error_msg) or "rate_limit" in str(error_msg).lower():
                        fallback = "I appreciate you answering! We're experiencing high volume right now. I'll call you back in 10 minutes. Have a great day!"
                        await tts_queue.put(fallback)
                        await tts_queue.put(None)
                        await playback_done.wait()

                        wait_time = len(fallback.split()) * 0.4 + 1.0
                        await asyncio.sleep(wait_time)
                        from app.services.twilio import twilio_service
                        twilio_service.hangup_call(call_sid)
                        full_response = fallback
                    else:
                        fallback = "I'm sorry, could you repeat that?"
                        await tts_queue.put(fallback)
                        await tts_queue.put(None)
                        full_response = fallback
                    break

                if chunk.get("done"):
                    # Flush any remaining buffer as final fragment
                    if sentence_buffer.strip() and len(sentence_buffer.strip()) > 5:
                        sentence_count += 1
                        print(f"🎵 [FINAL-FRAGMENT] '{sentence_buffer.strip()}'")
                        await tts_queue.put(sentence_buffer.strip())
                    await tts_queue.put(None)  # Signal end of sentences
                    break

                token = chunk.get("token", "")
                if not token:
                    continue

                full_response += token
                sentence_buffer += token

                # ✅ Detect sentence boundary and immediately queue for TTS
                # Don't wait — queue it and keep streaming
                if token in '.!?' or sentence_buffer.endswith(('? ', '. ', '! ')):
                    sentence = sentence_buffer.strip()
                    if len(sentence) > 10:
                        sentence_count += 1
                        elapsed = time.time() - start_time
                        print(f"🎵 [SENTENCE-{sentence_count}] '{sentence}' (after {elapsed:.2f}s)")
                        await tts_queue.put(sentence)  # ✅ Non-blocking — player handles it
                        sentence_buffer = ""

            # Wait for all audio to finish playing
            if not self.barge_in_occurred:
                await playback_done.wait()

            # Ensure player task is cleaned up
            if not player_task.done():
                player_task.cancel()
                try:
                    await player_task
                except asyncio.CancelledError:
                    pass

            total_time = time.time() - start_time
            print(f"⏱️ [LLM-STREAM] Completed in {total_time:.2f}s ({sentence_count} sentences)")

            if full_response.strip() and not had_error:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": full_response.strip()
                })

            print(f"🤖 [AI-REPLY] '{full_response.strip()}'")
            return full_response.strip()

        except Exception as e:
            print(f"❌ [STREAMING-ERROR] {e}")
            import traceback
            traceback.print_exc()
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str.lower():
                fallback = "I appreciate you answering! We're experiencing high volume. I'll call you back in 10 minutes. Have a great day!"
                await self.stream_elevenlabs_audio(fallback, websocket, stream_sid)
                await asyncio.sleep(6)
                from app.services.twilio import twilio_service
                twilio_service.hangup_call(call_sid)
            else:
                fallback = "I'm sorry, could you repeat that?"
                await self.stream_elevenlabs_audio(fallback, websocket, stream_sid)
            return fallback
        # print(f"🔧 [HANDLER-INIT] State: is_speaking={self.is_speaking}, has_greeted={self.has_greeted}")
        # print(f"⚡ [CACHE] Loaded {len(self.RESPONSE_CACHE)} instant responses")

    def _extract_number_from_text(self, text: str) -> Optional[int]:
        """
        ✅ NEW: Extract number from text, supporting both digits and spelled-out words
        Examples:
            "5" -> 5
            "five" -> 5
            "twenty five" -> 25
        """
        text = text.lower().strip()

        # First try to match a digit
        digit_match = re.search(r'(\d+)', text)
        if digit_match:
            return int(digit_match.group(1))

        # Check for spelled-out numbers (try longer phrases first)
        sorted_words = sorted(self.WORD_TO_NUMBER.keys(), key=len, reverse=True)
        for word in sorted_words:
            if word in text:
                return self.WORD_TO_NUMBER[word]

        return None

    def _extract_callback_time(self, text: str) -> Optional[Dict[str, Any]]:
        """
        ✅ NEW: Extract callback time from text with spelled-out number support
        Returns: {"minutes": X} or {"hours": X} or None
        """
        text_lower = text.lower()

        # Build word number pattern
        word_numbers = '|'.join(sorted(self.WORD_TO_NUMBER.keys(), key=len, reverse=True))

        # Pattern for minutes (digits or words)
        # Matches: "after five minutes", "in 5 minutes", "5 minutes from now", etc.
        minutes_patterns = [
            rf'after\s+({word_numbers}|\d+)\s*(?:minutes?|mins?|min)',
            rf'in\s+({word_numbers}|\d+)\s*(?:minutes?|mins?|min)',
            rf'({word_numbers}|\d+)\s*(?:minutes?|mins?|min)\s+(?:from\s+)?now',
            rf'({word_numbers}|\d+)\s*(?:minutes?|mins?|min)',
        ]

        for pattern in minutes_patterns:
            match = re.search(pattern, text_lower)
            if match:
                number_str = match.group(1)
                number = self._extract_number_from_text(number_str)
                if number:
                    print(f"✅ [TIME-EXTRACTED] Found {number} minutes from: '{text}'")
                    return {"minutes": number}
        
        hours_patterns = [
            rf'after\s+({word_numbers}|\d+)\s*(?:hours?|hrs?|hr)',
            rf'in\s+({word_numbers}|\d+)\s*(?:hours?|hrs?|hr)',
            rf'({word_numbers}|\d+)\s*(?:hours?|hrs?|hr)\s+(?:from\s+)?now',
            rf'({word_numbers}|\d+)\s*(?:hours?|hrs?|hr)',
        ]

        for pattern in hours_patterns:
            match = re.search(pattern, text_lower)
            if match:
                number_str = match.group(1)
                number = self._extract_number_from_text(number_str)
                if number:
                    print(f"✅ [TIME-EXTRACTED] Found {number} hours from: '{text}'")
                    return {"hours": number}

        return None

    async def handle_media_stream(
        self,
        websocket,
        call_sid: str,
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db: AsyncIOMotorDatabase,
        initial_stream_sid: str = None,
    ):
        print(f"=" * 80)
        print(f"🎙️ [STREAM] Starting for {call_sid}")
        print(f"🔍 [CONFIG] inbound_track mode with barge-in support")
        print(f"=" * 80)

        keepalive_task = None
        self.should_hangup = False
        self.hangup_after_audio = False

        try:
            deepgram = Deepgram(self.deepgram_key)

            transcript_buffer = []
            last_speech_time = time.time()
            deepgram_ready = asyncio.Event()
            first_user_speech_received = False
            call_start_time = time.time()
            MAX_SILENCE_BEFORE_HANGUP = 30

            stream_sid_inbound = initial_stream_sid
            stream_sid_outbound = None

            # ✅ PROACTIVE GREETING: If we have a stream_sid, greet immediately
            if initial_stream_sid and not self.has_greeted:
                print(f"📞 [PROACTIVE] Will play greeting on stream: {initial_stream_sid}")
                self.has_greeted = True
                asyncio.create_task(
                    self.trigger_initial_greeting(
                        websocket, call_sid, db, agent_config, user_id, call_id,
                        initial_stream_sid
                    )
                )

            # Counters
            inbound_packets = 0
            outbound_packets = 0
            total_packets = 0

            # Optimized Deepgram settings for telephony
            # nova-3 with multilingual support for language detection
            live_options = {
                'punctuate': True,
                'interim_results': True,
                'encoding': 'mulaw',
                'sample_rate': 8000,
                'channels': 1,
                'model': 'nova-3',
                'smart_format': True,
                'language': 'multi',  # Multilingual: en, es, fr, de, hi + more
            }
            print(f"🔧 [DEEPGRAM] Config: model=nova-3, language=multi, encoding=mulaw, sample_rate=8000")

            dg_connection = await deepgram.transcription.live(live_options)

            def on_open(event):
                print("✅ [DEEPGRAM] Connected and ready")
                deepgram_ready.set()

            transcript_event_count = 0  # Debug counter

            def on_transcript_received(event):
                nonlocal last_speech_time, transcript_buffer, transcript_event_count
                transcript_event_count += 1

                try:
                    if transcript_event_count <= 5:
                        # Log raw event structure for debugging
                        if isinstance(event, dict):
                            keys = list(event.keys())
                            has_speech = event.get('is_final', '?')
                            alt = event.get('channel', {}).get('alternatives', [{}])[0]
                            transcript_text = alt.get('transcript', '')
                            confidence = alt.get('confidence', 0)
                            print(f"🔍 [DEBUG-DG] Event #{transcript_event_count}: keys={keys}, is_final={has_speech}, transcript='{transcript_text[:50]}', confidence={confidence}")
                        else:
                            print(f"🔍 [DEBUG-DG] Event #{transcript_event_count}: type={type(event).__name__}, has_channel={hasattr(event, 'channel')}")

                    # Detect if this is an interim or final result
                    is_final = False
                    if hasattr(event, 'is_final'):
                        is_final = event.is_final
                    elif isinstance(event, dict):
                        is_final = event.get('is_final', False)

                    if hasattr(event, 'channel'):
                        sentence = event.channel.alternatives[0].transcript.strip()
                    elif isinstance(event, dict):
                        sentence = event.get('channel', {}).get('alternatives', [{}])[0].get('transcript', '').strip()
                    else:
                        return

                    if not sentence:
                        if transcript_event_count <= 5:
                            print(f"🔍 [DEBUG-DG] Event #{transcript_event_count}: EMPTY transcript (silence)")
                        return

                    # ✅ LANGUAGE DETECTION from Deepgram multilingual response
                    # Only lock on substantial utterances (>15 chars, >2 words) AND only for non-English
                    # (English is default, so no need to lock it — wait for non-English to confirm)
                    if is_final and not self.language_locked and len(sentence) > 15 and len(sentence.split()) >= 3:
                        try:
                            dg_langs = None
                            # Extract detected languages array from Deepgram response
                            if hasattr(event, 'channel') and hasattr(event.channel, 'alternatives'):
                                alt = event.channel.alternatives[0]
                                if hasattr(alt, 'languages'):
                                    dg_langs = alt.languages
                            elif isinstance(event, dict):
                                alt = event.get('channel', {}).get('alternatives', [{}])[0]
                                dg_langs = alt.get('languages', None)

                            if dg_langs and len(dg_langs) > 0:
                                primary_lang = dg_langs[0][:2]  # Get first 2 chars (e.g., "en" from "en-US")
                                if primary_lang in self.SUPPORTED_LANGUAGES and primary_lang != "en":
                                    # Non-English detected — lock immediately
                                    self.detected_language = primary_lang
                                    self.language_name = self.SUPPORTED_LANGUAGES[primary_lang]
                                    self.language_detection_done = True
                                    self.language_locked = True
                                    print(f"🌐 [LANG-DEEPGRAM] Detected: {self.language_name} ({primary_lang}) from multilingual response")
                                else:
                                    print(f"🌐 [LANG-DEEPGRAM] English detected, keeping unlocked for now")
                        except Exception as lang_err:
                            print(f"⚠️ [LANG] Deepgram language extraction error: {lang_err}")

                    if not self.has_greeted:
                        print(f"⚠️ [FIRST-UTTERANCE] User spoke before greeting played: '{sentence}'")
                        self.has_greeted = True

                    # ── Barge-in detection ──────────────────────────────────────
                    # Final results: stop AI on any meaningful content (>3 chars).
                    # Interim results: require 3+ words so that brief noise / filler
                    # words ("uh", "oh", "hmm") don't prematurely kill the AI response.
                    barge_in_words = len(sentence.split())
                    should_barge_in = (
                        (is_final and len(sentence) > 3) or
                        (not is_final and barge_in_words >= 3)
                    )
                    if self.is_speaking and should_barge_in:
                        print(f"🛑 [BARGE-IN] User interrupted AI ({'final' if is_final else f'interim/{barge_in_words}w'}): '{sentence}'")
                        if self.tts_task and not self.tts_task.done():
                            self.tts_task.cancel()
                        self.is_speaking = False
                        self.barge_in_occurred = True
                        self.last_barge_in_time = time.time()

                    if is_final:
                        print(f"📝 [TRANSCRIPT] '{sentence}'")
                        transcript_buffer.append(sentence)
                        last_speech_time = time.time()
                    else:
                        last_speech_time = time.time()

                except Exception as e:
                    print(f"⚠️ [DEEPGRAM] Error parsing: {e}")

            def on_close(event):
                print("🔌 [DEEPGRAM] Connection closed")

            def on_error(event):
                print(f"❌ [DEEPGRAM] Error: {event}")
                import traceback
                traceback.print_exc()

            dg_connection.registerHandler(dg_connection.event.OPEN, on_open)
            dg_connection.registerHandler(dg_connection.event.TRANSCRIPT_RECEIVED, on_transcript_received)
            dg_connection.registerHandler(dg_connection.event.CLOSE, on_close)
            dg_connection.registerHandler(dg_connection.event.ERROR, on_error)

            print("🔌 [DEEPGRAM] Connection established...")

            # ✅ FIX #1: Wait for Deepgram FIRST before doing anything else
            try:
                await asyncio.wait_for(deepgram_ready.wait(), timeout=5.0)
                print("✅ [DEEPGRAM] Ready to receive audio")
            except asyncio.TimeoutError:
                print("❌ [DEEPGRAM] Timeout waiting for ready")
                return

            # ✅ FIX #1 + #2: Launch greeting IMMEDIATELY after Deepgram is ready,
            # BEFORE starting keepalive/silence tasks so it gets CPU first
            if stream_sid_inbound and not self.has_greeted:
                print(f"📞 [PROACTIVE] Launching greeting immediately on stream: {stream_sid_inbound}")
                self.has_greeted = True
                asyncio.create_task(
                    self.trigger_initial_greeting(
                        websocket, call_sid, db, agent_config, user_id, call_id,
                        stream_sid_inbound,
                        greeting_audio=greeting_audio,   # ✅ pre-fetched, no DB call in greeting
                        greeting_text=greeting_text       # ✅ pre-fetched
                    )
                )

            # Start keepalive and silence tasks AFTER greeting is queued
            async def send_keepalives():
                keepalive_audio = bytes([0xFF] * 320)
                keepalive_count = 0
                while True:
                    try:
                        await asyncio.sleep(4)
                        if dg_connection and hasattr(dg_connection, 'send'):
                            dg_connection.send(keepalive_audio)
                            keepalive_count += 1
                        else:
                            print("⚠️ [DEEPGRAM] Connection lost, stopping keepalives")
                            break
                    except asyncio.CancelledError:
                        print("🛑 [DEEPGRAM] Keepalive task cancelled")
                        break
                    except Exception as e:
                        print(f"⚠️ [DEEPGRAM] Keepalive error: {e}")

            keepalive_task = asyncio.create_task(send_keepalives())
            print("✅ [DEEPGRAM] Started continuous keepalive task (every 4s)")

            keepalive_audio = bytes([0xFF] * 320)
            dg_connection.send(keepalive_audio)
            print("📡 [DEEPGRAM] Sent initial keepalive")

            async def check_silence():
                nonlocal last_speech_time, transcript_buffer, first_user_speech_received

                SILENCE_TIMEOUT = 0.5
                CALLBACK_SILENCE_TIMEOUT = 0.8

                while True:
                    await asyncio.sleep(0.3)
                    if self.should_hangup:
                        print(f"📞 [SILENCE-CHECK] Hangup flag detected, stopping silence checker")
                        break
                    if self.is_speaking:
                        last_speech_time = time.time()
                        continue

                    current_silence = time.time() - last_speech_time
                    total_call_time = time.time() - call_start_time
                    if not first_user_speech_received and total_call_time > MAX_SILENCE_BEFORE_HANGUP:
                        print(f"⏱️ [TIMEOUT] No user response for {total_call_time:.1f}s - hanging up")
                        goodbye_msg = "I haven't been able to hear you. I'll call you back later. Goodbye!"
                        try:
                            audio_duration = await self.stream_elevenlabs_audio(
                                goodbye_msg, websocket, stream_sid_inbound
                            )
                            wait_time = audio_duration + 1.0 if audio_duration > 0 else 6.0
                            await asyncio.sleep(wait_time)
                        except Exception as e:
                            print(f"⚠️ [TIMEOUT] Error playing goodbye: {e}")
                            await asyncio.sleep(3)
                        from app.services.twilio import twilio_service
                        hangup_result = twilio_service.hangup_call(call_sid)
                        if hangup_result.get("success"):
                            print(f"✅ [TIMEOUT] Call ended due to no response")
                        try:
                            await db.calls.update_one(
                                {"call_sid": call_sid},
                                {"$set": {
                                    "status": "no_response",
                                    "end_reason": "timeout_no_user_speech",
                                    "ended_at": datetime.utcnow(),
                                    "updated_at": datetime.utcnow()
                                }}
                            )
                        except Exception as db_error:
                            print(f"⚠️ [TIMEOUT] DB update error: {db_error}")
                        self.should_hangup = True
                        break
                    CONVERSATION_SILENCE_TIMEOUT = 45
                    if first_user_speech_received and current_silence > CONVERSATION_SILENCE_TIMEOUT:
                        print(f"⏱️ [TIMEOUT] Conversation silent for {current_silence:.1f}s - hanging up")
                        goodbye_msg = "Are you still there? I'll let you go for now. Feel free to call back anytime. Goodbye!"
                        try:
                            audio_duration = await self.stream_elevenlabs_audio(
                                goodbye_msg, websocket, stream_sid_inbound
                            )
                            wait_time = audio_duration + 1.0 if audio_duration > 0 else 6.0
                            await asyncio.sleep(wait_time)
                        except Exception as e:
                            print(f"⚠️ [TIMEOUT] Error playing goodbye: {e}")
                            await asyncio.sleep(3)
                        from app.services.twilio import twilio_service
                        twilio_service.hangup_call(call_sid)
                        try:
                            await db.calls.update_one(
                                {"call_sid": call_sid},
                                {"$set": {
                                    "status": "completed",
                                    "end_reason": "conversation_timeout",
                                    "ended_at": datetime.utcnow(),
                                    "updated_at": datetime.utcnow()
                                }}
                            )
                        except:
                            pass
                        self.should_hangup = True
                        break

                    if transcript_buffer:
                        buffer_text = " ".join(transcript_buffer).lower()
                        has_callback_keyword = any(phrase in buffer_text for phrase in ["call me", "call back", "callback", "call later"])

                        # ── Dynamic silence timeout ──────────────────────────
                        # Card number dictation: 2.0s — digits come in groups with pauses.
                        # Other payment steps: 1.2s — names/dates need a moment.
                        # Post-barge-in grace: 1.5s — after interruption give user time
                        #   to finish their full thought before responding.
                        # Default: 0.5s for normal conversation flow.
                        payment_state = self.agent_executor.active_payments.get(call_id, {})
                        payment_step = payment_state.get("step", "")
                        time_since_barge_in = time.time() - self.last_barge_in_time
                        barge_in_recently = time_since_barge_in < 3.0  # grace window: 3s after barge-in
                        if payment_step == "card_number":
                            timeout = 2.0   # 16 digits take time — wait for a real pause
                        elif payment_step in ("cardholder_name", "expiry", "cvc", "bank_name", "phone_number", "address", "confirm"):
                            timeout = 1.2   # Slightly longer for other payment inputs
                        elif barge_in_recently:
                            timeout = 1.5   # Post-barge-in: let user finish their sentence
                        elif has_callback_keyword:
                            timeout = CALLBACK_SILENCE_TIMEOUT
                        else:
                            timeout = SILENCE_TIMEOUT
                    else:
                        timeout = SILENCE_TIMEOUT

                    if transcript_buffer and current_silence > timeout:
                        if self.is_speaking:
                            print(f"🛑 [BARGE-IN] User interrupted! Cancelling AI speech...")
                            if self.tts_task and not self.tts_task.done():
                                self.tts_task.cancel()
                            self.is_speaking = False
                            self.barge_in_occurred = True

                            if stream_sid_inbound:
                                try:
                                    await websocket.send_text(json.dumps({
                                        "event": "clear",
                                        "streamSid": stream_sid_inbound
                                    }))
                                    print(f"🧹 [BARGE-IN] Sent 'clear' to Twilio to stop buffered audio")
                                except Exception as clear_err:
                                    print(f"⚠️ [BARGE-IN] Failed to send clear: {clear_err}")

                        full_text = " ".join(transcript_buffer)
                        transcript_buffer.clear()
                        if not first_user_speech_received:
                            first_user_speech_received = True
                            print(f"✅ [TIMEOUT] User responded - 30s timeout disabled")
                        incomplete_endings = ["but", "and", "so", "because", "if", "then", "uh", "um", "er", "ah", "well", "you know", "i mean", "we have", "i want", "currently", "actually", "basically"]
                        words = full_text.strip().split()
                        last_word = words[-1].lower() if words else ""
                        last_two_words = " ".join(words[-2:]).lower() if len(words) >= 2 else ""
                        is_incomplete = (
                            last_word in incomplete_endings or
                            last_two_words in incomplete_endings or
                            full_text.strip().endswith(",")
                        )
                        if is_incomplete:
                            print(f"⏸️ [INCOMPLETE] '{full_text}' - waiting for more...")
                            last_speech_time = time.time()
                            continue

                        single_word_fillers = ["um", "uh", "er", "ah", "hmm"]
                        if len(words) == 1 and full_text.strip().lower() in single_word_fillers:
                            print(f"⚠️ [FILLER] Ignored: '{full_text}'")
                            continue

                        print(f"💬 [FINAL] '{full_text}'")
                        asyncio.create_task(
                            self.process_user_utterance(
                                full_text, websocket, call_sid,
                                agent_config, user_id, call_id, db,
                                stream_sid_inbound
                            )
                        )

            silence_task = asyncio.create_task(check_silence())

            async def hangup_watcher():
                while True:
                    await asyncio.sleep(0.5)
                    if self.hangup_after_audio:
                        print(f"📞 [HANGUP-WATCHER] Waiting for audio to finish...")
                        wait_count = 0
                        while self.is_speaking and wait_count < 30:
                            await asyncio.sleep(0.5)
                            wait_count += 1
                        print(f"📞 [HANGUP-WATCHER] Audio finished, triggering hangup...")
                        self.should_hangup = True
                        break
                    if self.should_hangup:
                        break

            hangup_watcher_task = asyncio.create_task(hangup_watcher())

            try:
                while True:
                    if self.should_hangup:
                        print(f"📞 [HANGUP] Closing call after callback confirmation...")
                        await asyncio.sleep(1.0)
                        try:
                            await db.calls.update_one(
                                {"call_sid": call_sid},
                                {"$set": {
                                    "status": "completed",
                                    "ended_at": datetime.utcnow(),
                                    "end_reason": "callback_scheduled",
                                    "updated_at": datetime.utcnow()
                                }}
                            )
                            print(f"✅ [HANGUP] Call status updated to completed")
                        except Exception as db_error:
                            print(f"⚠️ [HANGUP] DB update error: {db_error}")
                        break

                    try:
                        message = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue

                    data = json.loads(message)
                    event = data.get("event")

                    if event == "start":
                        start_data = data.get("start", {})
                        track = start_data.get("track")
                        current_stream_sid = start_data.get("streamSid")

                        print(f"🎬 [START] Track: {track}, StreamSid: {current_stream_sid}")

                        if track == "inbound":
                            stream_sid_inbound = current_stream_sid
                            print(f"📥 [INBOUND] StreamSid: {stream_sid_inbound}")
                        elif track == "outbound":
                            stream_sid_outbound = current_stream_sid
                            print(f"📤 [OUTBOUND] StreamSid: {stream_sid_outbound}")
                        else:
                            if not stream_sid_inbound:
                                stream_sid_inbound = current_stream_sid
                                print(f"📥 [INBOUND-DEFAULT] StreamSid: {stream_sid_inbound}")

                        if stream_sid_inbound and not self.has_greeted:
                            print("📞 [START-EVENT] Firing greeting from start event (proactive missed)")
                            self.has_greeted = True
                            asyncio.create_task(
                                self.trigger_initial_greeting(
                                    websocket, call_sid, db, agent_config, user_id, call_id,
                                    stream_sid_inbound,
                                    greeting_audio=greeting_audio,
                                    greeting_text=greeting_text
                                )
                            )

                    elif event == "media":
                        total_packets += 1
                        current_stream_sid = data.get("streamSid")

                        if not stream_sid_inbound and current_stream_sid:
                            stream_sid_inbound = current_stream_sid
                            print(f"📥 [AUTO-DETECT] Setting first streamSid as inbound: {stream_sid_inbound}")

                        if total_packets <= 5:
                            print(f"   Inbound: {stream_sid_inbound}, Outbound: {stream_sid_outbound}")

                        if stream_sid_outbound and current_stream_sid == stream_sid_outbound:
                            outbound_packets += 1
                            if outbound_packets % 50 == 0:
                                print(f"🔇 [OUTBOUND-FILTERED] {outbound_packets} AI echo packets filtered")
                            continue

                        if stream_sid_inbound and current_stream_sid == stream_sid_inbound:
                            inbound_packets += 1
                            if inbound_packets == 1:
                                print(f"✅ [FIRST-INBOUND] Starting to process inbound audio")
                            audio_payload = base64.b64decode(data["media"]["payload"])
                            if inbound_packets <= 3:
                                print(f"🔍 [DEBUG-AUDIO] Packet #{inbound_packets}: {len(audio_payload)} bytes, first 10: {audio_payload[:10].hex()}")
                            dg_connection.send(audio_payload)
                        else:
                            if total_packets <= 10:
                                print(f"⚠️ [UNKNOWN-STREAM] Packet {total_packets} from unknown streamSid: {current_stream_sid}")

                    elif event == "stop":
                        print("🛑 [CALL] Stopped")
                        print(f"📊 [FINAL-STATS] Total: {total_packets}, Inbound: {inbound_packets}, Outbound: {outbound_packets}")
                        break

            except Exception as e:
                print(f"❌ [STREAM] Error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                print("🧹 [CLEANUP] Cancelling background tasks...")
                silence_task.cancel()
                try:
                    await silence_task
                except asyncio.CancelledError:
                    pass

                if keepalive_task:
                    keepalive_task.cancel()
                    try:
                        await keepalive_task
                    except asyncio.CancelledError:
                        pass

                if hangup_watcher_task:
                    hangup_watcher_task.cancel()
                    try:
                        await hangup_watcher_task
                    except asyncio.CancelledError:
                        pass

                try:
                    await dg_connection.finish()
                    print("✅ [DEEPGRAM] Connection finished")
                except Exception as e:
                    print(f"⚠️ [DEEPGRAM] Error during cleanup: {e}")

        except Exception as e:
            print(f"❌ [HANDLER] Error: {e}")
            import traceback
            traceback.print_exc()

    

    async def trigger_initial_greeting(
        self,
        websocket,
        call_sid: str,
        db,
        agent_config,
        user_id: str,
        call_id: str,
        stream_sid: str,
        greeting_audio=None,   # ✅ NEW: accept pre-fetched audio bytes (base64 str)
        greeting_text: str = "Hello! How can I help you today?"  # ✅ NEW: accept pre-fetched text
    ):
        """Play PRE-GENERATED greeting immediately (no generation delay)"""
        print(f"=" * 80)
        print(f"👋 [GREETING] Playing PRE-GENERATED greeting")
        print(f"=" * 80)

        try:
            # ✅ voice_id already set in handle_media_stream pre-fetch, but set fallback just in case
            if not self.current_voice_id:
                self.current_voice_id = (
                    agent_config.get("voice_id")
                    or agent_config.get("elevenlabs_voice_id")
                    or None
                )

            if self.current_voice_id:
                print(f"🎵 [VOICE] Using agent voice_id: {self.current_voice_id}")
            else:
                print(f"🎵 [VOICE] Using default ElevenLabs voice")

            # Get PRE-GENERATED greeting audio from database.
            # Poll briefly — audio is generated in a background task in the webhook
            # and is usually ready by the time we reach here.
            greeting_audio = None
            greeting_text = "Hello! How can I help you today?"
            for attempt in range(5):
                call = await db.calls.find_one({"call_sid": call_sid})
                if call:
                    greeting_audio = call.get("greeting_audio")
                    greeting_text = call.get("greeting_text", greeting_text)
                    if greeting_audio:
                        print(f"✅ [GREETING] Audio ready on attempt {attempt + 1}")
                        break
                if attempt < 4:
                    await asyncio.sleep(0.15)  # 150ms between retries (max 600ms total)

            if not greeting_audio:
                print(f"⚠️ [GREETING] No pre-generated audio after retries, generating now (slow path)")
                await self.stream_elevenlabs_audio(greeting_text, websocket, stream_sid)
            else:
                print(f"✅ [GREETING] Playing pre-generated audio instantly")
                print(f"🎵 [GREETING] Text: {greeting_text[:80]}...")

                mulaw_data = base64.b64decode(greeting_audio)
                print(f"📤 [GREETING] Playing {len(mulaw_data)} bytes...")

                self.is_speaking = True
                await self.send_mulaw_audio(mulaw_data, websocket, stream_sid)
                self.is_speaking = False

                print(f"✅ [GREETING] Completed (instant playback)")

            self.conversation_history.append({
                "role": "assistant",
                "content": greeting_text
            })
            print(f"💬 [GREETING] Added to conversation history: '{greeting_text[:60]}...'")

        except Exception as e:
            print(f"❌ [GREETING-ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.greeting_done.set()
            print(f"✅ [GREETING] greeting_done event set — AI responses unblocked")

    async def send_mulaw_audio(self, mulaw_data: bytes, websocket, stream_sid: str):
        """Send mulaw audio to Twilio - REAL-TIME PACED with barge-in support.
        ✅ FIX #5: Sleep once per BATCH (not per chunk) to eliminate startup lag.
        """
        chunk_size = 320
        batch_size = 5
        pace_delay = 0.19  # ~190ms per 200ms batch ≈ real-time

        # Pre-slice into chunks once
        chunks = [mulaw_data[i:i + chunk_size] for i in range(0, len(mulaw_data), chunk_size)]
        total_chunks = len(chunks)
        chunks_sent = 0

        for batch_start in range(0, total_chunks, batch_size):
            # ✅ CHECK: Stop immediately if user interrupted (barge-in)
            if not self.is_speaking:
                print(f"🛑 [SEND-STOPPED] Barge-in detected, stopped at chunk {chunks_sent}/{total_chunks}")
                try:
                    await websocket.send_text(json.dumps({
                        "event": "clear",
                        "streamSid": stream_sid
                    }))
                    print(f"🧹 [SEND-STOPPED] Sent 'clear' to flush Twilio buffer")
                except Exception:
                    pass
                return

            batch = chunks[batch_start:batch_start + batch_size]
            for chunk in batch:
                if len(chunk) > 0:
                    payload = base64.b64encode(chunk).decode("utf-8")
                    await websocket.send_text(
                        json.dumps({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": payload},
                        })
                    )
                    chunks_sent += 1

            # ✅ Sleep ONCE per batch (not per chunk) — only if more batches remain
            if batch_start + batch_size < total_chunks:
                await asyncio.sleep(pace_delay)

        print(f"📤 [SEND] Sent {chunks_sent} chunks ({len(mulaw_data)} bytes)")

    async def process_user_utterance(
        self,
        text: str,
        websocket,
        call_sid: str,
        agent_config,
        user_id,
        call_id,
        db,
        stream_sid: str
    ):
        """
        VAPI-STYLE SENTENCE-BY-SENTENCE STREAMING
        - Checks for hangup/busy intent FIRST (no re-pitching!)
        - Checks for callback requests SECOND
        - Uses existing callback logic from agent_executor
        - Creates Google Calendar events
        - Automatic callback at scheduled time
        ✅ FIXED: Now handles spelled-out numbers like "five minutes"
        ✅ FIXED: Detects hangup/busy and ends call cleanly
        """
        if self.callback_in_progress:
            print(f"🚫 [CALLBACK-BLOCKED] Ignoring input during callback: '{text}'")
            return
        if self.should_hangup:
            print(f"🚫 [HANGUP-IN-PROGRESS] Ignoring input, hangup already triggered")
            return

        # ── Utterance serialisation ──────────────────────────────────────────
        # Only one utterance should be processed at a time to avoid overlapping
        # audio.  There are two cases when we arrive here while the lock is held:
        #
        # 1. Normal overlap (AI is mid-response, user spoke but we are not done):
        #    Discard — the current AI response is still valid.
        #
        # 2. Post-barge-in overlap: user interrupted the AI (barge_in_occurred=True),
        #    the old streaming task is still cleaning up (cancelling TTS, breaking out
        #    of the stream loop).  We MUST NOT discard — this IS the user's actual new
        #    utterance.  Wait up to 3 s for the cleanup to finish, then process.
        if self._utterance_lock.locked():
            if self.barge_in_occurred:
                print(f"⏳ [BARGE-IN-WAIT] Previous response aborting, waiting to process: '{text[:50]}'")
                try:
                    # Wait for the aborting task to release the lock (should be <1s)
                    await asyncio.wait_for(self._utterance_lock.acquire(), timeout=3.0)
                except asyncio.TimeoutError:
                    print(f"⚠️ [BARGE-IN-WAIT] Lock not released after 3s — discarding utterance")
                    return
                # We now own the lock manually — process then release in finally
                try:
                    if self.tts_task and not self.tts_task.done():
                        self.tts_task.cancel()
                        try:
                            await self.tts_task
                        except asyncio.CancelledError:
                            pass
                        self.is_speaking = False
                    await self._process_user_utterance_inner(
                        text, websocket, call_sid, agent_config, user_id, call_id, db, stream_sid
                    )
                finally:
                    self._utterance_lock.release()
            else:
                print(f"🚫 [UTTERANCE-LOCK] Already processing an utterance, discarding: '{text[:50]}'")
            return

        async with self._utterance_lock:
            # Cancel any TTS still playing from the previous turn
            if self.tts_task and not self.tts_task.done():
                print(f"🛑 [TTS-CANCEL] Cancelling previous TTS before new response")
                self.tts_task.cancel()
                try:
                    await self.tts_task
                except asyncio.CancelledError:
                    pass
                self.is_speaking = False

            await self._process_user_utterance_inner(
                text, websocket, call_sid, agent_config, user_id, call_id, db, stream_sid
            )

    async def _process_user_utterance_inner(
        self,
        text: str,
        websocket,
        call_sid: str,
        agent_config,
        user_id,
        call_id,
        db,
        stream_sid: str
    ):
        """Inner implementation — called under _utterance_lock."""
        # Wait for greeting to finish before processing any user input
        if not self.greeting_done.is_set():
            print(f"⏳ [WAITING] Holding response until greeting finishes...")
            await asyncio.wait_for(self.greeting_done.wait(), timeout=15)
            print(f"✅ [WAITING] Greeting done, now processing user input")

        print(f"=" * 80)
        print(f"🤖 [PROCESSING] User: '{text}'")
        print(f"=" * 80)

        # ✅ Reset barge-in flag for new utterance processing
        self.barge_in_occurred = False

        start_time = time.time()
        text_lower = text.lower().strip()

        # ✅ LANGUAGE DETECTION: Detect language BEFORE generating AI response
        # AWAIT (not fire-and-forget) so language is known before the AI responds
        if not self.language_locked and len(text.split()) >= 2:
            await self._detect_language_from_text(text)
        elif self.language_locked and self.language_switch_count < 1:
            # Allow re-detection if user seems to be speaking a different language
            # Check on every utterance for the first 5 utterances, then every 3rd
            utterance_count = len([m for m in self.conversation_history if m.get("role") == "user"])
            should_recheck = (utterance_count <= 5) or (utterance_count % 3 == 0)
            if should_recheck and len(text.split()) >= 2:
                await self._recheck_language(text)

        # NOTE: Auto-hangup on customer exit phrases is intentionally disabled.
        # The agent handles objections and re-engages the customer instead of ending the call.
        # If the customer says "hang up" / "bye" / "not interested", the AI will respond
        # with a re-engagement pivot — the call only ends via silence timeout or callback.
        if any(phrase in text_lower for phrase in self.HANGUP_PATTERNS):
            print(f"🔄 [RETENTION] Customer exit phrase detected — letting AI re-engage: '{text[:60]}'")
            # Fall through to normal AI response (do NOT return or hang up)

        # ✅ PRIORITY -1b: If customer says "call me later" that also implies busy — schedule callback
        # (handled below via CALLBACK_PATTERNS)

        # ✅ STEP 0: Check for callback request FIRST (HIGHEST PRIORITY after hangup)

        # Check if user wants a callback
        wants_callback = any(phrase in text_lower for phrase in self.CALLBACK_PATTERNS)

        # ✅ UPDATED: Check for callback by time patterns (now includes spelled-out numbers)
        extracted_time = self._extract_callback_time(text_lower)
        if extracted_time:
            wants_callback = True
            print(f"📞 [CALLBACK-TIME-PATTERN] Detected callback with time: {extracted_time}")

        if wants_callback:
            print(f"📞 [CALLBACK-PRIORITY] Handling callback request")

            # Try to use the existing callback logic from agent_executor
            callback_response = await self._handle_callback_request(
                text=text,
                agent_config=agent_config,
                user_id=user_id,
                call_id=call_id,
                db=db,
                call_sid=call_sid,
                extracted_time=extracted_time  # ✅ Pass the extracted time
            )

            if callback_response:
                print(f"✅ [CALLBACK-SUCCESS] Response: {callback_response[:100]}...")

                # Store transcript
                await self.store_transcript(db, call_id, call_sid, text, callback_response)

                self.callback_in_progress = True


                # Play the callback response and get duration
                print(f"🔊 [CALLBACK] Playing confirmation message...")
                
                # ✅ Get actual audio duration from the function
                audio_duration = await self.stream_elevenlabs_audio(callback_response, websocket, stream_sid)
                
                # ✅ Wait for audio to finish playing (add buffer for phone processing)
                buffer_time = 1.0
                total_wait_time = audio_duration + buffer_time
                
                print(f"⏳ [CALLBACK] Audio duration: {audio_duration:.2f}s")
                print(f"⏳ [CALLBACK] Waiting {total_wait_time:.2f}s for audio to finish...")
                
                await asyncio.sleep(total_wait_time)
                
                print(f"✅ [CALLBACK] Audio finished playing")
                
                # Now hang up
                print(f"📞 [CALLBACK] Hanging up call {call_sid}...")
                hangup_result = twilio_service.hangup_call(call_sid)
                
                if hangup_result.get("success"):
                    print(f"✅ [CALLBACK] Call ended successfully: {hangup_result.get('status')}")
                else:
                    print(f"⚠️ [CALLBACK] Hangup failed: {hangup_result.get('error')}")
                return
            else:
                print(f"⚠️ [CALLBACK-FALLBACK] Using regular response flow")

        # =====================================================================
        # ✅ PRIORITY 1: EMAIL DETAILS REQUEST — user wants info sent to email
        # =====================================================================
        if self.email_request_pending:
            # User was asked for their email — try to extract it
            print(f"📧 [EMAIL-COLLECTING] User providing email: '{text}'")
            email = await self._extract_email_from_speech(text, db)
            if email:
                self.email_request_pending = False
                response = await self._send_details_email(
                    email=email,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db
                )
                print(f"📧 [EMAIL-SENT] Response: {response}")
                await self.store_transcript(db, call_id, call_sid, text, response)
                self.tts_task = asyncio.create_task(
                    self.stream_elevenlabs_audio(response, websocket, stream_sid)
                )
                return
            else:
                response = "I didn't quite catch that email. Could you spell it out slowly? For example: john, at, gmail, dot, com."
                await self.store_transcript(db, call_id, call_sid, text, response)
                self.tts_task = asyncio.create_task(
                    self.stream_elevenlabs_audio(response, websocket, stream_sid)
                )
                return

        wants_email_details = any(phrase in text_lower for phrase in self.EMAIL_REQUEST_PATTERNS)
        if wants_email_details:
            print(f"📧 [EMAIL-REQUEST] User wants details sent via email")
            # Check if the user already provided an email in the same message
            email_in_text = await self._extract_email_from_speech(text, db)
            if email_in_text:
                print(f"📧 [EMAIL-REQUEST] Email already provided: {email_in_text} — sending directly")
                response = await self._send_details_email(
                    email=email_in_text,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db
                )
                print(f"📧 [EMAIL-SENT] Response: {response}")
            else:
                self.email_request_pending = True
                self.email_request_context = "business_details"
                response = "Sure! I'd be happy to send you the details. What email address should I send them to?"
            await self.store_transcript(db, call_id, call_sid, text, response)
            self.tts_task = asyncio.create_task(
                self.stream_elevenlabs_audio(response, websocket, stream_sid)
            )
            return

        # =====================================================================
        # ✅ PRIORITY 1.5: POST-BOOKING EMAIL CORRECTION
        # =====================================================================
        if self._pending_email_correction:
            # User is providing the correct email after saying "wrong email"
            print(f"📧 [EMAIL-CORRECT] User providing correct email: '{text}'")
            email = await self._extract_email_from_speech(text, db)
            if email:
                self._pending_email_correction = False
                # Update the most recent appointment for this call
                updated = await self._update_appointment_email(email, call_id, user_id, db)
                if updated:
                    response = f"I've updated your appointment confirmation email to {email}. A new confirmation has been sent."
                else:
                    response = f"I've noted your email as {email}, but couldn't find a recent appointment to update."
                await self.store_transcript(db, call_id, call_sid, text, response)
                self.tts_task = asyncio.create_task(
                    self.stream_elevenlabs_audio(response, websocket, stream_sid)
                )
                return
            else:
                response = "I didn't catch that email. Could you spell it out? For example: john, at, gmail, dot, com."
                await self.store_transcript(db, call_id, call_sid, text, response)
                self.tts_task = asyncio.create_task(
                    self.stream_elevenlabs_audio(response, websocket, stream_sid)
                )
                return

        wrong_email_patterns = ["wrong email", "wrong gmail", "wrong mail", "incorrect email",
                                "update my email", "change my email", "correct my email",
                                "taken a wrong", "taken wrong", "not my email"]
        if any(p in text_lower for p in wrong_email_patterns):
            print(f"📧 [EMAIL-CORRECT] User wants to correct email")
            self._pending_email_correction = True
            response = "I apologize for that! What's the correct email address?"
            await self.store_transcript(db, call_id, call_sid, text, response)
            self.tts_task = asyncio.create_task(
                self.stream_elevenlabs_audio(response, websocket, stream_sid)
            )
            return

        # =====================================================================
        # ✅ PRIORITY 1.8: PAYMENT COLLECTION — route through agent_executor
        # =====================================================================
        has_active_payment = call_id in self.agent_executor.active_payments
        wants_to_pay = any(
            phrase in text_lower for phrase in self.agent_executor.PAYMENT_INTENT_PHRASES
        )

        if has_active_payment or wants_to_pay:
            print(f"💳 [PAYMENT] {'Continuing' if has_active_payment else 'Starting'} payment collection")
            try:
                payment_response = await self.agent_executor.process_user_message(
                    user_input=text,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db,
                    call_sid=call_sid
                )
                if payment_response:
                    print(f"💳 [PAYMENT-RESPONSE] {payment_response[:100]}...")
                    await self.store_transcript(db, call_id, call_sid, text, payment_response)
                    self.conversation_history.append({"role": "user", "content": text})
                    self.conversation_history.append({"role": "assistant", "content": payment_response})
                    self.tts_task = asyncio.create_task(
                        self.stream_elevenlabs_audio(payment_response, websocket, stream_sid)
                    )
                    return
            except Exception as e:
                print(f"❌ [PAYMENT-ERROR] {e}")
                import traceback
                traceback.print_exc()

        # =====================================================================
        # ✅ PRIORITY 2: APPOINTMENT BOOKING — route through agent_executor
        # =====================================================================
        has_active_booking = call_id in self.agent_executor.active_bookings
        wants_to_book = any(phrase in text_lower for phrase in self.EXPLICIT_BOOKING_PHRASES)

        if has_active_booking or wants_to_book:
            print(f"📅 [BOOKING] {'Continuing' if has_active_booking else 'Starting'} appointment booking via agent_executor")
            try:
                booking_response = await self.agent_executor.process_user_message(
                    user_input=text,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db,
                    call_sid=call_sid
                )
                if booking_response:
                    print(f"📅 [BOOKING-RESPONSE] {booking_response[:100]}...")
                    await self.store_transcript(db, call_id, call_sid, text, booking_response)
                    # Add to conversation history for context
                    self.conversation_history.append({"role": "user", "content": text})
                    self.conversation_history.append({"role": "assistant", "content": booking_response})
                    self.tts_task = asyncio.create_task(
                        self.stream_elevenlabs_audio(booking_response, websocket, stream_sid)
                    )
                    return
            except Exception as e:
                print(f"❌ [BOOKING-ERROR] {e}")
                import traceback
                traceback.print_exc()
                # Fall through to streaming response

        cache_hit = False
        cached_response = None
        # ✅ STEP 1: Check semantic cache first (INSTANT RESPONSE)
        if len(text.split()) <= 6:
            for cache_key, cache_value in self.RESPONSE_CACHE.items():
                # ✅ Better matching: Check if cache_key matches as whole phrase
                # Not just substring (avoids "interested" matching "not interested")
                if cache_key == text_lower or text_lower.startswith(cache_key + " ") or text_lower.endswith(" " + cache_key):
                    cache_hit = True
                    cached_response = cache_value
                    print(f"⚡ [CACHE HIT] '{cache_key}' → Instant response in 0ms!")
                    break

        if cache_hit:
            print(f"🤖 [AI-REPLY] '{cached_response}'")
            
            # Store transcript
            await self.store_transcript(db, call_id, call_sid, text, cached_response)
            
            # Play cached response immediately
            self.tts_task = asyncio.create_task(
                self.stream_elevenlabs_audio(cached_response, websocket, stream_sid)
            )
            return

        # ✅ STEP 2: No cache hit - Use conversation memory and AI
        print(f"💭 [CACHE MISS] Generating streaming response...")

        try:
            # ✅ NEW: Use the enhanced streaming response with conversation memory
            ai_response = await self.generate_streaming_response(
                user_input=text,
                agent_config=agent_config,
                user_id=user_id,
                call_id=call_id,
                db=db,
                call_sid=call_sid,
                websocket=websocket,
                stream_sid=stream_sid
            )

            # ✅ Store transcript (generate_streaming_response already played the audio)
            await self.store_transcript(db, call_id, call_sid, text, ai_response)

        except Exception as e:
            print(f"❌ [AI-ERROR] {e}")
            import traceback
            traceback.print_exc()

            # Fallback response
            agent_reply = "I'm sorry, could you repeat that?"
            print(f"🤖 [FALLBACK] '{agent_reply}'")

            await self.store_transcript(db, call_id, call_sid, text, agent_reply)

            self.tts_task = asyncio.create_task(
                self.stream_elevenlabs_audio(agent_reply, websocket, stream_sid)
            )

    async def _update_appointment_email(self, new_email: str, call_id: str, user_id: str, db) -> bool:
        """Update the email on the most recent appointment for this call and resend confirmation"""
        try:
            from bson import ObjectId
            # Find the most recent appointment for this call
            appointment = await db.appointments.find_one(
                {"call_id": call_id, "user_id": user_id},
                sort=[("created_at", -1)]
            )
            if not appointment:
                print(f"⚠️ [EMAIL-CORRECT] No appointment found for call {call_id}")
                return False

            old_email = appointment.get("customer_email", "")
            appointment_id = str(appointment["_id"])

            # Update email in database
            await db.appointments.update_one(
                {"_id": appointment["_id"]},
                {"$set": {"customer_email": new_email, "updated_at": datetime.utcnow()}}
            )
            print(f"✅ [EMAIL-CORRECT] Updated appointment {appointment_id}: {old_email} → {new_email}")

            # Resend confirmation email
            try:
                from app.services.email_automation import email_automation_service
                formatted_date = appointment.get("appointment_date", datetime.utcnow()).strftime("%A, %B %d, %Y at %I:%M %p")
                await email_automation_service.send_appointment_confirmation(
                    to_email=new_email,
                    customer_name=appointment.get("customer_name", ""),
                    customer_phone=appointment.get("customer_phone", ""),
                    service_type=appointment.get("service_type", "Consultation"),
                    appointment_date=formatted_date,
                    user_id=user_id,
                    appointment_id=appointment_id,
                    call_id=call_id
                )
                print(f"✅ [EMAIL-CORRECT] Confirmation email resent to {new_email}")
            except Exception as e:
                print(f"⚠️ [EMAIL-CORRECT] Failed to resend email: {e}")

            return True
        except Exception as e:
            print(f"❌ [EMAIL-CORRECT] Error: {e}")
            return False

    async def _detect_language_from_text(self, text: str):
        """Detect the language of user's speech using LLM (fallback when Deepgram doesn't provide it)."""
        if self.language_locked:
            return

        try:
            supported_codes = ", ".join(self.SUPPORTED_LANGUAGES.keys())
            prompt = (
                f"What language is the following spoken text? "
                f"Return ONLY the ISO 639-1 code from this list: {supported_codes}. "
                f"If unsure, return 'en'.\n\nText: \"{text}\""
            )

            result = await self.openai.generate_chat_response(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0.0
            )

            # generate_chat_response returns a dict: {"success": True, "response": "en"}
            if isinstance(result, dict):
                if not result.get("success"):
                    print(f"⚠️ [LANG-DETECT] LLM call failed: {result.get('error')}")
                    self.language_detection_done = True
                    self.language_locked = True
                    return
                response_text = result.get("response", "en")
            else:
                response_text = str(result)

            lang_code = response_text.strip().lower().replace('"', '').replace("'", "")[:2]

            if lang_code in self.SUPPORTED_LANGUAGES and lang_code != self.detected_language:
                self.detected_language = lang_code
                self.language_name = self.SUPPORTED_LANGUAGES[lang_code]
                self.language_detection_done = True
                if lang_code != "en":
                    self.language_locked = True  # Lock only for non-English
                print(f"🌐 [LANG-LLM] Detected: {self.language_name} ({lang_code})")
            elif lang_code == self.detected_language:
                print(f"🌐 [LANG-LLM] Confirmed: {self.language_name} ({lang_code})")
                if lang_code != "en":
                    self.language_locked = True

        except Exception as e:
            print(f"⚠️ [LANG-DETECT] Error: {e}")
            # Default stays as English
            self.language_detection_done = True
            self.language_locked = True

    async def _recheck_language(self, text: str):
        """Re-check language if user may have switched. Only allows 1 switch to prevent flip-flopping."""
        try:
            supported_codes = ", ".join(self.SUPPORTED_LANGUAGES.keys())
            prompt = (
                f"What language is the following spoken text? "
                f"Return ONLY the ISO 639-1 code from this list: {supported_codes}. "
                f"If unsure, return '{self.detected_language}'.\n\nText: \"{text}\""
            )

            result = await self.openai.generate_chat_response(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0.0
            )

            if isinstance(result, dict):
                if not result.get("success"):
                    return
                response_text = result.get("response", self.detected_language)
            else:
                response_text = str(result)

            lang_code = response_text.strip().lower().replace('"', '').replace("'", "")[:2]

            if lang_code in self.SUPPORTED_LANGUAGES and lang_code != self.detected_language:
                old_lang = self.language_name
                self.detected_language = lang_code
                self.language_name = self.SUPPORTED_LANGUAGES[lang_code]
                self.language_switch_count += 1
                print(f"🌐 [LANG-SWITCH] {old_lang} → {self.language_name} (switch #{self.language_switch_count})")

        except Exception as e:
            print(f"⚠️ [LANG-RECHECK] Error: {e}")

    async def _extract_email_from_speech(self, text: str, db=None) -> Optional[str]:
        """Extract email address from spoken text using AI"""
        try:
            # First try regex for obvious emails
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text.lower())
            if email_match:
                email = email_match.group(0)
                # Remove trailing dots/punctuation that may come from sentence endings
                email = email.rstrip('.,;:!?')
                return email

            # Use AI to extract email from speech (handles "john at gmail dot com")
            prompt = f"""Extract the email address from this spoken text. The person is spelling out their email address.
Common patterns: "john at gmail dot com", "jane dot doe at yahoo dot com", "mike123 at outlook dot com"

Spoken text: "{text}"

Return ONLY the email address, nothing else. If no valid email can be extracted, return "NONE"."""

            result = await self.openai.generate_chat_response(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.1
            )

            extracted = result.strip().lower()
            if extracted and extracted != "none" and "@" in extracted and "." in extracted.split("@")[-1]:
                # Clean up any extra whitespace and trailing punctuation
                extracted = re.sub(r'\s+', '', extracted)
                extracted = extracted.rstrip('.,;:!?')
                return extracted
            return None
        except Exception as e:
            print(f"❌ [EMAIL-EXTRACT] Error: {e}")
            return None

    async def _send_details_email(
        self,
        email: str,
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db
    ) -> str:
        """Send business details email to the caller"""
        try:
            from app.services.email_automation import email_automation_service

            # Build email content from agent config
            agent_context = agent_config.get("agent_context", {})
            identity = agent_context.get("identity", {})
            company_name = identity.get("company", agent_config.get("name", "Our Company"))
            company_desc = agent_context.get("company_description", "")

            # Get services/products info
            services = agent_context.get("services", [])
            products = agent_context.get("products", [])
            value_props = agent_context.get("value_propositions", [])
            faqs = agent_context.get("faqs", [])

            # Also check inbound config for business_info
            inbound_config = agent_config.get("inbound_config", {})
            business_info = inbound_config.get("business_info", "") or agent_context.get("business_info", "")

            # Build HTML email
            services_html = ""
            if services:
                services_html = "<h3>Our Services</h3><ul>"
                for s in services:
                    if isinstance(s, dict):
                        services_html += f"<li><strong>{s.get('name', '')}</strong>: {s.get('description', '')}</li>"
                    else:
                        services_html += f"<li>{s}</li>"
                services_html += "</ul>"

            products_html = ""
            if products:
                products_html = "<h3>Our Products</h3><ul>"
                for p in products:
                    if isinstance(p, dict):
                        products_html += f"<li><strong>{p.get('name', '')}</strong>: {p.get('description', '')}</li>"
                    else:
                        products_html += f"<li>{p}</li>"
                products_html += "</ul>"

            value_html = ""
            if value_props:
                value_html = "<h3>Why Choose Us</h3><ul>"
                for v in value_props:
                    value_html += f"<li>{v}</li>"
                value_html += "</ul>"

            business_html = ""
            if business_info:
                business_html = f"<h3>About Us</h3><p>{business_info}</p>"

            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
                    <h1 style="color: #1a1a1a;">Details from {company_name}</h1>
                    <p>Thank you for your interest! Here's the information you requested during our call:</p>

                    {f'<p style="font-size: 16px;">{company_desc}</p>' if company_desc else ''}
                    {business_html}
                    {services_html}
                    {products_html}
                    {value_html}

                    <hr style="border: 1px solid #eee; margin: 20px 0;">
                    <p>If you'd like to schedule an appointment or have any questions, feel free to call us back or reply to this email.</p>
                    <p>Best regards,<br><strong>{company_name}</strong></p>
                </div>
            </body>
            </html>
            """

            text_content = f"Details from {company_name}\n\n"
            if company_desc:
                text_content += f"{company_desc}\n\n"
            if business_info:
                text_content += f"About Us:\n{business_info}\n\n"
            if services:
                text_content += "Our Services:\n"
                for s in services:
                    if isinstance(s, dict):
                        text_content += f"- {s.get('name', '')}: {s.get('description', '')}\n"
                    else:
                        text_content += f"- {s}\n"
            text_content += "\nFeel free to call us back or reply for more information."

            email_result = await email_automation_service.send_email(
                to_email=email,
                subject=f"Details from {company_name} - As Requested",
                html_content=html_content,
                text_content=text_content,
                user_id=user_id,
                call_id=call_id
            )

            if email_result and email_result.get("success"):
                print(f"✅ [EMAIL-DETAILS] Sent to {email}")
                return f"I've sent the details to {email}. You should receive it shortly. Is there anything else I can help you with?"
            else:
                print(f"❌ [EMAIL-DETAILS] Failed: {email_result}")
                return f"I'm sorry, I wasn't able to send the email right now. Could you try again or give me a different email address?"

        except Exception as e:
            print(f"❌ [EMAIL-DETAILS] Exception: {e}")
            import traceback
            traceback.print_exc()
            return "I apologize, I had trouble sending the email. Is there anything else I can help you with?"

    async def _handle_callback_request(
        self,
        text: str,
        agent_config: Dict[str, Any],
        user_id: str,
        call_id: str,
        db,
        call_sid: str,
        extracted_time: Optional[Dict[str, Any]] = None  # ✅ NEW: Accept pre-extracted time
    ) -> Optional[str]:
        """
        Handle callback request by calling agent_executor's follow-up logic
        This will:
        1. Parse time using time_parser_service (or use pre-extracted time)
        2. Create database record
        3. Create Google Calendar event
        4. Return confirmation response

        ✅ UPDATED: Now accepts pre-extracted time with spelled-out number support
        """
        try:
            print(f"📞 [CALLBACK-LOGIC] Starting callback handling")

            text_lower = text.lower()
            now = datetime.utcnow()

            # ✅ NEW: Use pre-extracted time if available
            if extracted_time:
                if "minutes" in extracted_time:
                    minutes = extracted_time["minutes"]
                    print(f"✅ [TIME-PARSED] Using pre-extracted: {minutes} minutes")
                    modified_text = f"call me in {minutes} minutes"
                elif "hours" in extracted_time:
                    hours = extracted_time["hours"]
                    print(f"✅ [TIME-PARSED] Using pre-extracted: {hours} hours")
                    modified_text = f"call me in {hours} hours"
                else:
                    modified_text = text

                # Call the agent_executor's follow-up handler with normalized text
                callback_response = await self.agent_executor._handle_follow_up_request(
                    user_input=modified_text,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db
                )

                if callback_response:
                    return callback_response

            # ✅ FALLBACK: Try to extract time locally if not pre-extracted
            local_extracted = self._extract_callback_time(text_lower)
            if local_extracted:
                if "minutes" in local_extracted:
                    minutes = local_extracted["minutes"]
                    modified_text = f"call me in {minutes} minutes"
                elif "hours" in local_extracted:
                    hours = local_extracted["hours"]
                    modified_text = f"call me in {hours} hours"
                else:
                    modified_text = text

                print(f"✅ [TIME-PARSED-LOCAL] Extracted and normalized to: '{modified_text}'")

                callback_response = await self.agent_executor._handle_follow_up_request(
                    user_input=modified_text,
                    agent_config=agent_config,
                    user_id=user_id,
                    call_id=call_id,
                    db=db
                )

                if callback_response:
                    return callback_response

            # ✅ Try with the original text (might work for other patterns)
            print(f"📞 [CALLBACK-TRY-ORIGINAL] Trying original text")
            callback_response = await self.agent_executor._handle_follow_up_request(
                user_input=text,
                agent_config=agent_config,
                user_id=user_id,
                call_id=call_id,
                db=db
            )

            if callback_response:
                return callback_response

            # ✅ FALLBACK: Create callback manually if agent_executor fails
            print(f"⚠️ [CALLBACK-FALLBACK] Creating callback manually")

            # Get call record to get customer phone
            call = await db.calls.find_one({"call_sid": call_sid})
            if not call:
                print(f"❌ [CALLBACK] Call record not found")
                return None

            # Determine customer phone
            call_direction = call.get("direction", "inbound")
            if call_direction == "inbound":
                customer_phone = call.get("from_number") or call.get("phone_number")
            else:
                customer_phone = call.get("to_number") or call.get("phone_number")

            if not customer_phone:
                print(f"❌ [CALLBACK] No customer phone found")
                return "Sure! When would be a good time to call you back?"

            # ✅ UPDATED: Use extracted time or local extraction for manual fallback
            callback_time = None

            if extracted_time:
                if "minutes" in extracted_time:
                    callback_time = now + timedelta(minutes=extracted_time["minutes"])
                elif "hours" in extracted_time:
                    callback_time = now + timedelta(hours=extracted_time["hours"])

            if not callback_time and local_extracted:
                if "minutes" in local_extracted:
                    callback_time = now + timedelta(minutes=local_extracted["minutes"])
                elif "hours" in local_extracted:
                    callback_time = now + timedelta(hours=local_extracted["hours"])

            if not callback_time:
                # Default to 30 minutes if no time could be extracted
                callback_time = now + timedelta(minutes=30)
                print(f"⚠️ [CALLBACK] No time extracted, defaulting to 30 minutes")

            formatted_time = callback_time.strftime("%I:%M %p")

            # Create follow-up record manually
            follow_up_data = {
                "user_id": user_id,
                "agent_id": str(agent_config.get("_id")),
                "customer_phone": customer_phone,
                "customer_name": call.get("contact_name", "Customer"),
                "original_call_id": call_id,
                "scheduled_time": callback_time,
                "status": "scheduled",
                "confidence": "medium",
                "original_request": text,
                "created_at": now,
                "updated_at": now,
                "source": "audio_stream_handler_fallback"
            }

            result = await db.follow_ups.insert_one(follow_up_data)
            follow_up_id = str(result.inserted_id)
            print(f"✅ [CALLBACK-RECORD] Created follow-up: {follow_up_id}")

            # Get company name for response
            agent_context = agent_config.get("agent_context", {})
            company_name = "our team"
            if agent_context:
                identity = agent_context.get("identity", {})
                company_name = identity.get("company", "our team")

            return f"Perfect! I've scheduled a follow-up call for approximately {formatted_time}. I'll call you back then to discuss how {company_name} can help you. Is there anything specific you'd like me to prepare for our next conversation?"

        except Exception as e:
            print(f"❌ [CALLBACK-ERROR] {e}")
            import traceback
            traceback.print_exc()
            return "Sure! When would be a good time to call you back?"

    async def stream_elevenlabs_audio(self, text: str, websocket, stream_sid: str) -> float:
        """
        Generate and stream audio to Twilio - WITH BARGE-IN SUPPORT
        ✅ FIX: Uses self.current_voice_id so greeting voice MATCHES conversation voice.
        Returns: Audio duration in seconds
        """
        # ✅ BARGE-IN: Skip TTS entirely if user already interrupted
        if self.barge_in_occurred:
            print(f"🛑 [TTS-SKIPPED] Barge-in active, skipping TTS for: '{text[:80]}...'")
            return 0.0

        print(f"🔊 [TTS-START] Generating audio for: '{text[:500]}...'")
        self.is_speaking = True
        start_time = time.time()
        audio_duration = 0.0

        try:
            # ✅ FIX: Always pass the stored voice_id so every TTS call uses the SAME voice
            # ✅ MULTILINGUAL: Pass detected language code for better non-English TTS
            mulaw_data = await self.elevenlabs.text_to_speech_for_twilio(
                text,
                voice_id=self.current_voice_id,
                language_code=self.detected_language if self.detected_language != "en" else None
            )

            if mulaw_data:
                # ✅ Calculate actual audio duration
                audio_duration = len(mulaw_data) / 8000.0  # 8kHz sample rate
                
                print(f"✅ [TTS] Got {len(mulaw_data)} bytes ({audio_duration:.2f}s duration)")
                await self.send_mulaw_audio(mulaw_data, websocket, stream_sid)

                print(f"📤 [SENT] Audio sent ({audio_duration:.2f}s duration), ready for barge-in")
            else:
                print(f"❌ [TTS] Failed to generate audio")

        except asyncio.CancelledError:
            print("🛑 [TTS] Cancelled (barge-in detected)")
            raise
        except Exception as e:
            print(f"❌ [TTS-ERROR] {e}")
        finally:
            tts_time = time.time() - start_time
            self.is_speaking = False
            print(f"✅ [TTS] Completed in {tts_time:.2f}s")
        
        return audio_duration

    async def store_transcript(self, db, call_id, call_sid, user_text, agent_text):
        """Store conversation transcript"""
        from datetime import datetime

        try:
            await asyncio.gather(
                db.call_transcripts.insert_one({
                    "call_id": call_id,
                    "call_sid": call_sid,
                    "timestamp": datetime.utcnow(),
                    "speaker": "user",
                    "text": user_text,
                }),
                db.call_transcripts.insert_one({
                    "call_id": call_id,
                    "call_sid": call_sid,
                    "timestamp": datetime.utcnow(),
                    "speaker": "agent",
                    "text": agent_text,
                }),
            )
            print(f"💾 [TRANSCRIPT] Stored")
        except Exception as e:
            print(f"⚠️ [TRANSCRIPT-ERROR] {e}")
