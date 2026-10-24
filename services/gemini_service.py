import os
import json
import logging
from pydantic import BaseModel
from typing import Optional, List
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

# Initialize GenAI Client
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY is not set. Gemini services will be unavailable.")
    client = None

# Pydantic schemas for structured outputs
class ExtractedProfile(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    annual_income: Optional[int] = None
    state: Optional[str] = None
    social_category: Optional[str] = None
    education: Optional[str] = None

class StructuredEligibility(BaseModel):
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    gender: List[str] = []
    occupation: List[str] = []
    income_max: Optional[int] = None
    state: List[str] = []
    education: List[str] = []
    social_category: List[str] = []

class StateApplicability(BaseModel):
    scope: str  # "central", "state", "multi_state", "unknown"
    states: List[str] = []
    confidence: float
    evidence: str

def extract_profile_fields(text: str, target_field: Optional[str] = None) -> dict:
    """
    Extracts profile fields (age, gender, occupation, annual_income, state, social_category, education)
    from user input text. Map them to standard options where possible.
    """
    if not client:
        return {}

    prompt = f"""
    You are an expert information extraction assistant. Your task is to extract profile details from the user's input text.
    User input: "{text}"
    Target field currently being asked (if any): "{target_field}"

    Instructions:
    - Extract values only if they are clearly present or implied in the user input.
    - For age, return an integer.
    - For annual_income, if user mentions e.g. "1.5 Lakhs" or "150,000", convert to integer 150000.
    - For gender, extract "Male", "Female", or "Other".
    - For occupation, map to one of: "Farmer", "Student", "Employee", "Business", "Worker", "Other".
    - For social_category, map to one of: "General", "OBC", "SC", "ST".
    - For education, map to one of: "School", "Diploma", "UG", "PG".
    - For state, extract the proper name of the Indian State/UT (e.g., "Telangana", "Karnataka", "Tamil Nadu", "Maharashtra").
    - If a value cannot be determined, set it to null.
    """

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractedProfile,
                temperature=0.1
            )
        )
        data = json.loads(response.text)
        # Filter out keys with None values
        return {k: v for k, v in data.items() if v is not None}
    except Exception as e:
        logger.error(f"Error extracting profile from text: {e}")
        return {}

def translate_text(text: str, target_lang_code: str) -> str:
    """
    Translates text to the target language (Hindi, Telugu, Tamil, Kannada) using Gemini.
    If target_lang_code is en-IN or English, returns text as is.
    """
    if not client or not text:
        return text

    if target_lang_code.startswith("en"):
        return text

    lang_map = {
        "hi-IN": "Hindi",
        "te-IN": "Telugu",
        "ta-IN": "Tamil",
        "kn-IN": "Kannada"
    }
    target_lang = lang_map.get(target_lang_code, "Hindi")

    prompt = f"""
    Translate the following text to {target_lang}. Keep the translation natural, clear, and easy to understand for common citizens.
    Preserve any bullet points, numbers, and key terms (like scheme names or official website URLs) in English if appropriate for common usage.
    Do not add extra formatting or conversational prefix/suffix. Return ONLY the translated text.

    Text:
    {text}
    """

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Translation to {target_lang} failed: {e}")
        return text

def summarize_scheme_for_voice(name: str, description: str, target_lang_code: str) -> str:
    """
    Generates a short (1-2 sentences) natural summary of the scheme in the target language for voice TTS.
    """
    if not client:
        return f"Details about {name}."

    lang_map = {
        "en-IN": "English",
        "hi-IN": "Hindi",
        "te-IN": "Telugu",
        "ta-IN": "Tamil",
        "kn-IN": "Kannada"
    }
    target_lang = lang_map.get(target_lang_code, "English")

    prompt = f"""
    Write a very short (max 2 sentences, 30 words) natural-sounding summary of the government scheme '{name}' for a voice note.
    The summary should explain what the scheme is about in simple terms.
    The output must be in {target_lang}. Return ONLY the summary text.

    Scheme Description:
    {description}
    """

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Voice summary generation failed: {e}")
        return f"Details about the scheme {name}."

import time

def parse_eligibility_offline(raw_text: str) -> dict:
    """
    Parses natural language eligibility text into a structured JSON dictionary using Gemini.
    Called offline during scraping. Handles Gemini free-tier rate limits with backoff.
    """
    if not client or not raw_text:
        return {
            "age_min": None,
            "age_max": None,
            "gender": [],
            "occupation": [],
            "income_max": None,
            "state": [],
            "education": [],
            "social_category": []
        }

    prompt = f"""
    You are an expert data parsing assistant. Extract eligibility criteria from the following raw text into a structured JSON object.

    Raw text:
    "{raw_text}"

    Fields description:
    - age_min: integer (minimum age required, or null if none)
    - age_max: integer (maximum age permitted, or null if none)
    - gender: list of strings (e.g. ["Male", "Female"] or empty list if no restriction)
    - occupation: list of strings. Map occupations to: ["Farmer", "Student", "Employee", "Business", "Worker", "Other"]
    - income_max: integer (maximum annual income in INR, or null if none. Translate lakhs e.g. "1.5 Lakhs" or "1,50,000" to 150000)
    - state: list of states/UTs (e.g. ["Telangana", "Andhra Pradesh"] or empty list if nationwide)
    - education: list of strings. Map to: ["School", "Diploma", "UG", "PG"]
    - social_category: list of strings. Map to: ["General", "OBC", "SC", "ST"]

    Return ONLY the structured JSON output matching the schema.
    """

    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StructuredEligibility,
                    temperature=0.1
                )
            )
            return json.loads(response.text)
        except Exception as e:
            err_msg = str(e)
            if "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower() or "429" in err_msg:
                sleep_time = 15 * (attempt + 1)
                logger.warning(f"Gemini API rate limit hit in parse_eligibility_offline. Sleeping for {sleep_time}s... (Attempt {attempt+1}/4)")
                time.sleep(sleep_time)
            else:
                logger.error(f"Offline eligibility parsing failed: {e}")
                break

    return {
        "age_min": None,
        "age_max": None,
        "gender": [],
        "occupation": [],
        "income_max": None,
        "state": [],
        "education": [],
        "social_category": []
    }

def classify_state_applicability(title: str, description: str, eligibility_text: str, breadcrumbs: list, tags: list) -> dict:
    """
    Classifies the geographic applicability of a scheme using Gemini.
    Returns a dict matching the StateApplicability schema.
    Handles Gemini free-tier rate limits with backoff.
    """
    from config import STATES
    if not client:
        return {
            "scope": "unknown",
            "states": [],
            "confidence": 0.0,
            "evidence": "Gemini client is not initialized"
        }

    prompt = f"""
    Analyze the following government scheme to determine its geographic applicability (whether it is a Central/National scheme or a State-specific scheme).
    
    Scheme Title: {title}
    Description: {description[:1500]}
    Eligibility Text: {eligibility_text[:1500]}
    Breadcrumbs: {breadcrumbs}
    Tags: {tags}
    
    Instructions:
    1. Identify if the scheme is "central" (Government of India, nationwide, applicable across all states) or "state" (applicable to one specific state/UT) or "multi_state" (applicable to a specific group of states/UTs).
    2. If it is "state" or "multi_state", identify the exact state(s)/UT(s). Map them strictly to these canonical names: {STATES}.
    3. If applicability is ambiguous or you are not highly confident, set scope to "unknown" and states to an empty list.
    4. Gemini MUST NOT invent state applicability. If there is no clear evidence in the text connecting the scheme to a specific state or Central government, mark it as "unknown".
    
    Return ONLY the structured JSON output matching the schema.
    """

    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StateApplicability,
                    temperature=0.1
                )
            )
            return json.loads(response.text)
        except Exception as e:
            err_msg = str(e)
            if "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower() or "429" in err_msg:
                sleep_time = 15 * (attempt + 1)
                logger.warning(f"Gemini API rate limit hit in classify_state_applicability. Sleeping for {sleep_time}s... (Attempt {attempt+1}/4)")
                time.sleep(sleep_time)
            else:
                logger.error(f"State applicability classification failed: {e}")
                break

    return {
        "scope": "unknown",
        "states": [],
        "confidence": 0.0,
        "evidence": "Retries exhausted due to rate limits"
    }
