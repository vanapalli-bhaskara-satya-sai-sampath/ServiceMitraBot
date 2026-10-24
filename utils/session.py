import logging

logger = logging.getLogger(__name__)

# In-memory dictionary to store user sessions
# Key: telegram_user_id (str)
_sessions = {}

def get_session(user_id: int) -> dict:
    """
    Get the session for a user. If it doesn't exist, initialize it.
    """
    uid = str(user_id)
    if uid not in _sessions:
        reset_session(user_id)
    return _sessions[uid]

def reset_session(user_id: int) -> dict:
    """
    Reset the session for a user to initial defaults.
    """
    uid = str(user_id)
    _sessions[uid] = {
        "language": "en-IN",           # Default language code
        "state": "STATE_LANGUAGE",     # Initial conversation state
        "profile": {
            "age": None,
            "gender": None,
            "occupation": None,
            "annual_income": None,
            "state": None,
            "social_category": None,
            "education": None,
            "exact_age": None,
            "single_girl_child": None,
            "disability_percentage": None,
            "bpl_status": None,
            "land_ownership": None,
            "widow_status": None,
            "minority_status": None,
            "employment_status": None,
            "student_year": None,
            "course_type": None,
            "institution_type": None,
            "rural_resident": None,
            "domicile": None
        },
        "selected_category": None,
        "eligible_schemes": [],
        "selected_scheme": None,
        "current_question_index": 0,
        "questions_to_ask": [],
        "state_page": 0                # For pagination of states/schemes
    }
    logger.info(f"Session reset for user {uid}")
    return _sessions[uid]

def update_profile(user_id: int, key: str, value) -> dict:
    """
    Update a profile field for a user.
    """
    session = get_session(user_id)
    session["profile"][key] = value
    logger.info(f"Updated profile for user {user_id}: {key} = {value}")
    return session
