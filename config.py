import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# Supported Languages
LANGUAGES = {
    "en": {
        "name": "English",
        "code": "en-IN",
        "flag": "🇬🇧"
    },
    "hi": {
        "name": "हिन्दी",
        "code": "hi-IN",
        "flag": "🇮🇳"
    },
    "te": {
        "name": "తెలుగు",
        "code": "te-IN",
        "flag": "🇮🇳"
    },
    "ta": {
        "name": "தமிழ்",
        "code": "ta-IN",
        "flag": "🇮🇳"
    },
    "kn": {
        "name": "ಕನ್ನಡ",
        "code": "kn-IN",
        "flag": "🇮🇳"
    }
}

# Bot Conversational States
STATE_LANGUAGE = "STATE_LANGUAGE"
STATE_SECTOR = "STATE_SECTOR"
STATE_QUESTIONNAIRE = "STATE_QUESTIONNAIRE"
STATE_EDIT_SELECT = "STATE_EDIT_SELECT"
STATE_EDIT_FIELD = "STATE_EDIT_FIELD"
STATE_CONFIRM_PROFILE = "STATE_CONFIRM_PROFILE"
STATE_SCHEMES_LIST = "STATE_SCHEMES_LIST"
STATE_SCHEME_DETAIL = "STATE_SCHEME_DETAIL"

# Sector-specific Questions Mapping
SECTOR_QUESTIONS = {
    "Education & Learning": ["occupation", "age", "annual_income", "education", "social_category", "state"],
    "Agriculture, Rural & Environment": ["occupation", "age", "annual_income", "state"],
    "Agriculture,Rural & Environment": ["occupation", "age", "annual_income", "state"], # support scraper format
    "Health & Wellness": ["age", "gender", "annual_income", "state"],
    "Social Welfare & Empowerment": ["age", "gender", "annual_income", "social_category", "state"],
    "Skills & Employment": ["occupation", "age", "education", "state"],
    "Business & Entrepreneurship": ["occupation", "age", "annual_income", "state"],
    "default": ["age", "gender", "occupation", "annual_income", "state"]
}

# Questionnaire Options (Code, DisplayText)
AGE_OPTIONS = [
    ("under_18", "Under 18"),
    ("18_25", "18–25"),
    ("26_35", "26–35"),
    ("36_50", "36–50"),
    ("51_60", "51–60"),
    ("above_60", "Above 60")
]

AGE_RANGES = {
    "under_18": {"min": 0, "max": 17},
    "18_25": {"min": 18, "max": 25},
    "26_35": {"min": 26, "max": 35},
    "36_50": {"min": 36, "max": 50},
    "51_60": {"min": 51, "max": 60},
    "above_60": {"min": 61, "max": 120}
}

OCCUPATION_OPTIONS = [
    ("Farmer", "Farmer 🌾"),
    ("Student", "Student 🎓"),
    ("Employee", "Employee 👨‍💼"),
    ("Business", "Business 💼"),
    ("Worker", "Worker 👷"),
    ("Homemaker", "Homemaker 🏠"),
    ("Retired", "Retired 👴"),
    ("Other", "Other 🔹")
]

GENDER_OPTIONS = [
    ("Male", "Male"),
    ("Female", "Female"),
    ("Other", "Other"),
    ("skip", "Prefer not to say")
]

INCOME_OPTIONS = [
    ("lt_1l", "Below ₹1 Lakh"),
    ("1_2l", "₹1–2 Lakh"),
    ("2_5l", "₹2–5 Lakh"),
    ("5_10l", "₹5–10 Lakh"),
    ("10_20l", "₹10–20 Lakh"),
    ("gt_20l", "Above ₹20 Lakh")
]

INCOME_RANGES = {
    "lt_1l": {"min": 0, "max": 100000},
    "1_2l": {"min": 100000, "max": 200000},
    "2_5l": {"min": 200000, "max": 500000},
    "5_10l": {"min": 500000, "max": 1000000},
    "10_20l": {"min": 1000000, "max": 2000000},
    "gt_20l": {"min": 2000000, "max": 99999999}
}

SOCIAL_CATEGORY_OPTIONS = [
    ("General", "General"),
    ("OBC", "OBC"),
    ("SC", "SC"),
    ("ST", "ST"),
    ("Other", "Other")
]

EDUCATION_OPTIONS = [
    ("School", "School"),
    ("10th", "10th"),
    ("12th", "12th"),
    ("Diploma", "Diploma"),
    ("UG", "Undergraduate"),
    ("PG", "Postgraduate"),
    ("Other", "Other")
]

# Scraper Configuration Parameters
SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", "0.5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
HEADLESS = os.getenv("HEADLESS", "True").lower() == "true"

STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", 
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", 
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", 
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", 
    "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", 
    "Uttarakhand", "West Bengal", "Delhi", "Andaman and Nicobar Islands", 
    "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", "Jammu and Kashmir", 
    "Ladakh", "Lakshadweep", "Puducherry"
]
