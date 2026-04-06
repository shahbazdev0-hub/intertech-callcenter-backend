# backend/app/services/elevenlabs.py - ✅ COMPLETE & FIXED

import os
import logging
import aiohttp
import aiofiles
import asyncio
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ElevenLabsService:
    """
    ElevenLabs Text-to-Speech Service
    Supports dynamic voice_id per agent
    """
    
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.default_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "kdmDKE6EkgrWrrykO9Qt")
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # Create audio directory
        self.audio_dir = Path("static/audio/generated")
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("🎵 ElevenLabs Service initialized")
        logger.info(f"   API Key: {'✅ Configured' if self.api_key else '❌ Not configured'}")
        logger.info(f"   Default Voice ID: {self.default_voice_id}")
        logger.info(f"   Model: {self.model_id}")

    def is_configured(self) -> bool:
        """Check if ElevenLabs is properly configured"""
        return bool(self.api_key)

    async def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        save_to_file: bool = True
    ) -> Dict:
        """Convert text to speech - OPTIMIZED FOR SPEED"""
        try:
            if not self.is_configured():
                return {
                    "success": False,
                    "error": "ElevenLabs API key not configured"
                }
            
            voice_id = voice_id or self.default_voice_id
            
            url = f"{self.base_url}/text-to-speech/{voice_id}?optimize_streaming_latency=3&output_format=mp3_22050_32"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            # ✅ OPTIMIZED: Use turbo model and optimized settings
            data = {
                "text": text,
                "model_id": "eleven_flash_v2_5",  # Instead of eleven_turbo_v2_5  # ✅ Fastest model        
                "output_format": "mp3_22050_32",
                "voice_settings": {
                    "stability": 0.4,  # ✅ Lower = faster
                    "similarity_boost": 0.7,
                    "style": 0.0,  # ✅ Disable style for speed
                    "use_speaker_boost": False  # ✅ Disable for speed
                }
            }
            
            logger.info(f"🎤 Generating speech for: {text[:50]}...")
            
            # ✅ OPTIMIZED: Added timeout
            timeout = aiohttp.ClientTimeout(total=5, connect=2)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        audio_content = await response.read()
                        
                        if save_to_file:
                            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                            filename = f"speech_{timestamp}.mp3"
                            file_path = self.audio_dir / filename
                            
                            async with aiofiles.open(file_path, 'wb') as f:
                                await f.write(audio_content)
                            
                            logger.info(f"✅ Audio saved: {filename}")
                            
                            return {
                                "success": True,
                                "audio_url": f"/static/audio/generated/{filename}",
                                "file_path": str(file_path)
                            }
                        else:
                            return {
                                "success": True,
                                "audio": audio_content,
                                "content_type": "audio/mpeg"
                            }
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ ElevenLabs API error: {error_text}")
                        return {
                            "success": False,
                            "error": f"ElevenLabs API error: {error_text}"
                        }
                        
        except asyncio.TimeoutError:
            logger.error("❌ ElevenLabs timeout after 8 seconds")
            return {
                "success": False,
                "error": "ElevenLabs timeout"
            }
        except Exception as e:
            logger.error(f"❌ Error in text_to_speech: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def get_available_voices(self) -> List[Dict]:
        """
        Get list of available voices from ElevenLabs API
        
        Returns:
            List of voice dictionaries with id, name, category
        """
        try:
            if not self.is_configured():
                logger.error("❌ ElevenLabs API key not configured")
                return []
            
            url = f"{self.base_url}/voices"
            headers = {
                "Accept": "application/json",
                "xi-api-key": self.api_key
            }
            
            logger.info("🔍 Fetching available voices from ElevenLabs...")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        voices = data.get("voices", [])
                        
                        # Format voices for frontend
                        formatted_voices = []
                        for voice in voices:
                            formatted_voices.append({
                                "voice_id": voice.get("voice_id"),
                                "name": voice.get("name"),
                                "category": voice.get("category", "premade"),
                                "description": voice.get("description", ""),
                                "labels": voice.get("labels", {}),
                                "preview_url": voice.get("preview_url")
                            })
                        
                        logger.info(f"✅ Retrieved {len(formatted_voices)} voices from ElevenLabs")
                        
                        return formatted_voices
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to fetch voices: HTTP {response.status} - {error_text}")
                        return []
                        
        except Exception as e:
            logger.error(f"❌ Error fetching voices: {e}", exc_info=True)
            return []

    async def get_voice_settings(self, voice_id: str) -> Dict:
        """
        Get settings for a specific voice
        
        Args:
            voice_id: ElevenLabs voice ID
            
        Returns:
            Dict with voice settings
        """
        try:
            if not self.is_configured():
                return {
                    "success": False,
                    "error": "ElevenLabs API key not configured"
                }
            
            url = f"{self.base_url}/voices/{voice_id}/settings"
            headers = {
                "Accept": "application/json",
                "xi-api-key": self.api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        settings = await response.json()
                        return {
                            "success": True,
                            "settings": settings
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"Failed to get voice settings: {error_text}"
                        }
                        
        except Exception as e:
            logger.error(f"❌ Error getting voice settings: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def text_to_speech_for_twilio(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Generate speech optimized for Twilio (native ulaw 8kHz)
        Returns raw mulaw audio data ready for Twilio - NO CONVERSION NEEDED
        """
        try:
            voice_id = voice_id or self.default_voice_id
            
            # Request ulaw 8kHz directly - ElevenLabs native format for telephony!
            url = f"{self.base_url}/text-to-speech/{voice_id}?output_format=ulaw_8000"
            shaped_text = self._shape_text_for_naturalness(text)
            
            print(f"🎵 Requesting native ulaw 8kHz audio from ElevenLabs")
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            data = {
                "text": text,
                "model_id": "eleven_flash_v2_5",  # Instead of eleven_turbo_v2_5
                "voice_settings": {
                    "stability": 0.45,
                    "similarity_boost": 0.80,    # ✅ Maintain voice identity
                    "style": 0.10,               # ✅ Flash supports subtle style
                    "use_speaker_boost": True,
                    # "speed": 0.95    # ✅ Clearer in telephony
                },
                "output_format": "ulaw_8000"     # ✅ Native format for Twilio
            }

            # ✅ MULTILINGUAL: Pass language_code for better non-English TTS
            if language_code and language_code != "en":
                data["language_code"] = language_code
                print(f"🌐 [TTS] Language code: {language_code}")
            
            timeout = aiohttp.ClientTimeout(total=4, connect=1.5)
            print(f"🎵 [TTS] Flash model with natural settings")
            print(f"🎵 [TTS] Original: '{text[:50]}...'")
            print(f"🎵 [TTS] Shaped: '{shaped_text[:50]}...'")
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        mulaw_data = await response.read()
                        print(f"✅ Got {len(mulaw_data)} bytes of native ulaw 8kHz (perfect for Twilio!)")
                        return mulaw_data
                    else:
                        error = await response.text()
                        print(f"❌ ElevenLabs error ({response.status}): {error}")
                        return None
                        
        except Exception as e:
            print(f"❌ Error generating Twilio audio: {e}")
            import traceback
            traceback.print_exc()
            return None
        
    def _shape_text_for_naturalness(self, text: str) -> str:
        """
        ✅ TEXT SHAPING: Transform text to sound more natural
        This is the #1 trick for making Flash sound human!
        """
        import re
        
        shaped = text.strip()
        
        # 1. Add comma before common conjunctions if missing
        shaped = re.sub(r'\s+(but|and|so|because|however|though)\s+', r', \1 ', shaped, flags=re.IGNORECASE)
        
        # 2. Add dash for pause effect before key phrases
        pause_triggers = ['actually', 'honestly', 'well', 'you know', 'I mean', 'look']
        for trigger in pause_triggers:
            shaped = re.sub(rf'\b({trigger})\b', r'— \1', shaped, flags=re.IGNORECASE)
        
        # 3. Ensure sentences end with proper punctuation
        if shaped and shaped[-1] not in '.!?':
            # Check if it's a question
            question_starters = ['what', 'how', 'why', 'when', 'where', 'who', 'is', 'are', 'do', 'does', 'can', 'could', 'would', 'will']
            first_word = shaped.split()[0].lower() if shaped.split() else ''
            if first_word in question_starters:
                shaped += '?'
            else:
                shaped += '.'
        
        # 4. Break very long sentences (>100 chars) with natural pauses
        if len(shaped) > 100 and ',' not in shaped and '—' not in shaped:
            # Find a good break point
            words = shaped.split()
            mid = len(words) // 2
            words.insert(mid, '—')
            shaped = ' '.join(words)
        
        # 5. Add subtle filler for very short responses (sounds more human)
        if len(shaped) < 15 and not shaped.startswith(('Yes', 'No', 'Hi', 'Hello', 'Sure', 'Okay')):
            # Don't add filler to greetings or yes/no
            pass  # Keep short responses short
        
        return shaped

    async def stream_audio(self, text: str, voice_id: Optional[str] = None):
        """
        🎵 Stream audio from ElevenLabs in real-time
        Yields audio chunks as they're generated (for Twilio streaming)
        """
        try:
            voice_id = voice_id or self.default_voice_id
            
            # ElevenLabs streaming endpoint
            url = f"{self.base_url}/text-to-speech/{voice_id}/stream?optimize_streaming_latency=3&output_format=mp3_22050_32"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            data = {
                "text": text,
                "model_id": "eleven_flash_v2_5",  # Instead of eleven_turbo_v2_5
                "voice_settings": {
                    "stability": 0.4,
                    "similarity_boost": 0.7,
                    "style": 0.0,
                    "use_speaker_boost": False
                }
            }
            
            timeout = aiohttp.ClientTimeout(total=10, connect=2)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        # Stream chunks as they arrive
                        async for chunk in response.content.iter_chunked(4096):
                            if chunk:
                                yield chunk
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ ElevenLabs streaming error: {error_text}")
                        
        except Exception as e:
            logger.error(f"❌ ElevenLabs streaming error: {e}")


# ============================================
# SINGLETON INSTANCE
# ============================================

elevenlabs_service = ElevenLabsService()
