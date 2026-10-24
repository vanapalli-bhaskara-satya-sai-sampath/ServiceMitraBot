import logging
import re
from config import INCOME_RANGES, AGE_RANGES, STATES

logger = logging.getLogger(__name__)

# Education level hierarchy mappings
EDU_LEVELS = {
    "School": 1,
    "10th": 2,
    "12th": 3,
    "Diploma": 4,
    "UG": 5,
    "PG": 6
}

def normalize_state(state_name: str) -> str:
    """Canonizes state names to match config.STATES list."""
    if not state_name:
        return ""
    s = state_name.strip().lower().replace("-", " ").replace("_", " ").replace("&", "and")
    
    mapping = {
        "ap": "Andhra Pradesh",
        "andhra": "Andhra Pradesh",
        "andhra pradesh": "Andhra Pradesh",
        "arunachal": "Arunachal Pradesh",
        "arunachal pradesh": "Arunachal Pradesh",
        "assam": "Assam",
        "bihar": "Bihar",
        "chhattisgarh": "Chhattisgarh",
        "cg": "Chhattisgarh",
        "goa": "Goa",
        "gujarat": "Gujarat",
        "haryana": "Haryana",
        "hr": "Haryana",
        "himachal": "Himachal Pradesh",
        "hp": "Himachal Pradesh",
        "himachal pradesh": "Himachal Pradesh",
        "jharkhand": "Jharkhand",
        "karnataka": "Karnataka",
        "kerala": "Kerala",
        "kl": "Kerala",
        "mp": "Madhya Pradesh",
        "madhya pradesh": "Madhya Pradesh",
        "maharashtra": "Maharashtra",
        "mh": "Maharashtra",
        "manipur": "Manipur",
        "meghalaya": "Meghalaya",
        "mizoram": "Mizoram",
        "nagaland": "Nagaland",
        "odisha": "Odisha",
        "orissa": "Odisha",
        "punjab": "Punjab",
        "pb": "Punjab",
        "rajasthan": "Rajasthan",
        "rj": "Rajasthan",
        "sikkim": "Sikkim",
        "tamil nadu": "Tamil Nadu",
        "tn": "Tamil Nadu",
        "tamilnadu": "Tamil Nadu",
        "telangana": "Telangana",
        "tg": "Telangana",
        "ts": "Telangana",
        "tripura": "Tripura",
        "up": "Uttar Pradesh",
        "uttar pradesh": "Uttar Pradesh",
        "uttarakhand": "Uttarakhand",
        "uk": "Uttarakhand",
        "west bengal": "West Bengal",
        "wb": "West Bengal",
        "delhi": "Delhi",
        "nct of delhi": "Delhi",
        "andaman": "Andaman and Nicobar Islands",
        "andaman and nicobar": "Andaman and Nicobar Islands",
        "andaman and nicobar islands": "Andaman and Nicobar Islands",
        "chandigarh": "Chandigarh",
        "ch": "Chandigarh",
        "dadra": "Dadra and Nagar Haveli and Daman and Diu",
        "daman": "Dadra and Nagar Haveli and Daman and Diu",
        "dnh": "Dadra and Nagar Haveli and Daman and Diu",
        "dd": "Dadra and Nagar Haveli and Daman and Diu",
        "dadra and nagar haveli and daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
        "jk": "Jammu and Kashmir",
        "jammu": "Jammu and Kashmir",
        "kashmir": "Jammu and Kashmir",
        "jammu and kashmir": "Jammu and Kashmir",
        "ladakh": "Ladakh",
        "lakshadweep": "Lakshadweep",
        "puducherry": "Puducherry",
        "pondicherry": "Puducherry",
        "py": "Puducherry"
    }
    
    if s in mapping:
        return mapping[s]
        
    for canonical in STATES:
        c_low = canonical.lower()
        if c_low in s or s in c_low:
            return canonical
            
    return state_name

def normalize_category(cat: str) -> str:
    """Maps sector name variations to standard category names."""
    if not cat:
        return ""
    cat_lower = cat.strip().lower()
    
    mapping = {
        "education & learning": "Education & Learning",
        "education, learning & scholarships": "Education & Learning",
        "education": "Education & Learning",
        "scholarships": "Education & Learning",
        "scholarship": "Education & Learning",
        
        "agriculture, rural & environment": "Agriculture, Rural & Environment",
        "agriculture,rural & environment": "Agriculture, Rural & Environment",
        "agriculture": "Agriculture, Rural & Environment",
        "rural": "Agriculture, Rural & Environment",
        "environment": "Agriculture, Rural & Environment",
        "farming": "Agriculture, Rural & Environment",
        
        "health & wellness": "Health & Wellness",
        "health": "Health & Wellness",
        "wellness": "Health & Wellness",
        
        "social welfare & empowerment": "Social Welfare & Empowerment",
        "social welfare": "Social Welfare & Empowerment",
        "welfare": "Social Welfare & Empowerment",
        
        "skills & employment": "Skills & Employment",
        "employment & training": "Skills & Employment",
        "employment": "Skills & Employment",
        "training": "Skills & Employment",
        "skills": "Skills & Employment",
        
        "business & entrepreneurship": "Business & Entrepreneurship",
        "business": "Business & Entrepreneurship",
        "entrepreneurship": "Business & Entrepreneurship",
        
        "housing & shelter": "Housing & Shelter",
        "housing": "Housing & Shelter",
        
        "banking, financial services and insurance": "Banking, Financial Services and Insurance",
        "banking, financial services & insurance": "Banking, Financial Services and Insurance",
        "banking": "Banking, Financial Services and Insurance",
        "finance": "Banking, Financial Services and Insurance",
        "financial services": "Banking, Financial Services and Insurance",
        
        "travel & tourism": "Travel & Tourism",
        "travel": "Travel & Tourism",
        "tourism": "Travel & Tourism",
        
        "sports & culture": "Sports & Culture",
        "culture & heritage": "Sports & Culture",
        "sports": "Sports & Culture",
        "culture": "Sports & Culture"
    }
    
    return mapping.get(cat_lower, cat)

def get_age_bounds(user_age):
    """Parses user age input (exact integer, range key, or dict) into min and max bounds."""
    if isinstance(user_age, dict):
        return user_age.get("min", 0), user_age.get("max", 120)
    if isinstance(user_age, str):
        if user_age in AGE_RANGES:
            return AGE_RANGES[user_age]["min"], AGE_RANGES[user_age]["max"]
        try:
            val = int(user_age)
            return val, val
        except ValueError:
            pass
    if isinstance(user_age, (int, float)):
        return int(user_age), int(user_age)
    return None, None

def get_income_bounds(user_income):
    """Parses user income input (exact integer, range key, or dict) into min and max bounds."""
    if isinstance(user_income, dict):
        return user_income.get("min", 0), user_income.get("max", 99999999)
    if isinstance(user_income, str):
        if user_income in INCOME_RANGES:
            return INCOME_RANGES[user_income]["min"], INCOME_RANGES[user_income]["max"]
        try:
            val = int(user_income)
            return val, val
        except ValueError:
            pass
    if isinstance(user_income, (int, float)):
        return int(user_income), int(user_income)
    return None, None

def normalize_profile(profile: dict) -> dict:
    """Standardizes user profile values to canonical formats."""
    np = dict(profile)
    
    if np.get("state"):
        np["state"] = normalize_state(np["state"])
        
    edu = np.get("education")
    if edu:
        edu_low = edu.strip().lower()
        if edu_low in ["pg", "postgraduate", "post graduate", "post graduation", "masters", "master", "phd", "ph.d."]:
            np["education"] = "PG"
        elif edu_low in ["ug", "undergraduate", "under grad", "degree", "graduation", "graduate"]:
            np["education"] = "UG"
        elif edu_low in ["diploma", "polytechnic"]:
            np["education"] = "Diploma"
        elif edu_low in ["12th", "class 12", "intermediate", "hsc"]:
            np["education"] = "12th"
        elif edu_low in ["10th", "class 10", "matric", "ssc"]:
            np["education"] = "10th"
        elif edu_low in ["school", "primary", "secondary"]:
            np["education"] = "School"
        else:
            np["education"] = "Other"
            
    cat = np.get("social_category")
    if cat:
        cat_low = cat.strip().lower()
        if cat_low in ["general", "gen", "unreserved", "ur"]:
            np["social_category"] = "General"
        elif cat_low in ["obc", "other backward class", "backward class", "obcs"]:
            np["social_category"] = "OBC"
        elif cat_low in ["sc", "scheduled caste", "scs"]:
            np["social_category"] = "SC"
        elif cat_low in ["st", "scheduled tribe", "sts", "scheduled tribes"]:
            np["social_category"] = "ST"
        elif cat_low in ["ews", "economically weaker section"]:
            np["social_category"] = "EWS"
        elif cat_low in ["minority", "minorities"]:
            np["social_category"] = "Minority"
        else:
            np["social_category"] = "Other"
            
    gender = np.get("gender")
    if gender:
        gender_low = gender.strip().lower()
        if gender_low in ["male", "boy", "man", "men"]:
            np["gender"] = "Male"
        elif gender_low in ["female", "girl", "woman", "women"]:
            np["gender"] = "Female"
        elif gender_low in ["other", "transgender", "third gender"]:
            np["gender"] = "Other"
        else:
            np["gender"] = None
            
    occ = np.get("occupation")
    if occ:
        occ_low = occ.strip().lower()
        if occ_low in ["farmer", "agriculture", "cultivator", "grower", "farmers", "tenant farmer", "agricultural worker"]:
            np["occupation"] = "Farmer"
        elif occ_low in ["student", "scholar", "learner", "students"]:
            np["occupation"] = "Student"
        elif occ_low in ["employee", "salaried", "service", "job", "employees"]:
            np["occupation"] = "Employee"
        elif occ_low in ["business", "self employed", "entrepreneur", "trader", "self-employed", "business owner"]:
            np["occupation"] = "Business"
        elif occ_low in ["worker", "labour", "laborer", "artisan", "weavers", "weaver", "workers"]:
            np["occupation"] = "Worker"
        elif occ_low in ["homemaker", "housewife", "homemakers"]:
            np["occupation"] = "Homemaker"
        elif occ_low in ["retired", "pensioner"]:
            np["occupation"] = "Retired"
        else:
            np["occupation"] = "Other"
            
    return np

def normalize_scheme_data(scheme: dict) -> dict:
    """Converts a legacy or un-normalized scheme to the new eligibility and geo-applicability model."""
    if "government_level" in scheme:
        return scheme
        
    ns = dict(scheme)
    app = ns.get("applicability") or {}
    legacy_scope = app.get("scope") or "unknown"
    legacy_states = app.get("states") or []
    
    gov_level = "unknown"
    new_scope = "unknown"
    new_states = []
    region = None
    
    if legacy_scope == "state":
        gov_level = "state"
        new_scope = "state"
        new_states = [normalize_state(s) for s in legacy_states if s]
    elif legacy_scope == "multi_state":
        gov_level = "state"
        new_scope = "multi_state"
        new_states = [normalize_state(s) for s in legacy_states if s]
    elif legacy_scope == "central":
        gov_level = "central"
        desc = (ns.get("description") or "").lower()
        elig_text = (ns.get("eligibility_text") or "").lower()
        title = (ns.get("name") or "").lower()
        
        ne_keywords = ["north eastern", "north-eastern", "northeast", "north east region", "jhum"]
        is_ne = any(kw in desc or kw in elig_text or kw in title for kw in ne_keywords)
        
        ne_states = [
            "Arunachal Pradesh", "Assam", "Manipur", "Meghalaya", 
            "Mizoram", "Nagaland", "Sikkim", "Tripura"
        ]
        
        if is_ne:
            new_scope = "regional"
            region = "North East"
            new_states = ne_states
        else:
            found_states = []
            for st in STATES:
                st_low = st.lower()
                if re.search(r'\b' + re.escape(st_low) + r'\b', elig_text) or re.search(r'\b' + re.escape(st_low) + r'\b', title):
                    found_states.append(st)
            
            if found_states:
                if len(found_states) == 1:
                    new_scope = "state"
                    new_states = found_states
                else:
                    new_scope = "multi_state"
                    new_states = found_states
            else:
                new_scope = "national"
                new_states = []
    else:
        gov_level = "unknown"
        new_scope = "unknown"
        new_states = []
        
    ns["government_level"] = gov_level
    ns["applicability"] = {
        "scope": new_scope,
        "states": new_states,
        "region": region
    }
    
    legacy_elig = ns.get("eligibility") or {}
    age_min = legacy_elig.get("age_min")
    age_max = legacy_elig.get("age_max")
    
    gender = legacy_elig.get("gender") or []
    if isinstance(gender, str):
        gender = [gender]
    gender = [g.strip() for g in gender if g]
    
    occupation = legacy_elig.get("occupation") or []
    if isinstance(occupation, str):
        occupation = [occupation]
    occupation = [o.strip() for o in occupation if o]
    
    social_category = legacy_elig.get("social_category") or []
    if isinstance(social_category, str):
        social_category = [social_category]
    social_category = [c.strip() for c in social_category if c]
    
    income_max = legacy_elig.get("income_max")
    
    education = legacy_elig.get("education") or []
    if isinstance(education, str):
        education = [education]
    education = [e.strip() for e in education if e]
    
    min_edu_level = None
    if education:
        edu_hierarchy = {
            "school": 1, "class 10": 2, "10th": 2, "matric": 2, "post-matric": 3,
            "class 12": 3, "12th": 3, "intermediate": 3, "diploma": 4, "polytechnic": 4,
            "ug": 5, "undergraduate": 5, "degree": 5, "graduation": 5, "graduate": 5,
            "pg": 6, "postgraduate": 6, "post grad": 6, "post graduation": 6, "masters": 6, "master": 6,
            "phd": 7, "ph.d.": 7
        }
        
        mapped_levels = []
        for edu_req in education:
            req_low = edu_req.lower()
            for key, level in edu_hierarchy.items():
                if key in req_low:
                    mapped_levels.append((level, key))
                    
        if mapped_levels:
            mapped_levels.sort(key=lambda x: x[0])
            min_level_val, min_level_key = mapped_levels[0]
            canonical_map = {
                1: "School", 2: "10th", 3: "12th", 4: "Diploma", 5: "UG", 6: "PG", 7: "PG"
            }
            min_edu_level = canonical_map.get(min_level_val, "School")
            
    conditions = []
    desc_low = (ns.get("description") or "").lower() + " " + (ns.get("eligibility_text") or "").lower()
    
    if "single girl" in desc_low or "only girl" in desc_low:
        conditions.append({
            "field": "single_girl_child",
            "required": True,
            "source_text": "single girl child in the family"
        })
    if "disability" in desc_low or "divyangjan" in desc_low:
        dis_pct = 40
        if "80%" in desc_low or "severe" in desc_low:
            dis_pct = 80
        conditions.append({
            "field": "disability_percentage",
            "min": dis_pct,
            "source_text": f"disability of {dis_pct}% or more"
        })
    if "widow" in desc_low:
        conditions.append({
            "field": "widow_status",
            "required": True,
            "source_text": "widowed female"
        })
    if "bpl" in desc_low or "below poverty line" in desc_low:
        conditions.append({
            "field": "bpl_status",
            "required": True,
            "source_text": "belonging to BPL household"
        })
    if "landowner" in desc_low or "landholding" in desc_low or "own land" in desc_low:
        conditions.append({
            "field": "land_ownership",
            "required": True,
            "source_text": "land ownership"
        })
    if "minority" in desc_low or "minorities" in desc_low:
        conditions.append({
            "field": "minority_status",
            "required": True,
            "source_text": "minority community"
        })
    if "unemployed" in desc_low or "break in career" in desc_low:
        conditions.append({
            "field": "employment_status",
            "allowed": ["Unemployed"],
            "source_text": "unemployed"
        })
    if "1st year" in desc_low or "first year" in desc_low or "1st-year" in desc_low:
        conditions.append({
            "field": "student_year",
            "allowed": ["1"],
            "source_text": "enrolled in 1st year"
        })
        
    ns["eligibility"] = {
        "age_min": age_min,
        "age_max": age_max,
        "gender": gender,
        "occupation": occupation,
        "income_max": income_max,
        "state": legacy_states,
        "education": education,
        "social_category": social_category,
        "age": {
            "min": age_min,
            "max": age_max
        },
        "education_detail": {
            "minimum_level": min_edu_level
        },
        "income": {
            "max": income_max
        },
        "conditions": conditions
    }
    
    return ns

def match_gender(user_gender, scheme_genders):
    if not scheme_genders:
        return True
    norm_scheme = [g.lower().strip() for g in scheme_genders if g]
    if "any" in norm_scheme or "all" in norm_scheme:
        return True
    if not user_gender:
        return False
    u_g = user_gender.lower().strip()
    synonyms = {
        "male": ["male", "boy", "men", "man"],
        "female": ["female", "girl", "women", "woman"],
        "other": ["other", "transgender", "third gender"]
    }
    if u_g in norm_scheme:
        return True
    for key, syns in synonyms.items():
        if u_g == key or u_g in syns:
            for s in syns:
                if s in norm_scheme:
                    return True
    return False

def match_occupation(user_occ, scheme_occs):
    if not scheme_occs:
        return True
    norm_scheme = [o.lower().strip() for o in scheme_occs if o]
    if "any" in norm_scheme or "all" in norm_scheme:
        return True
    if not user_occ:
        return False
    u_o = user_occ.lower().strip()
    synonyms = {
        "farmer": ["farmer", "agriculture", "cultivator", "grower", "farmers", "tenant farmer", "agricultural worker"],
        "student": ["student", "scholar", "learner", "students"],
        "employee": ["employee", "salaried", "service", "job", "employees"],
        "business": ["business", "self employed", "entrepreneur", "trader", "self-employed", "business owner"],
        "worker": ["worker", "labour", "laborer", "artisan", "weavers", "weaver", "workers"],
        "homemaker": ["homemaker", "housewife", "homemakers"],
        "retired": ["retired", "pensioner"],
        "other": ["other", "any"]
    }
    if u_o in norm_scheme:
        return True
    for key, syns in synonyms.items():
        if u_o == key or u_o in syns:
            for s in syns:
                if s in norm_scheme:
                    return True
    return False

def match_education(user_edu, scheme_edus, min_level=None):
    if not scheme_edus and not min_level:
        return True
    if not user_edu:
        return False
    user_val = EDU_LEVELS.get(user_edu, 0)
    
    if min_level:
        req_val = EDU_LEVELS.get(min_level, 0)
        if user_val >= req_val:
            return True
            
    if scheme_edus:
        edu_hierarchy = {
            "school": 1, "class 10": 2, "10th": 2, "matric": 2, "post-matric": 3,
            "class 12": 3, "12th": 3, "intermediate": 3, "diploma": 4, "polytechnic": 4,
            "ug": 5, "undergraduate": 5, "degree": 5, "graduation": 5, "graduate": 5,
            "pg": 6, "postgraduate": 6, "post grad": 6, "post graduation": 6, "masters": 6, "master": 6,
        }
        scheme_levels = []
        for s_edu in scheme_edus:
            s_edu_low = s_edu.lower()
            if s_edu_low == user_edu.lower():
                return True
            matched_level = None
            for key, level in edu_hierarchy.items():
                if key in s_edu_low:
                    matched_level = level
                    break
            if matched_level:
                scheme_levels.append(matched_level)
                
        if scheme_levels:
            min_scheme_level = min(scheme_levels)
            if user_val >= min_scheme_level:
                return True
                
        for s_edu in scheme_edus:
            if user_edu.lower() in s_edu.lower() or s_edu.lower() in user_edu.lower():
                return True
                
    return False

def match_social_category(user_cat, scheme_cats):
    if not scheme_cats:
        return True
    norm_scheme = [c.lower().strip() for c in scheme_cats if c]
    if "any" in norm_scheme or "all" in norm_scheme:
        return True
    if not user_cat:
        return False
    u_c = user_cat.lower().strip()
    synonyms = {
        "general": ["general", "gen", "unreserved", "ur"],
        "obc": ["obc", "other backward class", "backward class", "obcs"],
        "sc": ["sc", "scheduled caste", "scs"],
        "st": ["st", "scheduled tribe", "sts", "scheduled tribes"],
        "ews": ["ews", "economically weaker section"],
        "minority": ["minority", "minorities"],
        "other": ["other"]
    }
    if u_c in norm_scheme:
        return True
    for key, syns in synonyms.items():
        if u_c == key or u_c in syns:
            for s in syns:
                if s in norm_scheme:
                    return True
    return False

def check_age_match(user_age, scheme_min, scheme_max) -> tuple:
    if scheme_min is None and scheme_max is None:
        return "eligible", ""
    if user_age is None:
        return "possible_match", "Age details missing"
    u_min, u_max = get_age_bounds(user_age)
    if u_min is None or u_max is None:
        return "possible_match", "Age range bounds could not be parsed"
    s_min = int(scheme_min) if scheme_min is not None else 0
    s_max = int(scheme_max) if scheme_max is not None else 120
    if u_max < s_min or u_min > s_max:
        return "ineligible", f"User age range {u_min}-{u_max} does not intersect with scheme age range {s_min}-{s_max}"
    if u_min >= s_min and u_max <= s_max:
        return "eligible", ""
    return "possible_match", f"User age range {u_min}-{u_max} overlaps with scheme age range {s_min}-{s_max}"

def check_income_match(user_income, scheme_max) -> tuple:
    if scheme_max is None:
        return "eligible", ""
    if user_income is None:
        return "possible_match", "Income details missing"
    u_min, u_max = get_income_bounds(user_income)
    if u_min is None or u_max is None:
        return "possible_match", "Income range bounds could not be parsed"
    s_max = int(scheme_max)
    if u_min > s_max:
        return "ineligible", f"User income range {u_min}-{u_max} is entirely above scheme max income of {s_max}"
    if u_max <= s_max:
        return "eligible", ""
    return "possible_match", f"User income range {u_min}-{u_max} overlaps with scheme max income of {s_max}"

def is_scheme_applicable_to_state(scheme: dict, user_state: str) -> str:
    """Checks geographic applicability. Returns 'applicable', 'not_applicable', or 'unknown'."""
    ns = normalize_scheme_data(scheme)
    if not user_state:
        return "unknown"
    u_state = normalize_state(user_state)
    app = ns.get("applicability") or {}
    scope = app.get("scope") or "unknown"
    states = app.get("states") or []
    norm_states = [normalize_state(s) for s in states if s]
    
    if scope == "national":
        return "applicable"
    if scope in ["state", "multi_state", "regional"]:
        if u_state in norm_states:
            return "applicable"
        return "not_applicable"
    return "unknown"

def evaluate_scheme(scheme: dict, profile: dict) -> dict:
    """Evaluates scheme eligibility criteria against user profile."""
    ns = normalize_scheme_data(scheme)
    np = normalize_profile(profile)
    
    status = "eligible"
    matched_criteria = []
    missing_criteria = []
    failed_criteria = []
    
    # 1. Geography Check
    user_state = np.get("state")
    geo_res = is_scheme_applicable_to_state(ns, user_state)
    if user_state:
        if geo_res == "not_applicable":
            failed_criteria.append("State applicability mismatch")
            status = "ineligible"
        elif geo_res == "unknown":
            missing_criteria.append("State applicability confirmation")
            if status != "ineligible":
                status = "possible_match"
        else:
            matched_criteria.append(f"State: {user_state} is applicable")
    else:
        missing_criteria.append("State of residence")
        if status != "ineligible":
            status = "possible_match"
            
    # 2. Age Check
    age_crit = ns["eligibility"].get("age") or {}
    age_min = age_crit.get("min")
    age_max = age_crit.get("max")
    user_age_raw = np.get("exact_age") if np.get("exact_age") is not None else np.get("age")
    
    age_status, age_reason = check_age_match(user_age_raw, age_min, age_max)
    if age_status == "ineligible":
        failed_criteria.append(f"Age: {age_reason}")
        status = "ineligible"
    elif age_status == "possible_match":
        missing_criteria.append("Age confirmation")
        if status != "ineligible":
            status = "possible_match"
    else:
        if age_min is not None or age_max is not None:
            matched_criteria.append("Age matches requirement")
            
    # 3. Income Check
    inc_crit = ns["eligibility"].get("income") or {}
    income_max = inc_crit.get("max")
    user_income = np.get("annual_income")
    
    inc_status, inc_reason = check_income_match(user_income, income_max)
    if inc_status == "ineligible":
        failed_criteria.append(f"Income: {inc_reason}")
        status = "ineligible"
    elif inc_status == "possible_match":
        missing_criteria.append("Income confirmation")
        if status != "ineligible":
            status = "possible_match"
    else:
        if income_max is not None:
            matched_criteria.append("Income matches requirement")
            
    # 4. Gender Check
    gender_req = ns["eligibility"].get("gender") or []
    user_gender = np.get("gender")
    if gender_req:
        if not user_gender:
            missing_criteria.append("Gender")
            if status != "ineligible":
                status = "possible_match"
        else:
            if match_gender(user_gender, gender_req):
                matched_criteria.append("Gender matches requirement")
            else:
                failed_criteria.append(f"Gender: {user_gender} does not match allowed {gender_req}")
                status = "ineligible"
                
    # 5. Occupation Check
    occ_req = ns["eligibility"].get("occupation") or []
    user_occ = np.get("occupation")
    if occ_req:
        if not user_occ:
            missing_criteria.append("Occupation")
            if status != "ineligible":
                status = "possible_match"
        else:
            if match_occupation(user_occ, occ_req):
                matched_criteria.append("Occupation matches requirement")
            else:
                failed_criteria.append(f"Occupation: {user_occ} does not match allowed {occ_req}")
                status = "ineligible"
                
    # 6. Education Check
    edu_crit = ns["eligibility"].get("education_detail") or {}
    edu_min = edu_crit.get("minimum_level")
    edu_list = ns["eligibility"].get("education") or []
    if edu_min or edu_list:
        user_edu = np.get("education")
        if not user_edu:
            missing_criteria.append("Education level")
            if status != "ineligible":
                status = "possible_match"
        else:
            if match_education(user_edu, edu_list, edu_min):
                matched_criteria.append("Education level matches requirement")
            else:
                failed_criteria.append(f"Education: {user_edu} is below required level(s)")
                status = "ineligible"
                
    # 7. Social Category Check
    cat_req = ns["eligibility"].get("social_category") or []
    user_cat = np.get("social_category")
    if cat_req:
        if not user_cat:
            missing_criteria.append("Social category")
            if status != "ineligible":
                status = "possible_match"
        else:
            if match_social_category(user_cat, cat_req):
                matched_criteria.append("Social category matches requirement")
            else:
                failed_criteria.append(f"Social Category: {user_cat} does not match allowed {cat_req}")
                status = "ineligible"
                
    # 8. Dynamic Conditions Check
    conditions = ns["eligibility"].get("conditions") or []
    for cond in conditions:
        field = cond.get("field")
        u_val = np.get(field)
        source_text = cond.get("source_text") or field.replace("_", " ")
        
        if u_val is None:
            missing_criteria.append(field)
            if status != "ineligible":
                status = "possible_match"
        else:
            if "required" in cond:
                required_val = cond["required"]
                u_bool = False
                if isinstance(u_val, bool):
                    u_bool = u_val
                elif isinstance(u_val, str):
                    u_bool = u_val.lower().strip() in ["yes", "true", "1"]
                
                if u_bool == required_val:
                    matched_criteria.append(f"Verified: {source_text}")
                else:
                    failed_criteria.append(f"Failed condition: {source_text}")
                    status = "ineligible"
            elif "allowed" in cond:
                allowed_vals = [str(x).lower().strip() for x in cond["allowed"]]
                u_str = str(u_val).lower().strip()
                if u_str in allowed_vals:
                    matched_criteria.append(f"Verified: {source_text}")
                else:
                    failed_criteria.append(f"Failed condition: {source_text} (Value '{u_val}' not allowed)")
                    status = "ineligible"
            elif "min" in cond:
                try:
                    u_num = float(u_val)
                    c_min = float(cond["min"])
                    if u_num >= c_min:
                        matched_criteria.append(f"Verified: {source_text}")
                    else:
                        failed_criteria.append(f"Failed condition: {source_text} (Value {u_num} < {c_min})")
                        status = "ineligible"
                except (ValueError, TypeError):
                    failed_criteria.append(f"Failed condition: {source_text} (Invalid value '{u_val}')")
                    status = "ineligible"

    # Compute ranking score
    total_crit = (
        (1 if (age_min is not None or age_max is not None) else 0) +
        (1 if income_max is not None else 0) +
        (1 if gender_req else 0) +
        (1 if occ_req else 0) +
        (1 if (edu_min or edu_list) else 0) +
        (1 if cat_req else 0) +
        len(conditions) + 1
    )
    score = (len(matched_criteria) / total_crit) if total_crit > 0 else 0.5
    
    # Detailed Debug Logging
    logger.debug(f"EVAL SCHEME: {ns.get('name')}")
    logger.debug(f"  Geography: {geo_res}")
    logger.debug(f"  Matched: {matched_criteria}")
    logger.debug(f"  Missing: {missing_criteria}")
    logger.debug(f"  Failed: {failed_criteria}")
    logger.debug(f"  Status: {status}")
    
    return {
        "status": status,
        "geography": geo_res,
        "matched_criteria": matched_criteria,
        "missing_criteria": missing_criteria,
        "failed_criteria": failed_criteria,
        "score": score
    }

def check_eligibility(scheme: dict, profile: dict) -> str:
    """Compatibility check_eligibility function."""
    res = evaluate_scheme(scheme, profile)
    return res["status"]

def filter_by_state(schemes: list, user_state: str) -> list:
    """Filters scheme list by state applicability (Stage 1)."""
    if not user_state:
        return schemes
    return [s for s in schemes if is_scheme_applicable_to_state(s, user_state) == "applicable"]

def filter_by_eligibility(schemes: list, profile: dict) -> list:
    """Filters scheme list by deterministic eligibility matching (Stage 2)."""
    eligible = []
    possible = []
    
    for s in schemes:
        res = evaluate_scheme(s, profile)
        if res["status"] == "eligible":
            eligible.append(s)
        elif res["status"] == "possible_match":
            possible.append(s)
            
    # Order: strong matches then possible matches
    return eligible, possible

def find_matching_schemes(schemes: list, profile: dict, category: str = None) -> list:
    """Runs the full eligibility pipeline and returns sorted matching schemes."""
    # Normalize profile and scheme data
    norm_prof = normalize_profile(profile)
    user_state = norm_prof.get("state")
    
    # Stage 1: Filter by state applicability
    # State mismatch always causes exclusion.
    applicable_schemes = schemes
    if user_state:
        applicable_schemes = [
            s for s in schemes 
            if is_scheme_applicable_to_state(s, user_state) == "applicable"
        ]
        
    # Stage 2: Filter by category (using aliases)
    category_to_match = category or profile.get("selected_category")
    if category_to_match:
        norm_match_cat = normalize_category(category_to_match)
        applicable_schemes = [
            s for s in applicable_schemes 
            if normalize_category(s["category"]) == norm_match_cat
        ]
        
    # Stage 3: Evaluate eligibility
    eligible, possible = filter_by_eligibility(applicable_schemes, norm_prof)
    
    # Sort eligible by score, possible by score
    eligible.sort(key=lambda s: evaluate_scheme(s, norm_prof)["score"], reverse=True)
    possible.sort(key=lambda s: evaluate_scheme(s, norm_prof)["score"], reverse=True)
    
    total_schemes = len(schemes)
    central_schemes = sum(1 for s in schemes if (normalize_scheme_data(s).get("applicability") or {}).get("scope") == "national")
    
    logger.info("="*50)
    logger.info("ELIGIBILITY FILTERING STAGES REPORT")
    logger.info("="*50)
    logger.info(f"Selected state:                        {user_state or 'None'}")
    logger.info(f"Total schemes:                         {total_schemes}")
    logger.info(f"Central national schemes:              {central_schemes}")
    logger.info(f"Eligible schemes (Strong):             {len(eligible)}")
    logger.info(f"Possible schemes (More Info Needed):   {len(possible)}")
    logger.info("="*50)
    
    return eligible + possible

def get_next_missing_field(schemes: list, profile: dict) -> str:
    """Finds the next unanswered field to resolve possible matches."""
    possible_matches = []
    norm_prof = normalize_profile(profile)
    for s in schemes:
        res = evaluate_scheme(s, norm_prof)
        if res["status"] == "possible_match":
            possible_matches.append((s, res))
            
    if not possible_matches:
        return None
        
    from collections import Counter
    missing_fields = []
    for s, res in possible_matches:
        for mc in res["missing_criteria"]:
            if mc == "Age confirmation":
                if norm_prof.get("exact_age") is None:
                    missing_fields.append("exact_age")
            elif mc == "Income confirmation":
                pass
            elif mc in ["State of residence", "Gender", "Occupation", "Education level", "Social category"]:
                field_map = {
                    "State of residence": "state",
                    "Gender": "gender",
                    "Occupation": "occupation",
                    "Education level": "education",
                    "Social category": "social_category"
                }
                field_key = field_map[mc]
                if norm_prof.get(field_key) is None:
                    missing_fields.append(field_key)
            else:
                if norm_prof.get(mc) is None:
                    missing_fields.append(mc)
                    
    if not missing_fields:
        return None
        
    counter = Counter(missing_fields)
    most_common = counter.most_common(1)
    if most_common:
        return most_common[0][0]
        
    return None
