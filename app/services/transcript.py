# backend/app/services/transcript.py

import os
import tempfile
from typing import Dict, Optional
import aiofiles
import aiohttp


class TranscriptService:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

    async def transcribe_audio(
        self,
        audio_url: str,
        language: str = "en"
    ) -> Dict:
        """Transcribe audio file using OpenAI Whisper"""
        try:
            # Download audio file
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "error": "Failed to download audio"
                        }
                    
                    audio_content = await response.read()
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                temp_file.write(audio_content)
                temp_path = temp_file.name
            
            # Transcribe using OpenAI Whisper
            import openai
            openai.api_key = self.openai_api_key
            
            with open(temp_path, "rb") as audio_file:
                transcript = await openai.Audio.atranscribe(
                    "whisper-1",
                    audio_file,
                    language=language
                )
            
            # Clean up temp file
            os.unlink(temp_path)
            
            return {
                "success": True,
                "transcript": transcript["text"]
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def transcribe_audio_file(
        self,
        file_path: str,
        language: str = "en"
    ) -> Dict:
        """Transcribe audio from local file"""
        try:
            import openai
            openai.api_key = self.openai_api_key
            
            with open(file_path, "rb") as audio_file:
                transcript = await openai.Audio.atranscribe(
                    "whisper-1",
                    audio_file,
                    language=language
                )
            
            return {
                "success": True,
                "transcript": transcript["text"]
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Create singleton instance
transcript_service = TranscriptService()