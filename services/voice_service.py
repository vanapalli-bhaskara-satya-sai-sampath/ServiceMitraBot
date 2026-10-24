import os
import base64
import time
import logging
import requests
from config import SARVAM_API_KEY

logger = logging.getLogger(__name__)

# Endpoints
TTS_URL = "https://api.sarvam.ai/text-to-speech"
STT_URL = "https://api.sarvam.ai/speech-to-text"

# In-memory cache to store telegram file_ids for sent voice notes
# Key: (language_code, text), Value: telegram_file_id
TTS_CACHE = {}

# Ensure temp directory exists inside workspace
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

def text_to_speech(text: str, language_code: str) -> str:
    """
    Converts text to speech using Sarvam AI TTS (bulbul:v3).
    Saves the decoded audio as an MP3 file in the temp directory.
    Returns the absolute path to the MP3 file, or None if TTS fails.
    """
    if not SARVAM_API_KEY:
        logger.warning("SARVAM_API_KEY is not set. TTS is disabled.")
        return None

    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }

    # Select suitable speaker depending on language code
    # 'shubh' is default and supports multilingual/code-mixed
    payload = {
        "text": text,
        "language_code": language_code,
        "model": "bulbul:v3",
        "pace": 1.0,
        "sample_rate": 24000
    }

    try:
        logger.info(f"Requesting Sarvam TTS for lang {language_code}, text length: {len(text)}")
        response = requests.post(TTS_URL, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if "audios" in data and len(data["audios"]) > 0:
                audio_base64 = data["audios"][0]
                audio_bytes = base64.b64decode(audio_base64)
                
                # Save to a unique temp file
                filename = f"tts_{int(time.time())}_{language_code}.mp3"
                filepath = os.path.join(TEMP_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(audio_bytes)
                logger.info(f"TTS audio saved successfully to {filepath}")
                return filepath
            else:
                logger.error(f"Sarvam TTS did not return audios: {data}")
        else:
            logger.error(f"Sarvam TTS failed with status {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Exception during Sarvam TTS: {e}")

    return None

def speech_to_text(audio_file_path: str) -> str:
    """
    Transcribes audio to text using Sarvam AI STT (saaras:v3).
    Supports WAV, MP3, AAC, FLAC, and OGG formats.
    Returns the transcribed text, or None if transcription fails.
    """
    if not SARVAM_API_KEY:
        logger.warning("SARVAM_API_KEY is not set. STT is disabled.")
        return None

    if not os.path.exists(audio_file_path):
        logger.error(f"Audio file not found for STT: {audio_file_path}")
        return None

    headers = {
        "api-subscription-key": SARVAM_API_KEY
    }

    data = {
        "model": "saaras:v3",
        "mode": "transcribe"
    }

    # Detect content type from extension
    ext = os.path.splitext(audio_file_path)[1].lower()
    mime_type = "audio/wav"
    if ext == ".mp3":
        mime_type = "audio/mp3"
    elif ext == ".ogg":
        mime_type = "audio/ogg"
    elif ext in [".aac", ".m4a"]:
        mime_type = "audio/aac"

    try:
        logger.info(f"Uploading audio file {audio_file_path} for STT transcription...")
        with open(audio_file_path, "rb") as f:
            files = {
                "file": (os.path.basename(audio_file_path), f, mime_type)
            }
            response = requests.post(STT_URL, files=files, data=data, headers=headers, timeout=20)
            
        if response.status_code == 200:
            res_data = response.json()
            transcript = res_data.get("transcript")
            logger.info(f"STT Transcription successful: '{transcript}'")
            return transcript
        else:
            logger.error(f"Sarvam STT failed with status {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Exception during Sarvam STT: {e}")

    return None

def clean_temp_files():
    """
    Deletes all temporary audio files generated.
    """
    try:
        for file in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        logger.info("Temporary audio files cleaned up.")
    except Exception as e:
        logger.error(f"Error cleaning temp files: {e}")
