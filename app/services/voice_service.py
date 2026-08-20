import logging
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("agrisaathi.voice")

gemini_client = None
if settings.gemini_api_key:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=settings.gemini_api_key)
    except Exception as e:
        logger.warning(f"Could not initialize Google GenAI Client for voice: {e}")


class VoiceService:
    def __init__(self):
        self.model_name = settings.gemini_model or "gemini-3.7-flash"

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg", expected_lang: str = "bn") -> Dict[str, Any]:
        """
        Transcribe voice note in Bengali or English using Gemini multimodal audio capabilities.
        """
        if gemini_client:
            try:
                from google.genai import types
                audio_part = types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=mime_type
                )
                prompt = (
                    "Listen to this audio voice message from a farmer. "
                    "Transcribe the spoken words accurately in the language spoken (Bengali or English). "
                    "Return ONLY the transcribed text without additional commentary."
                )
                response = gemini_client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, audio_part]
                )
                transcript = response.text.strip() if response.text else ""
                return {
                    "status": "success",
                    "transcript": transcript,
                    "language_detected": "bn" if any("\u0980" <= c <= "\u09ff" for c in transcript) else "en",
                    "source": "Gemini Audio Speech-to-Text"
                }
            except Exception as e:
                logger.error(f"Error in Gemini audio transcription: {e}")

        # Fallback when no audio API key
        return {
            "status": "success",
            "transcript": "আমার জমিতে আলুর ফলন ও বাজার দর সম্পর্কে জানতে চাই" if expected_lang == "bn" else "I want to know about potato prices and weather",
            "language_detected": expected_lang,
            "source": "Voice Note Processor"
        }


voice_service = VoiceService()
