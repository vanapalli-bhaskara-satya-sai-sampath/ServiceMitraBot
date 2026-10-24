import os
import sys
import json
import logging
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("bot")

# Load configuration and services
from config import (
    TELEGRAM_BOT_TOKEN,
    LANGUAGES,
    STATE_LANGUAGE,
    STATE_SECTOR,
    STATE_QUESTIONNAIRE,
    STATE_EDIT_SELECT,
    STATE_EDIT_FIELD,
    STATE_CONFIRM_PROFILE,
    STATE_SCHEMES_LIST,
    STATE_SCHEME_DETAIL,
    SECTOR_QUESTIONS,
    OCCUPATION_OPTIONS,
    GENDER_OPTIONS,
    INCOME_OPTIONS,
    SOCIAL_CATEGORY_OPTIONS,
    EDUCATION_OPTIONS,
    STATES,
    AGE_OPTIONS,
    GEMINI_MODEL,
)
from utils.session import get_session, reset_session, update_profile
from services.eligibility_service import check_eligibility, find_matching_schemes, is_scheme_applicable_to_state, evaluate_scheme, get_next_missing_field
from services.gemini_service import extract_profile_fields, translate_text, summarize_scheme_for_voice
from services.voice_service import text_to_speech, speech_to_text, TTS_CACHE

# Check and load schemes data
SCHEMES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "schemes.json")
if not os.path.exists(SCHEMES_PATH):
    print("\n" + "="*60)
    print("Scheme data not found. Run:")
    print("python scraper/umang_scraper.py")
    print("="*60 + "\n")
    sys.exit(0)

with open(SCHEMES_PATH, "r", encoding="utf-8") as f:
    raw_data = json.load(f)
    # Check if schemes is formatted inside standard metadata block or plain array
    if isinstance(raw_data, dict) and "schemes" in raw_data:
        ALL_SCHEMES = raw_data["schemes"]
    else:
        ALL_SCHEMES = raw_data

# Ensure temp directory for downloaded/generated audio files
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# Static UI Texts Dictionary for core bot flows
UI_TEXTS = {
    "welcome": {
        "en-IN": "👋 Welcome to ServiceMitra AI\n\nI can help you discover government schemes and understand how to apply.\n\nPlease choose your preferred language.",
        "hi-IN": "👋 ServiceMitra AI में आपका स्वागत है\n\nमैं आपको सरकारी योजनाओं को खोजने और आवेदन करने का तरीका समझने में मदद कर सकता हूँ।\n\nकृपया अपनी पसंदीदा भाषा चुनें।",
        "te-IN": "👋 సర్వీస్ మిత్ర AI కి స్వాగతం\n\nనేను మీకు ప్రభుత్వ పథకాలను కనుగొనడంలో మరియు ఎలా దరఖాస్తు చేయాలో అర్థం చేసుకోవడంలో సహాయపడతాను.\n\nదయచేసి మీ ప్రాధాన్యత భాషను ఎంచుకోండి.",
        "ta-IN": "👋 సర్వీస్మిత్రా AI-కు ఉమ్మై వరవేర్కిరోమ్\n\nఅరసు తిట్టంగళై క్కందరియవుమ్, ఎవ్వాఱు విణ్ణప్పిప్పదు ఎన్బదై ప్புரிందు కొళ్ళవుమ్ నాన్ ఉంగళుక్కు ఉదవ ముడియుమ్.\n\nదయవుசெய்து ఉంగళుక్కు విరుప్పమాన మొళియై త్తేర్ందెడుక్కవుమ్.",
        "kn-IN": "👋 ಸರ್ವಿಸ್ ಮಿತ್ರ AI ಗೆ ಸುಸ್ವಾಗತ\n\nಸರ್ಕಾರಿ ಯೋಜನೆಗಳನ್ನು ಕಂಡುಹಿಡಿಯಲು ಮತ್ತು ಹೇಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಬೇಕು ಎಂಬುದನ್ನು ತಿಳಿಯಲು ನಾನು ನಿಮಗೆ ಸಹಾಯ ಮಾಡುತ್ತೇನೆ.\n\nದಯವಿಟ್ಟು ನಿಮ್ಮ ಆದ್ಯತೆಯ ಭಾಷೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ."
    },
    "choose_sector": {
        "en-IN": "🏛 What would you like to check today?",
        "hi-IN": "🏛 आज आप क्या चेक करना चाहेंगे?",
        "te-IN": "🏛 ఈ రోజు మీరు దేనిని పరిశీలించాలనుకుంటున్నారు?",
        "ta-IN": "🏛 ಇಂದು ನೀವು ಏನನ್ನು ಪರಿಶೀಲಿಸಲು ಬಯಸುತ್ತೀರಿ?",
        "kn-IN": "🏛 ಇಂದು ನೀವು ಏನನ್ನು ಪರಿಶೀಲಿಸಲು ಬಯಸುತ್ತೀರಿ?"
    },
    "question_age": {
        "en-IN": "🔢 Please select your age range:",
        "hi-IN": "🔢 कृपया अपनी आयु सीमा चुनें:",
        "te-IN": "🔢 దయచేసి మీ వయస్సు పరిధిని ఎంచుకోండి:",
        "ta-IN": "🔢 தயவுசெய்து உங்கள் வயது வரம்பைத் தேர்ந்தெடுக்கவும்:",
        "kn-IN": "🔢 ದಯವಿಟ್ಟು ನಿಮ್ಮ ವಯಸ್ಸಿನ ಮಿತಿಯನ್ನು ಆಯ್ಕೆಮಾಡಿ:"
    },
    "question_gender": {
        "en-IN": "👤 Please select your gender:",
        "hi-IN": "👤 कृपया अपना लिंग चुनें:",
        "te-IN": "👤 దయచేసి మీ లింగాన్ని ఎంచుకోండి:",
        "ta-IN": "👤 தயவுசெய்து உங்கள் பாலினத்தைத் தேர்ந்தெடுக்கவும்:",
        "kn-IN": "👤 ದಯವಿಟ್ಟು ನಿಮ್ಮ ಲಿಂಗವನ್ನು ಆಯ್ಕೆಮಾಡಿ:"
    },
    "question_occupation": {
        "en-IN": "💼 Please select your occupation:",
        "hi-IN": "💼 कृपया अपना व्यवसाय चुनें:",
        "te-IN": "💼 దయచేసి మీ వృత్తిని ఎంచుకోండి:",
        "ta-IN": "💼 தயவுசெய்து உங்கள் தொழிலைத் தேர்ந்தெடுக்கவும்:",
        "kn-IN": "💼 ದಯವಿಟ್ಟು ನಿಮ್ಮ ಉದ್ಯೋಗವನ್ನು ಆಯ್ಕೆಮಾಡಿ:"
    },
    "question_annual_income": {
        "en-IN": "💰 Please select your annual income range:",
        "hi-IN": "💰 कृपया अपनी वार्षिक आय सीमा चुनें:",
        "te-IN": "💰 దయచేసి మీ వార్షిక ఆదాయ పరిధిని ఎంచుకోండి:",
        "ta-IN": "💰 தயவுசெய்து உங்கள் ஆண்டு வருமான வரம்பைத் தேர்ந்தெடுக்கவும்:",
        "kn-IN": "💰 ದಯವಿಟ್ಟು ನಿಮ್ಮ ವಾರ್ಷಿಕ ಆದಾಯದ ಮಿತಿಯನ್ನು ಆಯ್ಕೆಮಾಡಿ:"
    },
    "question_state": {
        "en-IN": "📍 Please select your state of residence:",
        "hi-IN": "📍 कृपया अपने निवास का राज्य चुनें:",
        "te-IN": "📍 దయచేసి మీ నివాస రాష్ట్రాన్ని ఎంచుకోండి:",
        "ta-IN": "📍 தயவுசெய்து உங்கள் வசிப்பிட மாநிலத்தைத் தேர்ந்தெடுக்கவும்:",
        "kn-IN": "📍 ದಯವಿಟ್ಟು ನಿಮ್ಮ ವಾಸಸ್ಥಳದ ರಾಜ್ಯವನ್ನು ಆಯ್ಕೆಮಾಡಿ:"
    },
    "question_social_category": {
        "en-IN": "🏷 Please select your social category:",
        "hi-IN": "🏷 कृपया अपनी सामाजिक श्रेणी चुनें:",
        "te-IN": "🏷 దయచేసి మీ సామాజిక వర్గాన్ని ఎంచుకోండి:",
        "ta-IN": "🏷 தயவுசெய்து உங்கள் சமூகப் பிரிவைத் தேர்ந்தெடுக்கவும்:",
        "kn-IN": "🏷 ದಯವಿಟ್ಟು ನಿಮ್ಮ ಸಾಮಾಜಿಕ ವರ್ಗವನ್ನು ಆಯ್ಕೆಮಾಡಿ:"
    },
    "question_education": {
        "en-IN": "🎓 Please select your education level:",
        "hi-IN": "🎓 कृपया अपना शिक्षा स्तर चुनें:",
        "te-IN": "🎓 దయచేసి మీ విద్యా స్థాయిని ఎంచుకోండి:",
        "ta-IN": "🎓 தயவுசெய்து உங்கள் கல்வித் தகுதியைத் தேர்ந்தெடுக்கவும்:",
        "kn-IN": "🎓 ದಯವಿಟ್ಟು ನಿಮ್ಮ ಶಿಕ್ಷಣದ ಮಟ್ಟವನ್ನು ಆಯ್ಕೆಮಾಡಿ:"
    },
    "button_skip": {
        "en-IN": "⏭ Skip", "hi-IN": "⏭ छोड़ें", "te-IN": "⏭ స్కిప్", "ta-IN": "⏭ தவிர்க்கவும்", "kn-IN": "⏭ ಸ್ಕಿಪ್"
    },
    "button_start_over": {
        "en-IN": "🔄 Start Over", "hi-IN": "🔄 फिर से शुरू करें", "te-IN": "🔄 మొదటికి వెళ్ళు", "ta-IN": "🔄 மீண்டும் தொடங்கவும்", "kn-IN": "🔄 ಮೊದಲಿನಿಂದ ಪ್ರಾರಂಭಿಸಿ"
    },
    "button_change_lang": {
        "en-IN": "🌐 Change Language", "hi-IN": "🌐 भाषा बदलें", "te-IN": "🌐 भाषा మార్చండి", "ta-IN": "🌐 மொழியை மாற்றவும்", "kn-IN": "🌐 ಭಾಷೆ ಬದಲಾಯಿಸಿ"
    },
    "button_back_schemes": {
        "en-IN": "⬅ Back to Schemes", "hi-IN": "⬅ योजनाओं पर वापस जाएं", "te-IN": "⬅ పథకాలకు తిరిగి వెళ్ళు", "ta-IN": "⬅ திட்டங்களுக்குத் திரும்புக", "kn-IN": "⬅ ಯೋಜನೆಗಳಿಗೆ ಹಿಂತಿರುಗಿ"
    },
    "button_back_menu": {
        "en-IN": "⬅ Main Menu", "hi-IN": "⬅ मुख्य मेनू", "te-IN": "⬅ ప్రధాన మెనూ", "ta-IN": "⬅ முதன்மை மெனு", "kn-IN": "⬅ ಮುಖ್ಯ ಮೆನು"
    },
    "results_found": {
        "en-IN": "🎉 Great news!\n\nWe found {count} schemes that may be suitable for you.\n\nYour selected state:\n📍 {state_name}\n\nThese include central schemes and schemes applicable to your state.\n\nPlease choose one to view details.",
        "hi-IN": "🎉 खुशखबरी!\n\nहमें {count} योजनाएं मिली हैं जो आपके लिए उपयुक्त हो सकती हैं।\n\nआपका चयनित राज्य:\n📍 {state_name}\n\nविवरण देखने के लिए कृपया एक चुनें।",
        "te-IN": "🎉 శుభవార్త!\n\nమీకు సరిపోయే {count} పథకాలను మేము కనుగోన్నాము.\n\nమీరు ఎంచుకున్న రాష్ట్రం:\n📍 {state_name}\n\nవివరాలను చూడటానికి దయచేసి ఒకదాన్ని ఎంచుకోండి.",
        "ta-IN": "🎉 சிறந்த செய்தி!\n\nஉங்களுக்குப் பொருத்தமான {count} திட்டங்களைக் கண்டறிந்துள்ளோம்.\n\nதேர்ந்தெடுக்கப்பட்ட மாநிலம்:\n📍 {state_name}\n\nவிவரங்களைப் பார்க்க தயவுசெய்து ஒன்றைத் தேர்ந்தெடுக்கவும்.",
        "kn-IN": "🎉 ಉತ್ತಮ ಸುದ್ದಿ!\n\nನಿಮಗೆ ಸೂಕ್ತವಾದ {count} ಯೋಜನೆಗಳನ್ನು ನಾವು ಕಂಡುಕೊಂಡಿದ್ದೇವೆ.\n\nನಿಮ್ಮ ರಾಜ್ಯ:\n📍 {state_name}\n\nವಿವರಗಳನ್ನು ವೀಕ್ಷಿಸಲು ದಯವಿಟ್ಟು ಒಂದನ್ನು ಆಯ್ಕೆಮಾಡಿ."
    },
    "no_results": {
        "en-IN": "😔 Sorry, we couldn't find any matching schemes for your profile. Try changing category or updating your inputs.",
        "hi-IN": "😔 क्षमा करें, हमें आपकी प्रोफ़ाइल के लिए कोई मेल खाने वाली योजना नहीं मिली। श्रेणी बदलने या अपनी प्रविष्टियों को अपडेट करने का प्रयास करें।",
        "te-IN": "😔 క్షమించండి, మీ ప్రొఫైల్‌కు సరిపోయే పథకాలు ఏవీ లభించలేదు. వర్గాన్ని మార్చడానికి లేదా మీ వివరాలను మార్చడానికి ప్రయత్నించండి.",
        "ta-IN": "😔 மன்னிக்கவும், உங்கள் சுயவிவரத்திற்குப் பொருத்தமான திட்டங்கள் எதுவும் கிடைக்கவில்லை. வகையை மாற்ற அல்லது உங்கள் உள்ளீடுகளைப் புதுப்பிக்க முயற்சிக்கவும்.",
        "kn-IN": "😔 ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ಗೆ ಹೊಂದುವ ಯಾವುದೇ ಯೋಜನೆಗಳು ನಮಗೆ ಕಂಡುಬಂದಿಲ್ಲ. ವರ್ಗವನ್ನು ಬದಲಾಯಿಸಲು ಅಥವಾ ನಿಮ್ಮ ಇನ್ ಪುಟ್ ಗಳನ್ನು ನವೀಕರಿಸಲು ಪ್ರಯತ್ನಿಸಿ."
    },
    "scheme_details_prompt": {
        "en-IN": "📋 {name}\n\nWhat would you like to know?",
        "hi-IN": "📋 {name}\n\nआप क्या जानना चाहेंगे?",
        "te-IN": "📋 {name}\n\nమీరు ఏమి తెలుసుకోవాలనుకుంటున్నారు?",
        "ta-IN": "📋 {name}\n\nநீங்கள் என்ன தெரிந்து கொள்ள விரும்புகிறீர்கள்?",
        "kn-IN": "📋 {name}\n\nನೀವು ಏನನ್ನು ತಿಳಿಯಲು ಬಯಸುತ್ತೀರಿ?"
    }
}

PROGRESS_TEMPLATES = {
    "en-IN": "📋 **Eligibility Check**\nQuestion {current} of {total}\n\n{question}",
    "hi-IN": "📋 **पात्रता जाँच**\nप्रश्न {current} का {total}\n\n{question}",
    "te-IN": "📋 **అర్హత తనిఖీ**\nప్రశ్న {current} కి {total}\n\n{question}",
    "ta-IN": "📋 **தகுதி சரிபார்ப்பு**\nகேள்வி {current} இல் {total}\n\n{question}",
    "kn-IN": "📋 **ಅರ್ಹತೆ ಪರಿಶೀಲನೆ**\nಪ್ರಶ್ನೆ {current} ರಲ್ಲಿ {total}\n\n{question}"
}

PROGRESS_VOICE_TEMPLATES = {
    "en-IN": "Question {current} of {total}. {question}",
    "hi-IN": "प्रश्न संख्या {current}. {question}",
    "te-IN": "ప్రశ్న సంఖ్య {current}. {question}",
    "ta-IN": "கேள்வி எண் {current}. {question}",
    "kn-IN": "ಪ್ರಶ್ನೆ ಸಂಖ್ಯೆ {current}. {question}"
}

SELECT_LABELS = {
    "en-IN": "👇 Select an option below:",
    "hi-IN": "👇 नीचे एक विकल्प चुनें:",
    "te-IN": "👇 క్రింది ఎంపికను ఎంచుకోండి:",
    "ta-IN": "👇 கீழே உள்ள ஒரு விருப்பத்தைத் தேர்ந்தெடுக்கவும்:",
    "kn-IN": "👇 ಕೆಳಗಿನ ಆಯ್ಕೆಯನ್ನು ಆರಿಸಿ:"
}

OPTION_LABELS = {
    "en-IN": "👇 Select an action:",
    "hi-IN": "👇 एक विकल्प चुनें:",
    "te-IN": "👇 చర్యను ఎంచుకోండి:",
    "ta-IN": "👇 ஒரு செயலைத் தேர்ந்தெடுக்கவும்:",
    "kn-IN": "👇 ಕ್ರಿಯೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ:"
}

SCHEME_SELECT_LABELS = {
    "en-IN": "👇 Select a scheme to explore:",
    "hi-IN": "👇 अन्वेषण करने के लिए एक योजना चुनें:",
    "te-IN": "👇 అన్వేషించడానికి ఒక పథకాన్ని ఎంచుకోండి:",
    "ta-IN": "👇 ஆராய ஒரு திட்டத்தைத் தேர்ந்தெடுக்கவும்:",
    "kn-IN": "👇 ಅನ್ವೇಷಿಸಲು ಒಂದು ಯೋಜನೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ:"
}

def t(key: str, lang_code: str, **kwargs) -> str:
    """Helper to translate static UI strings or format them."""
    trans = UI_TEXTS.get(key, {}).get(lang_code)
    if not trans:
        trans = UI_TEXTS.get(key, {}).get("en-IN", "")
    return trans.format(**kwargs) if trans else ""

# ----------------------------------------------------------------------
# NEW TEXT-ONLY AND EXPLICIT VOICE SEQUENCE HELPERS
# ----------------------------------------------------------------------

async def send_question(bot, chat_id, question, language, keyboard, session, voice_text=None) -> None:
    """Sends question text and buttons only. Updates session last_voice_text."""
    session["last_voice_text"] = voice_text if voice_text else question
    translated_text = translate_text(question, language)
    await bot.send_message(chat_id=chat_id, text=translated_text)
    
    select_prompt = SELECT_LABELS.get(language, SELECT_LABELS["en-IN"])
    await bot.send_message(chat_id=chat_id, text=select_prompt, reply_markup=keyboard)

async def send_info(bot, chat_id, text, language, session, keyboard=None, voice_text=None) -> None:
    """Sends informational text and buttons only. Updates session last_voice_text."""
    session["last_voice_text"] = voice_text if voice_text else text
    translated_text = translate_text(text, language)
    await bot.send_message(chat_id=chat_id, text=translated_text)
    
    if keyboard:
        action_prompt = OPTION_LABELS.get(language, OPTION_LABELS["en-IN"])
        await bot.send_message(chat_id=chat_id, text=action_prompt, reply_markup=keyboard)

async def send_scheme_list(bot, chat_id, schemes, language, session, page=0) -> None:
    """Sends the paginated lists of schemes (5 per page) as individual cards. Text-only by default."""
    items_per_page = 5
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_schemes = schemes[start_idx:end_idx]
    
    user_state = session["profile"].get("state") or "Selected State"
    
    # Separate into strong and possible matches
    eligible_schemes = []
    possible_schemes = []
    for s in schemes:
        eval_res = evaluate_scheme(s, session["profile"])
        if eval_res["status"] == "eligible":
            eligible_schemes.append(s)
        else:
            possible_schemes.append(s)
            
    if page == 0:
        strong_count = len(eligible_schemes)
        possible_count = len(possible_schemes)
        
        raw_msg = f"🎉 **{translate_text('Matches Found', language)}**:\n\n"
        if strong_count > 0:
            raw_msg += f"✅ **{translate_text('Strong Matches', language)} ({strong_count})**\n"
            for idx, s in enumerate(eligible_schemes[:5]):
                trans_name = translate_text(s["name"], language)
                raw_msg += f"  {idx+1}. {trans_name}\n"
            if strong_count > 5:
                raw_msg += f"  ... and {strong_count - 5} more.\n"
            raw_msg += "\n"
            
        if possible_count > 0:
            raw_msg += f"🟡 **{translate_text('More Information Needed', language)} ({possible_count})**\n"
            for idx, s in enumerate(possible_schemes[:5]):
                trans_name = translate_text(s["name"], language)
                raw_msg += f"  {idx+1}. {trans_name}\n"
            if possible_count > 5:
                raw_msg += f"  ... and {possible_count - 5} more.\n"
            raw_msg += "\n"
            
        raw_msg += f"📍 **{translate_text('Selected State', language)}**: {user_state}\n\n"
        raw_msg += translate_text("Please choose a scheme from the buttons below to explore details.", language)
        
        raw_voice = f"Based on the information you provided, we found {strong_count} strong matches and {possible_count} possible matches that may suit you."
    else:
        raw_msg = f"{translate_text('Eligible schemes', language)} ({translate_text('Page', language)} {page + 1}):"
        raw_voice = raw_msg
        
    session["last_voice_text"] = raw_voice
    
    keyboard = []
    for s in page_schemes:
        eval_res = evaluate_scheme(s, session["profile"])
        tag = "🟢" if eval_res["status"] == "eligible" else "🟡"
        trans_name = translate_text(s["name"], language)
        keyboard.append([InlineKeyboardButton(f"{tag} {trans_name}", callback_data=f"scheme:{s['id']}")])
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"scheme_page:{page - 1}"))
    if end_idx < len(schemes):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"scheme_page:{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)
        
    keyboard.append([InlineKeyboardButton(t("button_back_menu", language), callback_data="action:back_menu")])
    keyboard.append([InlineKeyboardButton(t("button_start_over", language), callback_data="action:start_over")])
    keyboard.append([InlineKeyboardButton(translate_text("🔊 Voice Help", language), callback_data="action:voice_help")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send text directly (already formatted)
    await bot.send_message(chat_id=chat_id, text=raw_msg, parse_mode="Markdown")
    
    select_prompt = SCHEME_SELECT_LABELS.get(language, SCHEME_SELECT_LABELS["en-IN"])
    await bot.send_message(chat_id=chat_id, text=select_prompt, reply_markup=reply_markup)

# Explicit voice note helper (triggered only by [🔊 Voice Help] button click)
async def send_voice_help(bot, chat_id, voice_text, language) -> None:
    """Generates and sends voice help audio note. Uses cache mapping to prevent duplicate API hits."""
    translated_voice = translate_text(voice_text, language)
    cache_key = (language, voice_text)
    
    if cache_key in TTS_CACHE:
        logger.info(f"Reusing cached voice for voice help: '{voice_text[:20]}...'")
        try:
            await bot.send_voice(chat_id=chat_id, voice=TTS_CACHE[cache_key])
            return
        except Exception as ex:
            logger.error(f"Failed to send cached voice help by file_id: {ex}. Re-generating...")
            
    try:
        logger.info(f"Generating voice help in {language} for: '{voice_text[:20]}...'")
        audio_path = await asyncio.to_thread(text_to_speech, translated_voice, language)
        if audio_path and os.path.exists(audio_path):
            with open(audio_path, "rb") as voice_file:
                sent_msg = await bot.send_voice(chat_id=chat_id, voice=voice_file)
                if sent_msg and sent_msg.voice:
                    TTS_CACHE[cache_key] = sent_msg.voice.file_id
            try:
                os.remove(audio_path)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"TTS voice help sending failed: {e}")

# ----------------------------------------------------------------------
# CORE FLOW IMPLEMENTATIONS
# ----------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for the /start command."""
    user_id = update.effective_user.id
    reset_session(user_id)
    
    keyboard = []
    for code, info in LANGUAGES.items():
        keyboard.append([InlineKeyboardButton(f"{info['flag']} {info['name']}", callback_data=f"language:{code}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = t("welcome", "en-IN")
    
    # Language menu is always a new message
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)

async def show_sectors_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict) -> None:
    """Displays the government service sectors dynamically scraped."""
    session["state"] = STATE_SECTOR
    categories_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "categories.json")
    with open(categories_file, "r", encoding="utf-8") as f:
        categories = json.load(f)
        
    keyboard = []
    emojis = {
        "Education & Learning": "🎓",
        "Agriculture, Rural & Environment": "🌾",
        "Agriculture,Rural & Environment": "🌾",
        "Health & Wellness": "🏥",
        "Social Welfare & Empowerment": "🤝",
        "Skills & Employment": "💼",
        "Business & Entrepreneurship": "🚀",
        "Housing & Shelter": "🏠",
        "Banking, Financial Services and Insurance": "🏦",
        "Public Safety, Law & Justice": "⚖️",
        "Science, Technology & IT": "💻",
        "Sports & Culture": "🏆",
        "Transport & Infrastructure": "🚇",
        "Travel & Tourism": "✈️"
    }
    
    for idx, cat in enumerate(categories):
        cat_name = cat["name"] if isinstance(cat, dict) else cat
        emoji = emojis.get(cat_name, "🏛")
        translated_cat = translate_text(cat_name, session["language"])
        btn_text = f"{emoji} {translated_cat}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"category:{idx}")])
        
    keyboard.append([InlineKeyboardButton(t("button_change_lang", session["language"]), callback_data="action:change_language")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    prompt_text = t("choose_sector", session["language"])
    
    voice_text = "Welcome to ServiceMitra. Please select a sector from the menu below to discover eligible schemes."
    await send_info(context.bot, update.effective_chat.id, prompt_text, session["language"], session, keyboard=reply_markup, voice_text=voice_text)

async def ask_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict) -> None:
    """Interactively asks the next missing eligibility question from the sector's queue."""
    session["state"] = STATE_QUESTIONNAIRE
    questions = session["questions_to_ask"]
    
    # Skip already answered fields
    while session["current_question_index"] < len(questions):
        field = questions[session["current_question_index"]]
        if session["profile"].get(field) is not None:
            session["current_question_index"] += 1
        else:
            break
            
    idx = session["current_question_index"]
    if idx >= len(questions):
        await show_profile_summary(update, context, session)
        return
        
    field = questions[idx]
    lang = session["language"]
    
    raw_prompt = t(f"question_{field}", lang)
    
    # Build progress heading
    prog_template = PROGRESS_TEMPLATES.get(lang, PROGRESS_TEMPLATES["en-IN"])
    prompt_text = prog_template.format(current=idx + 1, total=len(questions), question=raw_prompt)
    
    voice_template = PROGRESS_VOICE_TEMPLATES.get(lang, PROGRESS_VOICE_TEMPLATES["en-IN"])
    clean_q_text = raw_prompt.replace("🔢 ", "").replace("👤 ", "").replace("💼 ", "").replace("💰 ", "").replace("📍 ", "").replace("🏷 ", "").replace("🎓 ", "")
    voice_text = voice_template.format(current=idx + 1, total=len(questions), question=clean_q_text)
    
    keyboard = []
    
    if field == "gender":
        for code, name in GENDER_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"gender:{code}")])
    elif field == "occupation":
        for code, name in OCCUPATION_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"occupation:{code}")])
    elif field == "annual_income":
        for code, name in INCOME_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"income:{code}")])
    elif field == "social_category":
        for code, name in SOCIAL_CATEGORY_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"social_category:{code}")])
    elif field == "education":
        for code, name in EDUCATION_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"education:{code}")])
    elif field == "age":
        for code, name in AGE_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"age:{code}")])
    elif field == "state":
        page_num = session.get("state_page", 0)
        items_per_page = 5
        start_idx = page_num * items_per_page
        end_idx = start_idx + items_per_page
        
        page_states = STATES[start_idx:end_idx]
        for s_name in page_states:
            btn_text = translate_text(s_name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"state:{s_name.replace(' ', '_')}")])
            
        nav_row = []
        if page_num > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"state_page:{page_num - 1}"))
        if end_idx < len(STATES):
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"state_page:{page_num + 1}"))
        if nav_row:
            keyboard.append(nav_row)
            
    skip_text = t("button_skip", lang)
    keyboard.append([InlineKeyboardButton(skip_text, callback_data=f"{field}:skip")])
    keyboard.append([InlineKeyboardButton(t("button_start_over", lang), callback_data="action:start_over")])
    keyboard.append([InlineKeyboardButton(translate_text("🔊 Voice Help", lang), callback_data="action:voice_help")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_question(context.bot, update.effective_chat.id, prompt_text, lang, keyboard=reply_markup, session=session, voice_text=voice_text)

async def ask_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict, field: str) -> None:
    """Asks a specific question when the user chooses to modify details."""
    session["state"] = STATE_EDIT_FIELD
    lang = session["language"]
    
    raw_prompt = t(f"question_{field}", lang)
    prompt_text = f"✏️ {translate_text('Edit', lang)}: {raw_prompt}"
    voice_text = raw_prompt
    
    keyboard = []
    
    if field == "gender":
        for code, name in GENDER_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"gender:{code}")])
    elif field == "occupation":
        for code, name in OCCUPATION_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"occupation:{code}")])
    elif field == "annual_income":
        for code, name in INCOME_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"income:{code}")])
    elif field == "social_category":
        for code, name in SOCIAL_CATEGORY_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"social_category:{code}")])
    elif field == "education":
        for code, name in EDUCATION_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"education:{code}")])
    elif field == "age":
        for code, name in AGE_OPTIONS:
            btn_text = translate_text(name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"age:{code}")])
    elif field == "state":
        page_num = session.get("state_page", 0)
        items_per_page = 5
        start_idx = page_num * items_per_page
        end_idx = start_idx + items_per_page
        
        page_states = STATES[start_idx:end_idx]
        for s_name in page_states:
            btn_text = translate_text(s_name, lang)
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"state:{s_name.replace(' ', '_')}")])
            
        nav_row = []
        if page_num > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"state_page:{page_num - 1}"))
        if end_idx < len(STATES):
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"state_page:{page_num + 1}"))
        if nav_row:
            keyboard.append(nav_row)
            
    cancel_text = translate_text("⬅️ Cancel", lang)
    keyboard.append([InlineKeyboardButton(cancel_text, callback_data="action:cancel_edit")])
    keyboard.append([InlineKeyboardButton(translate_text("🔊 Voice Help", lang), callback_data="action:voice_help")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_question(context.bot, update.effective_chat.id, prompt_text, lang, keyboard=reply_markup, session=session, voice_text=voice_text)

async def show_profile_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict) -> None:
    """Displays a summary of user-provided details for verification before matching."""
    session["state"] = STATE_CONFIRM_PROFILE
    lang = session["language"]
    profile = session["profile"]
    
    summary_lines = []
    
    def get_display_val(f_name, val):
        if val is None:
            return translate_text("Not Provided", lang)
        if f_name == "age":
            for code, name in AGE_OPTIONS:
                if code == val:
                    return translate_text(name, lang)
            return str(val)
        if f_name == "gender":
            for code, name in GENDER_OPTIONS:
                if code == val:
                    return translate_text(name, lang)
            return translate_text(val, lang)
        if f_name == "occupation":
            for code, name in OCCUPATION_OPTIONS:
                if code == val:
                    return translate_text(val, lang)
            return translate_text(val, lang)
        if f_name == "annual_income":
            for code, name in INCOME_OPTIONS:
                if code == val:
                    return translate_text(name, lang)
            try:
                num = int(val)
                return f"₹{num:,}"
            except ValueError:
                pass
            return translate_text(str(val), lang)
        if f_name == "education":
            for code, name in EDUCATION_OPTIONS:
                if code == val:
                    return translate_text(name, lang)
            return translate_text(val, lang)
        if f_name == "social_category":
            for code, name in SOCIAL_CATEGORY_OPTIONS:
                if code == val:
                    return translate_text(name, lang)
            return translate_text(val, lang)
        if f_name == "state":
            return translate_text(val, lang)
        return str(val)

    for field in session["questions_to_ask"]:
        label = translate_text(field.replace("_", " ").title(), lang)
        val_display = get_display_val(field, profile.get(field))
        summary_lines.append(f"• **{label}**: {val_display}")
        
    summary_text = f"📋 **{translate_text('Please confirm your details', lang)}**:\n\n" + "\n".join(summary_lines)
    
    keyboard = [
        [InlineKeyboardButton(translate_text("✅ Check Eligible Schemes", lang), callback_data="action:check_schemes")],
        [InlineKeyboardButton(translate_text("✏️ Change Details", lang), callback_data="action:change_details")],
        [InlineKeyboardButton(t("button_start_over", lang), callback_data="action:start_over")],
        [InlineKeyboardButton(translate_text("🔊 Voice Help", lang), callback_data="action:voice_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    voice_txt = translate_text("Please confirm your details. Click Check Eligible Schemes to proceed, or Change Details to modify your answers.", lang)
    await send_info(context.bot, update.effective_chat.id, summary_text, lang, session=session, keyboard=reply_markup, voice_text=voice_txt)

async def show_change_details_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict) -> None:
    """Shows options for editing profile fields."""
    session["state"] = STATE_EDIT_SELECT
    lang = session["language"]
    
    keyboard = []
    row = []
    for field in session["questions_to_ask"]:
        label = translate_text(field.replace("_", " ").title(), lang)
        row.append(InlineKeyboardButton(label, callback_data=f"edit_field:{field}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton(translate_text("⬅️ Back to Summary", lang), callback_data="action:back_summary")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    prompt = translate_text("Which detail would you like to change?", lang)
    await send_info(context.bot, update.effective_chat.id, prompt, lang, session=session, keyboard=reply_markup)

async def ask_dynamic_question(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict, field: str) -> None:
    session["state"] = STATE_QUESTIONNAIRE
    session["dynamic_field"] = field
    lang = session["language"]
    
    dynamic_questions = {
        "single_girl_child": {
            "text": "👧 Are you the only girl child in your family?",
            "options": [("yes", "Yes"), ("no", "No"), ("skip", "Not sure")]
        },
        "disability_percentage": {
            "text": "♿ Do you have any physical disability?",
            "options": [("0", "No"), ("40", "Yes (40% or more)"), ("skip", "Not sure")]
        },
        "widow_status": {
            "text": "👩‍👦 Are you a widow?",
            "options": [("yes", "Yes"), ("no", "No"), ("skip", "Not sure")]
        },
        "bpl_status": {
            "text": "📦 Do you belong to a Below Poverty Line (BPL) household?",
            "options": [("yes", "Yes"), ("no", "No"), ("skip", "Not sure")]
        },
        "land_ownership": {
            "text": "🌾 Do you own agricultural land?",
            "options": [("yes", "Yes"), ("no", "No"), ("skip", "Not sure")]
        },
        "student_year": {
            "text": "🎓 Which year of your course are you currently in?",
            "options": [("1", "1st Year"), ("2", "2nd Year"), ("3", "3rd Year"), ("skip", "Not sure")]
        },
        "course_type": {
            "text": "📚 What type of course are you enrolled in?",
            "options": [("regular", "Regular"), ("distance", "Distance/Part-time"), ("skip", "Not sure")]
        },
        "institution_type": {
            "text": "🏫 What type of institution do you study in?",
            "options": [("government", "Government"), ("private", "Private"), ("skip", "Not sure")]
        },
        "rural_resident": {
            "text": "🏡 Do you reside in a rural area?",
            "options": [("yes", "Yes"), ("no", "No"), ("skip", "Not sure")]
        },
        "domicile": {
            "text": "📍 Do you hold a domicile certificate of your state?",
            "options": [("yes", "Yes"), ("no", "No"), ("skip", "Not sure")]
        },
        "minority_status": {
            "text": "☪️ Do you belong to a notified minority community?",
            "options": [("yes", "Yes"), ("no", "No"), ("skip", "Not sure")]
        },
        "employment_status": {
            "text": "💼 What is your employment status?",
            "options": [("Unemployed", "Unemployed"), ("Employed", "Employed"), ("skip", "Not sure")]
        }
    }
    
    if field == "exact_age":
        age_range_code = session["profile"].get("age")
        from config import AGE_RANGES
        bounds = AGE_RANGES.get(age_range_code, {"min": 18, "max": 35})
        r_min = bounds["min"]
        r_max = bounds["max"]
        
        prompt_text = translate_text("🔢 Your age range overlaps with some schemes' requirements. Would you like to provide your exact age?", lang)
        keyboard = []
        row = []
        keyboard.append([InlineKeyboardButton(translate_text("25 or below", lang), callback_data="exact_age:25")])
        for age_val in range(r_min, r_max + 1):
            row.append(InlineKeyboardButton(str(age_val), callback_data=f"exact_age:{age_val}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(translate_text("36 or above", lang), callback_data="exact_age:36")])
        keyboard.append([InlineKeyboardButton(t("button_skip", lang), callback_data="exact_age:skip")])
        keyboard.append([InlineKeyboardButton(t("button_start_over", lang), callback_data="action:start_over")])
        keyboard.append([InlineKeyboardButton(translate_text("🔊 Voice Help", lang), callback_data="action:voice_help")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_question(context.bot, update.effective_chat.id, prompt_text, lang, keyboard=reply_markup, session=session)
        return
        
    q_info = dynamic_questions.get(field, {
        "text": f"Please provide details for: {field.replace('_', ' ')}",
        "options": [("yes", "Yes"), ("no", "No"), ("skip", "Not sure")]
    })
    
    prompt_text = translate_text(q_info["text"], lang)
    keyboard = []
    for val_code, val_name in q_info["options"]:
        btn_text = translate_text(val_name, lang)
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"dynamic:{field}:{val_code}")])
        
    keyboard.append([InlineKeyboardButton(t("button_start_over", lang), callback_data="action:start_over")])
    keyboard.append([InlineKeyboardButton(translate_text("🔊 Voice Help", lang), callback_data="action:voice_help")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_question(context.bot, update.effective_chat.id, prompt_text, lang, keyboard=reply_markup, session=session)

async def process_schemes_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict) -> None:
    category = session["selected_category"]
    profile = session["profile"]
    lang = session["language"]
    
    schemes_list = find_matching_schemes(ALL_SCHEMES, profile, category)
    
    next_field = get_next_missing_field(schemes_list, profile)
    if next_field:
        wait_msg = "ℹ️ " + translate_text("I need a few more details to confirm your eligibility.", lang)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=wait_msg)
        await ask_dynamic_question(update, context, session, next_field)
    else:
        session["eligible_schemes"] = schemes_list
        session["state_page"] = 0
        await show_eligible_schemes(update, context, session)

async def show_eligible_schemes(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict) -> None:
    """Lists matching eligible schemes dynamically using send_scheme_list."""
    session["state"] = STATE_SCHEMES_LIST
    schemes_list = session.get("eligible_schemes", [])
    lang = session["language"]
    
    if not schemes_list:
        no_res_text = t("no_results", lang)
        keyboard = [
            [InlineKeyboardButton(translate_text("✏️ Change Details", lang), callback_data="action:change_details")],
            [InlineKeyboardButton(t("button_start_over", lang), callback_data="action:start_over")],
            [InlineKeyboardButton(translate_text("🔊 Voice Help", lang), callback_data="action:voice_help")]
        ]
        session["last_voice_text"] = no_res_text
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_info(context.bot, update.effective_chat.id, no_res_text, lang, session=session, keyboard=reply_markup)
        return
    # Assertion safety validation immediately before displaying schemes to prevent leakage (Section 38)
    user_state = session["profile"].get("state")
    if user_state:
        for s in schemes_list:
            assert is_scheme_applicable_to_state(s, user_state) == "applicable", f"Assert failed: cross-state leakage. Scheme {s.get('id')} is not applicable in state '{user_state}'."
            
    page_num = session.get("state_page", 0)
    await send_scheme_list(context.bot, update.effective_chat.id, schemes_list, lang, session=session, page=page_num)

async def show_scheme_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict) -> None:
    """Shows the main options card for a selected scheme."""
    session["state"] = STATE_SCHEME_DETAIL
    scheme = session["selected_scheme"]
    lang = session["language"]
    
    trans_name = translate_text(scheme["name"], lang)
    
    eval_res = evaluate_scheme(scheme, session["profile"])
    status_label = "🟢 Likely Match" if eval_res["status"] == "eligible" else "🟡 More Information Needed"
    status_trans = translate_text(status_label, lang)
    
    prompt_text = f"📋 **{trans_name}**\n\n🔹 **{translate_text('Status', lang)}**: {status_trans}\n\n{translate_text('What would you like to know?', lang)}"
    
    # Translations for details buttons
    btn_why = translate_text("🔎 Why this scheme?", lang)
    btn_benefits = translate_text("💰 Benefits", lang)
    btn_eligibility = translate_text("✅ Eligibility", lang)
    btn_docs = translate_text("📄 Required Documents", lang)
    btn_steps = translate_text("📝 Apply Steps", lang)
    btn_official = translate_text("🌐 Official Website", lang)
    btn_help = translate_text("🏢 Help Centre", lang)
    btn_back = t("button_back_schemes", lang)
    btn_start_over = t("button_start_over", lang)
    
    keyboard = [
        [
            InlineKeyboardButton(btn_why, callback_data="detail:why_matched")
        ],
        [
            InlineKeyboardButton(btn_benefits, callback_data="detail:benefits"),
            InlineKeyboardButton(btn_eligibility, callback_data="detail:eligibility")
        ],
        [
            InlineKeyboardButton(btn_docs, callback_data="detail:documents"),
            InlineKeyboardButton(btn_steps, callback_data="detail:apply")
        ],
        [
            InlineKeyboardButton(btn_official, callback_data="detail:official"),
            InlineKeyboardButton(btn_help, callback_data="detail:help")
        ],
        [InlineKeyboardButton(btn_back, callback_data="action:back_schemes")],
        [InlineKeyboardButton(btn_start_over, callback_data="action:start_over")],
        [InlineKeyboardButton(translate_text("🔊 Voice Help", lang), callback_data="action:voice_help")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Asynchronously generate voice summary using Gemini (run in thread)
    voice_text = await asyncio.to_thread(summarize_scheme_for_voice, scheme["name"], scheme["description"], lang)
    
    await send_info(context.bot, update.effective_chat.id, prompt_text, lang, session=session, keyboard=reply_markup, voice_text=voice_text)

# ----------------------------------------------------------------------
# CALLBACK QUERY CONTROLLER
# ----------------------------------------------------------------------

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes all bot callback query events and generates separate messages."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    session = get_session(user_id)
    lang = session["language"]
    data = query.data
    
    # A. Explicit Voice Help action handler (Section 11, 12)
    if data == "action:voice_help":
        voice_text = session.get("last_voice_text")
        if not voice_text:
            return
            
        # Light voice generation guard (Section 12)
        if session.get("voice_generating"):
            warning_text = translate_text("🔊 Voice help is being prepared. Please wait.", lang)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=warning_text)
            return
            
        session["voice_generating"] = True
        try:
            await send_voice_help(context.bot, update.effective_chat.id, voice_text, lang)
        finally:
            session["voice_generating"] = False
        return
        
    # 1. Language selections
    if data.startswith("language:"):
        code_short = data.split(":")[-1]
        lang_info = LANGUAGES.get(code_short)
        if lang_info:
            session["language"] = lang_info["code"]
            lang = lang_info["code"]
            
        welcome_voice = translate_text("Welcome to ServiceMitra. Please select a sector from the menu below to discover eligible schemes.", lang)
        # Note: sector menu plays voice first time because it's welcome
        await show_sectors_menu(update, context, session)
        return
        
    # 2. Sector selection
    if data.startswith("category:"):
        cat_idx = int(data.split(":")[-1])
        categories_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "categories.json")
        with open(categories_file, "r", encoding="utf-8") as f:
            categories = json.load(f)
        cat_obj = categories[cat_idx]
        selected_cat = cat_obj["name"] if isinstance(cat_obj, dict) else cat_obj
        
        # Section 51: Sector change detection
        previous_category = session.get("selected_category")
        if previous_category != selected_cat:
            session["eligible_schemes"] = []
            session["selected_scheme"] = None
            session["state_page"] = 0
            logger.info(f"User changed category from {previous_category} to {selected_cat}. Cleared old results.")
            
        session["selected_category"] = selected_cat
        session["questions_to_ask"] = SECTOR_QUESTIONS.get(selected_cat, SECTOR_QUESTIONS["default"])
        session["current_question_index"] = 0
        session["state_page"] = 0
        
        intro_text = "📋 Let's check which schemes you may be eligible for. I'll ask you a few simple questions."
        await send_info(context.bot, update.effective_chat.id, intro_text, lang, session=session)
        
        await ask_next_question(update, context, session)
        return
        
    # 3. State page pagination
    if data.startswith("state_page:"):
        page_val = int(data.split(":")[-1])
        session["state_page"] = page_val
        if session["state"] == STATE_EDIT_FIELD:
            await ask_edit_field(update, context, session, session.get("editing_field"))
        else:
            await ask_next_question(update, context, session)
        return
        
    # 4. Schemes lists page pagination
    if data.startswith("scheme_page:"):
        page_val = int(data.split(":")[-1])
        session["state_page"] = page_val
        await show_eligible_schemes(update, context, session)
        return
        
    # 4b. Dynamic follow-up answers
    if data.startswith("dynamic:"):
        _, field, val = data.split(":")
        if val == "skip":
            val = None
        elif val == "yes":
            val = True
        elif val == "no":
            val = False
        elif val.isdigit():
            val = int(val)
            
        session["profile"][field] = val
        session["dynamic_field"] = None
        await process_schemes_evaluation(update, context, session)
        return
        
    if data.startswith("exact_age:"):
        val = data.split(":")[-1]
        if val == "skip":
            val = None
        else:
            try:
                val = int(val)
            except ValueError:
                val = None
                
        session["profile"]["exact_age"] = val
        session["dynamic_field"] = None
        await process_schemes_evaluation(update, context, session)
        return

    # 5. Core form answer inputs
    question_prefixes = ["age:", "gender:", "occupation:", "income:", "state:", "social_category:", "education:"]
    for prefix in question_prefixes:
        if data.startswith(prefix):
            field = prefix.split(":")[0]
            val = data.split(":")[-1]
            if val == "skip":
                val = None
                
            # State canonization and state-change detection (Section 48, 49, 50)
            if field == "state":
                if val:
                    val = val.replace("_", " ") # restore space
                previous_state = session["profile"].get("state")
                if previous_state != val:
                    session["eligible_schemes"] = []
                    session["selected_scheme"] = None
                    session["state_page"] = 0
                    logger.info(f"User changed state from {previous_state} to {val}. Cleared old results.")
                session["state_page"] = 0
                
            session["profile"][field] = val
            
            if session["state"] == STATE_EDIT_FIELD:
                session["editing_field"] = None
                await show_profile_summary(update, context, session)
            else:
                session["current_question_index"] += 1
                await ask_next_question(update, context, session)
            return
            
    # 6. Change specific field request
    if data.startswith("edit_field:"):
        field = data.split(":")[-1]
        session["editing_field"] = field
        session["state_page"] = 0
        await ask_edit_field(update, context, session, field)
        return
        
    # 7. Select scheme card menu
    if data.startswith("scheme:"):
        scheme_id = data.split(":")[-1]
        scheme = None
        for s in ALL_SCHEMES:
            if s["id"] == scheme_id:
                scheme = s
                break
        if scheme:
            session["selected_scheme"] = scheme
            await show_scheme_detail(update, context, session)
        return
        
    # 8. Scheme detail card options (submenu pages)
    if data.startswith("detail:"):
        detail_type = data.split(":")[-1]
        scheme = session.get("selected_scheme")
        if not scheme:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Session timeout. Please start again with /start.")
            return
            
        detail_text = ""
        voice_text = ""
        
        if detail_type == "benefits":
            benefits_text = scheme["benefits"] or "Benefits details are not available in the source data."
            translated = translate_text(benefits_text, lang)
            detail_text = f"💰 **{translate_text('Benefits', lang)}**\n\n{translated}"
            voice_text = await asyncio.to_thread(summarize_scheme_for_voice, scheme["name"], benefits_text, lang)
            
        elif detail_type == "why_matched":
            eval_res = evaluate_scheme(scheme, session["profile"])
            matched = eval_res["matched_criteria"]
            missing = eval_res["missing_criteria"]
            failed = eval_res["failed_criteria"]
            
            detail_text = f"🔎 **{translate_text('Why this scheme matches you', lang)}**:\n\n"
            if matched:
                detail_text += f"✅ **{translate_text('Matched Criteria', lang)}**:\n"
                for m in matched:
                    detail_text += f"• {translate_text(m, lang)}\n"
                detail_text += "\n"
            if missing:
                detail_text += f"🟡 **{translate_text('Missing Criteria (More Info Needed)', lang)}**:\n"
                for m in missing:
                    field_label = m.replace("_", " ").title()
                    detail_text += f"• {translate_text(field_label, lang)}\n"
                detail_text += "\n"
            if failed:
                detail_text += f"❌ **{translate_text('Unmatched / Failed Criteria', lang)}**:\n"
                for f in failed:
                    detail_text += f"• {translate_text(f, lang)}\n"
                detail_text += "\n"
            voice_text = translate_text("Here is why this scheme matches your profile.", lang)
            
        elif detail_type == "eligibility":
            official_elig = scheme["eligibility_text"] or "Official eligibility details are not available in the source data."
            translated_elig = translate_text(official_elig, lang)
            
            eval_res = evaluate_scheme(scheme, session["profile"])
            checklist = f"👤 **{translate_text('Eligibility Assessment', lang)}**:\n\n"
            for m in eval_res["matched_criteria"]:
                checklist += f"✓ {translate_text(m, lang)}\n"
            for m in eval_res["missing_criteria"]:
                field_label = m.replace("_", " ").title()
                checklist += f"❔ {translate_text(field_label, lang)} ({translate_text('More info needed', lang)})\n"
            for f in eval_res["failed_criteria"]:
                checklist += f"✗ {translate_text(f, lang)}\n"
                
            checklist += f"\n📋 **{translate_text('Official requirements', lang)}**:\n{translated_elig}"
            detail_text = checklist
            voice_text = translate_text("Based on your profile, you appear to meet the available eligibility criteria.", lang)
            
        elif detail_type == "documents":
            docs = scheme["required_documents"]
            if docs:
                translated_docs = [translate_text(d, lang) for d in docs]
                detail_text = f"📄 **{translate_text('Required Documents', lang)}**\n\n" + "\n".join([f"☐ {d}" for d in translated_docs])
                voice_text = translate_text("To apply for this scheme, the required documents include: " + ", ".join(translated_docs[:3]), lang)
            else:
                detail_text = f"📄 **{translate_text('Required Documents', lang)}**\n\n" + translate_text("No required documents list is available in the source data.", lang)
                voice_text = translate_text("Required documents information is not available in the source data.", lang)
                
        elif detail_type == "apply":
            steps = scheme["application_steps"]
            if steps:
                translated_steps = [translate_text(s, lang) for s in steps]
                detail_text = f"📝 **{translate_text('How to Apply', lang)}**\n\n" + "\n".join([f"{idx+1}. {s}" for idx, s in enumerate(translated_steps)])
                voice_text = translate_text("The application steps are: " + " ".join(translated_steps[:3]), lang)
            else:
                detail_text = f"📝 **{translate_text('How to Apply', lang)}**\n\n" + translate_text("Application steps are not available in the source data.", lang)
                voice_text = translate_text("Application steps are not available in the source data.", lang)
                
        elif detail_type == "help":
            help_info = scheme["help_center"]
            if help_info:
                translated_help = translate_text(help_info, lang)
                detail_text = f"🏢 **{translate_text('Help Centre', lang)}**\n\n{translated_help}"
                voice_text = translate_text("Here is the contact information.", lang)
            else:
                detail_text = f"🏢 **{translate_text('Help Centre', lang)}**\n\n" + translate_text("Help centre information is not available in the source data.", lang)
                voice_text = translate_text("Help centre information is not available in the source data.", lang)
                
        elif detail_type == "official":
            link = scheme["official_link"]
            if link:
                detail_text = f"🌐 **{translate_text('Official Website', lang)}**\n\n" + translate_text("Use the button below to visit the official website.", lang)
                voice_text = translate_text("You can open the official website using the link below.", lang)
            else:
                detail_text = f"🌐 **{translate_text('Official Website', lang)}**\n\n" + translate_text("Official application link is not available in the source data.", lang)
                voice_text = translate_text("Official application link is not available in the source data.", lang)

        # Build inline keyboard navigation options for all other submenus
        keyboard = []
        row = []
        all_details = [
            ("why_matched", "🔎 Why this scheme?"),
            ("benefits", "💰 Benefits"),
            ("eligibility", "✅ Eligibility"),
            ("documents", "📄 Documents"),
            ("apply", "📝 Apply Steps"),
            ("help", "🏢 Help Centre")
        ]
        
        for code, label in all_details:
            if code != detail_type:
                row.append(InlineKeyboardButton(translate_text(label, lang), callback_data=f"detail:{code}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
        if row:
            keyboard.append(row)
            
        # Add official website link if it exists and we're not currently on it
        if scheme["official_link"] and detail_type != "official":
            keyboard.append([InlineKeyboardButton(translate_text("🌐 Official Website", lang), url=scheme["official_link"])])
        elif scheme["official_link"] and detail_type == "official":
            keyboard.append([InlineKeyboardButton(translate_text("Open Website 🌐", lang), url=scheme["official_link"])])
            
        keyboard.append([InlineKeyboardButton(translate_text("⬅ Back to Scheme", lang), callback_data=f"scheme:{scheme['id']}")])
        keyboard.append([InlineKeyboardButton(t("button_start_over", lang), callback_data="action:start_over")])
        keyboard.append([InlineKeyboardButton(translate_text("🔊 Voice Help", lang), callback_data="action:voice_help")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await send_info(context.bot, update.effective_chat.id, detail_text, lang, session=session, keyboard=reply_markup, voice_text=voice_text)
        return

    # 9. General Menu actions
    if data == "action:start_over":
        await start(update, context)
        return
        
    if data == "action:change_language":
        reset_session(user_id)
        keyboard = []
        for code, info in LANGUAGES.items():
            keyboard.append([InlineKeyboardButton(f"{info['flag']} {info['name']}", callback_data=f"language:{code}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t("welcome", "en-IN"), reply_markup=reply_markup)
        return
        
    if data == "action:back_menu":
        await show_sectors_menu(update, context, session)
        return
        
    if data == "action:back_schemes":
        session["state_page"] = 0
        await show_eligible_schemes(update, context, session)
        return
        
    if data == "action:change_details":
        await show_change_details_menu(update, context, session)
        return
        
    if data == "action:back_summary" or data == "action:cancel_edit":
        session["editing_field"] = None
        await show_profile_summary(update, context, session)
        return
        
    if data == "action:check_schemes":
        # First send standard thank you text (text-only)
        ack_text = "Thanks! I have all the information I need."
        await send_info(context.bot, update.effective_chat.id, ack_text, lang, session=session)
        
        # Second send matching loader
        wait_text = "🔎 Checking available schemes..."
        await send_info(context.bot, update.effective_chat.id, wait_text, lang, session=session)
        
        # Start dynamic evaluation loop
        await process_schemes_evaluation(update, context, session)
        return

# ----------------------------------------------------------------------
# INCOMING MESSAGE HANDLER (TEXT/VOICE)
# ----------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Router for typed texts and voice messages."""
    user_id = update.effective_user.id
    session = get_session(user_id)
    lang = session["language"]
    
    voice_file_path = None
    text_content = ""
    
    # 1. Download and process voice note
    if update.message.voice:
        try:
            logger.info("Voice message received from Telegram.")
            voice_file = await update.message.voice.get_file()
            voice_file_path = os.path.join(TEMP_DIR, f"voice_{user_id}_{int(time.time())}.ogg")
            await voice_file.download_to_drive(voice_file_path)
            
            # Run STT transcription in thread
            text_content = await asyncio.to_thread(speech_to_text, voice_file_path)
            if not text_content:
                fail_msg = translate_text("Sorry, I couldn't understand the voice message. Please try again or use the buttons below.", lang)
                await send_info(context.bot, update.effective_chat.id, fail_msg, lang, session=session)
                return
        except Exception as e:
            logger.error(f"Failed to handle voice message: {e}")
            fail_msg = translate_text("Sorry, I couldn't understand the voice message. Please try again or use the buttons below.", lang)
            await send_info(context.bot, update.effective_chat.id, fail_msg, lang, session=session)
            return
        finally:
            if voice_file_path and os.path.exists(voice_file_path):
                try:
                    os.remove(voice_file_path)
                except Exception:
                    pass
    elif update.message.text:
        text_content = update.message.text.strip()
        
    if not text_content:
        return
        
    logger.info(f"Processing text input: '{text_content}'")
    state = session["state"]
    
    # 2. Match states for free text logic
    if state == STATE_LANGUAGE:
        keyboard = []
        for code, info in LANGUAGES.items():
            keyboard.append([InlineKeyboardButton(f"{info['flag']} {info['name']}", callback_data=f"language:{code}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=t("welcome", "en-IN"), reply_markup=reply_markup)
        
    elif state == STATE_SECTOR:
        categories_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "categories.json")
        with open(categories_file, "r", encoding="utf-8") as f:
            categories = json.load(f)
            
        from services.gemini_service import client
        from google.genai import types
        
        category_matched = None
        # Extract category names for Gemini matching
        cat_names = [cat["name"] if isinstance(cat, dict) else cat for cat in categories]
        
        if client:
            prompt = f"""
            The user wants to find government schemes. They said: "{text_content}"
            Available categories: {cat_names}
            
            Identify if their input matches any of the available categories.
            Return ONLY the exact matched category name from the list, or the word "None" if there is no clear match.
            Do not include punctuation or explanations.
            """
            try:
                # Run Gemini generate content in thread to avoid blocking loop
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.1)
                )
                res = response.text.strip()
                if res in cat_names:
                    category_matched = res
            except Exception as e:
                logger.error(f"Failed to match category using Gemini: {e}")
                
        if category_matched:
            session["selected_category"] = category_matched
            session["questions_to_ask"] = SECTOR_QUESTIONS.get(category_matched, SECTOR_QUESTIONS["default"])
            session["current_question_index"] = 0
            session["state_page"] = 0
            
            # Extract profile fields from the category selection prompt if any
            extracted = await asyncio.to_thread(extract_profile_fields, text_content)
            for k, v in extracted.items():
                if v is not None:
                    # Canonize state in voice/text extraction
                    if k == "state":
                        v = v.replace("_", " ")
                    session["profile"][k] = v
            
            confirm_msg = f"🏛 Selected: {translate_text(category_matched, lang)}"
            await send_info(context.bot, update.effective_chat.id, confirm_msg, lang, session=session)
            
            intro_text = "📋 Let's check which schemes you may be eligible for. I'll ask you a few simple questions."
            await send_info(context.bot, update.effective_chat.id, intro_text, lang, session=session)
            
            await ask_next_question(update, context, session)
        else:
            fail_text = translate_text("I couldn't match that to any category. Please select from the buttons below.", lang)
            await show_sectors_menu(update, context, session)
            
    elif state in [STATE_QUESTIONNAIRE, STATE_CONFIRM_PROFILE, STATE_EDIT_FIELD]:
        dynamic_field = session.get("dynamic_field")
        if dynamic_field:
            val = None
            text_low = text_content.lower()
            if dynamic_field == "exact_age":
                import re
                nums = re.findall(r'\d+', text_low)
                if nums:
                    val = int(nums[0])
            elif dynamic_field in ["single_girl_child", "widow_status", "bpl_status", "land_ownership", "rural_resident", "domicile", "minority_status"]:
                if any(w in text_low for w in ["yes", "ha", "true", "yeah", "हाँ", "అవును", "ஆம்", "ಹೌದು"]):
                    val = True
                elif any(w in text_low for w in ["no", "na", "false", "nah", "नहीं", "కాదు", "இல்லை", "ಇಲ್ಲ"]):
                    val = False
            elif dynamic_field == "disability_percentage":
                if any(w in text_low for w in ["no", "na", "नहीं", "కాదు", "இல்லை", "ಇಲ್ಲ"]):
                    val = 0
                elif "80" in text_low:
                    val = 80
                elif "40" in text_low:
                    val = 40
            
            if val is not None:
                session["profile"][dynamic_field] = val
                session["dynamic_field"] = None
                await process_schemes_evaluation(update, context, session)
            else:
                error_msg = translate_text("I couldn't understand your response. Please select an option using the buttons or type/speak a clear answer.", lang)
                await send_info(context.bot, update.effective_chat.id, error_msg, lang, session=session)
                await ask_dynamic_question(update, context, session, dynamic_field)
            return

        # Extract fields from voice/text in thread
        extracted = await asyncio.to_thread(extract_profile_fields, text_content)
        
        # Canonize state if extracted
        if "state" in extracted and extracted["state"]:
            extracted["state"] = extracted["state"].replace("_", " ")
            
        # Check if we were editing a specific field
        if state == STATE_EDIT_FIELD:
            field = session.get("editing_field")
            val = extracted.get(field)
            if val is not None:
                # Clear state mapping checks
                if field == "state":
                    previous_state = session["profile"].get("state")
                    if previous_state != val:
                        session["eligible_schemes"] = []
                        session["selected_scheme"] = None
                        session["state_page"] = 0
                session["profile"][field] = val
                session["editing_field"] = None
                await show_profile_summary(update, context, session)
            else:
                error_msg = translate_text("I couldn't understand your response. Please select an option using the buttons or type/speak a clear answer.", lang)
                await send_info(context.bot, update.effective_chat.id, error_msg, lang, session=session)
                await ask_edit_field(update, context, session, field)
            return

        # Regular questionnaire flow extraction
        questions = session["questions_to_ask"]
        idx = session["current_question_index"]
        
        # Update all extracted fields
        updated_any = False
        for k, v in extracted.items():
            if v is not None:
                # State change checks
                if k == "state":
                    previous_state = session["profile"].get("state")
                    if previous_state != v:
                        session["eligible_schemes"] = []
                        session["selected_scheme"] = None
                        session["state_page"] = 0
                session["profile"][k] = v
                updated_any = True
                
        if idx < len(questions):
            current_field = questions[idx]
            # If the current field was not set by the extraction, alert user
            if session["profile"].get(current_field) is None:
                error_msg = translate_text("I couldn't understand your response. Please select an option using the buttons or type/speak a clear answer.", lang)
                await send_info(context.bot, update.effective_chat.id, error_msg, lang, session=session)
                
        await ask_next_question(update, context, session)
            
    else:
        fallback_msg = translate_text("Please use the buttons provided above to navigate, or send /start to start over.", lang)
        await send_info(context.bot, update.effective_chat.id, fallback_msg, lang, session=session)

def main() -> None:
    """Builds and launches the bot application."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("your_"):
        print("\n" + "="*60)
        print("CRITICAL CONFIGURATION ERROR:")
        print("TELEGRAM_BOT_TOKEN is missing or not configured in .env.")
        print("Please create a .env file and set TELEGRAM_BOT_TOKEN before running bot.py.")
        print("="*60 + "\n")
        sys.exit(0)
        
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT | filters.VOICE, handle_message))
    
    # Start polling
    logger.info("Bot started and polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
