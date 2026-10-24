import os
import sys
import json

# Add parent directory to path so we can import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.eligibility_service import (
    evaluate_scheme,
    find_matching_schemes,
    is_scheme_applicable_to_state,
    normalize_profile,
    normalize_state,
    normalize_category,
    normalize_scheme_data
)

# Load actual schemes if they exist
SCHEMES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "schemes.json")
ALL_SCHEMES = []
if os.path.exists(SCHEMES_PATH):
    with open(SCHEMES_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        if isinstance(raw_data, dict) and "schemes" in raw_data:
            ALL_SCHEMES = raw_data["schemes"]
        else:
            ALL_SCHEMES = raw_data

print(f"Loaded {len(ALL_SCHEMES)} actual schemes for regression checks.")

def run_tests():
    print("Starting Eligibility Engine Regression Tests...")
    print("="*60)
    
    # ------------------------------------------------------------------
    # MOCK SCHEMES FOR DETERMINISTIC TESTING
    # ------------------------------------------------------------------
    mock_national_scheme = {
        "id": "mock-national",
        "name": "National Scholarship Scheme",
        "category": "Education & Learning",
        "eligibility": {
            "age_min": 18,
            "age_max": 30,
            "gender": [],
            "occupation": ["Student"],
            "income_max": 300000,
            "state": [],
            "education": ["UG", "PG"],
            "social_category": []
        },
        "applicability": {
            "scope": "central",
            "states": []
        }
    }
    
    mock_gujarat_scheme = {
        "id": "mock-gujarat",
        "name": "Gujarat Youth Support",
        "category": "Education & Learning",
        "eligibility": {
            "age_min": 18,
            "age_max": 35,
            "gender": [],
            "occupation": [],
            "income_max": None,
            "state": ["Gujarat"],
            "education": [],
            "social_category": []
        },
        "applicability": {
            "scope": "state",
            "states": ["Gujarat"]
        }
    }
    
    mock_ne_scheme = {
        "id": "mock-ne-regional",
        "name": "Northeast Development Plan",
        "category": "Agriculture, Rural & Environment",
        "description": "Applicable for farmers in North Eastern states including Assam.",
        "eligibility": {
            "age_min": None,
            "age_max": None,
            "gender": [],
            "occupation": ["Farmer"],
            "income_max": None,
            "state": [],
            "education": [],
            "social_category": []
        },
        "applicability": {
            "scope": "central",
            "states": []
        }
    }

    # ------------------------------------------------------------------
    # TEST 1: AP PG Student
    # ------------------------------------------------------------------
    print("TEST 1: AP PG Student - National scheme should match, Gujarat scheme should be excluded")
    profile_1 = {
        "age": "26_35",
        "gender": "Female",
        "occupation": "Student",
        "education": "PG",
        "social_category": "OBC",
        "state": "Andhra Pradesh"
    }
    
    # Check geographic applicability
    geo_ap = is_scheme_applicable_to_state(mock_gujarat_scheme, "Andhra Pradesh")
    assert geo_ap == "not_applicable", f"Expected Gujarat scheme to be not applicable to AP, got {geo_ap}"
    
    res_1_nat = evaluate_scheme(mock_national_scheme, profile_1)
    # Since age range is 26_35 and scheme age_max is 30, it should be possible_match (overlap)
    assert res_1_nat["status"] == "possible_match", f"Expected possible_match for national scheme due to age overlap, got {res_1_nat['status']}"
    
    print("[OK] TEST 1 passed.")
    print("-" * 40)
    
    # ------------------------------------------------------------------
    # TEST 2: Gujarat ST User
    # ------------------------------------------------------------------
    print("TEST 2: Gujarat ST User - Gujarat scheme should match")
    profile_2 = {
        "age": "26_35",
        "gender": "Female",
        "occupation": "Student",
        "education": "PG",
        "social_category": "ST",
        "state": "Gujarat"
    }
    geo_gj = is_scheme_applicable_to_state(mock_gujarat_scheme, "Gujarat")
    assert geo_gj == "applicable", f"Expected Gujarat scheme to be applicable to Gujarat, got {geo_gj}"
    
    res_2_gj = evaluate_scheme(mock_gujarat_scheme, profile_2)
    assert res_2_gj["status"] == "eligible", f"Expected Gujarat scheme to be eligible, got {res_2_gj['status']}"
    print("[OK] TEST 2 passed.")
    print("-" * 40)
    
    # ------------------------------------------------------------------
    # TEST 3: Age clearly above maximum
    # ------------------------------------------------------------------
    print("TEST 3: Age clearly above maximum -> ineligible")
    profile_3 = {
        "age": "36_50", # 36 to 50
        "state": "Gujarat"
    }
    # Scheme age_max = 30
    res_3 = check_age_match = evaluate_scheme(mock_national_scheme, profile_3)
    assert res_3["status"] == "ineligible", f"Expected ineligible for age 36_50 against max 30, got {res_3['status']}"
    print("[OK] TEST 3 passed.")
    print("-" * 40)
    
    # ------------------------------------------------------------------
    # TEST 4: Age range overlap
    # ------------------------------------------------------------------
    print("TEST 4: Age range overlaps max -> possible_match")
    profile_4 = {
        "age": "26_35", # 26 to 35
        "state": "Gujarat"
    }
    # Scheme age_max = 30
    res_4 = evaluate_scheme(mock_national_scheme, profile_4)
    assert res_4["status"] == "possible_match", f"Expected possible_match for age 26_35 against max 30, got {res_4['status']}"
    print("[OK] TEST 4 passed.")
    print("-" * 40)
    
    # ------------------------------------------------------------------
    # TEST 5: Education PG matches minimum UG
    # ------------------------------------------------------------------
    print("TEST 5: Education PG against minimum UG -> eligible")
    # Let's verify education hierarchy: PG (level 6) >= UG (level 5)
    # We will construct a scheme requiring minimum level of UG
    scheme_ug_min = {
        "id": "scheme-ug-min",
        "name": "UG Min Scheme",
        "category": "Education & Learning",
        "eligibility": {
            "age_min": None, "age_max": None, "gender": [], "occupation": [],
            "income_max": None, "state": [], "education": ["UG"], "social_category": []
        },
        "applicability": {"scope": "central", "states": []}
    }
    profile_5 = {
        "education": "PG",
        "state": "Gujarat"
    }
    res_5 = evaluate_scheme(scheme_ug_min, profile_5)
    assert res_5["status"] == "eligible", f"Expected PG user to match UG requirement, got {res_5['status']}"
    print("[OK] TEST 5 passed.")
    print("-" * 40)
    
    # ------------------------------------------------------------------
    # TEST 6: Education 12th fails minimum PG
    # ------------------------------------------------------------------
    print("TEST 6: Education 12th against minimum PG -> ineligible")
    scheme_pg_min = {
        "id": "scheme-pg-min",
        "name": "PG Min Scheme",
        "category": "Education & Learning",
        "eligibility": {
            "age_min": None, "age_max": None, "gender": [], "occupation": [],
            "income_max": None, "state": [], "education": ["PG"], "social_category": []
        },
        "applicability": {"scope": "central", "states": []}
    }
    profile_6 = {
        "education": "12th",
        "state": "Gujarat"
    }
    res_6 = evaluate_scheme(scheme_pg_min, profile_6)
    assert res_6["status"] == "ineligible", f"Expected 12th user to fail PG requirement, got {res_6['status']}"
    print("[OK] TEST 6 passed.")
    print("-" * 40)
    
    # ------------------------------------------------------------------
    # TEST 7: Central + National scheme is applicable to AP
    # ------------------------------------------------------------------
    print("TEST 7: Central + National applicable to AP")
    geo_ap_nat = is_scheme_applicable_to_state(mock_national_scheme, "Andhra Pradesh")
    assert geo_ap_nat == "applicable", f"Expected mock-national to be applicable to AP, got {geo_ap_nat}"
    print("[OK] TEST 7 passed.")
    print("-" * 40)
    
    # ------------------------------------------------------------------
    # TEST 8: Central + regional NE scheme is not applicable to AP
    # ------------------------------------------------------------------
    print("TEST 8: Central + Northeast regional is not applicable to AP")
    geo_ap_ne = is_scheme_applicable_to_state(mock_ne_scheme, "Andhra Pradesh")
    assert geo_ap_ne == "not_applicable", f"Expected NE scheme to be not applicable to AP, got {geo_ap_ne}"
    
    # But should be applicable to Assam
    geo_as_ne = is_scheme_applicable_to_state(mock_ne_scheme, "Assam")
    assert geo_as_ne == "applicable", f"Expected NE scheme to be applicable to Assam, got {geo_as_ne}"
    print("[OK] TEST 8 passed.")
    print("-" * 40)
    
    # ------------------------------------------------------------------
    # TEST 9: Income Rs. 5-10 Lakh against max Rs. 2 Lakh
    # ------------------------------------------------------------------
    print("TEST 9: Income Rs. 5-10 Lakh against max Rs. 2 Lakh -> ineligible")
    scheme_inc_2l = {
        "id": "scheme-inc-2l",
        "name": "Low Income Scheme",
        "category": "Education & Learning",
        "eligibility": {
            "age_min": None, "age_max": None, "gender": [], "occupation": [],
            "income_max": 200000, "state": [], "education": [], "social_category": []
        },
        "applicability": {"scope": "central", "states": []}
    }
    profile_9 = {
        "annual_income": "5_10l", # 5 to 10 Lakh
        "state": "Gujarat"
    }
    res_9 = evaluate_scheme(scheme_inc_2l, profile_9)
    assert res_9["status"] == "ineligible", f"Expected 5-10l income user to be ineligible for max 2l scheme, got {res_9['status']}"
    print("[OK] TEST 9 passed.")
    print("-" * 40)
    
    # ------------------------------------------------------------------
    # TEST 10: Income Rs. 1-2 Lakh against max Rs. 2 Lakh
    # ------------------------------------------------------------------
    print("TEST 10: Income Rs. 1-2 Lakh against max Rs. 2 Lakh -> eligible")
    profile_10 = {
        "annual_income": "1_2l", # 1 to 2 Lakh
        "state": "Gujarat"
    }
    res_10 = evaluate_scheme(scheme_inc_2l, profile_10)
    assert res_10["status"] == "eligible", f"Expected 1-2l income user to be eligible for max 2l scheme, got {res_10['status']}"
    print("[OK] TEST 10 passed.")
    print("-" * 40)

    # ------------------------------------------------------------------
    # REGRESSION TEST: Halpati Housing Scheme
    # ------------------------------------------------------------------
    print("REGRESSION TEST: Halpati Housing Scheme - Gujarat-only ST scheme")
    halpati_scheme = None
    for s in ALL_SCHEMES:
        if s["id"] == "gujarat-halpati-housing" or "halpati" in s["name"].lower():
            halpati_scheme = s
            break
            
    if halpati_scheme:
        # Check AP user
        res_ap_halpati = evaluate_scheme(halpati_scheme, {
            "age": "26_35",
            "gender": "Female",
            "occupation": "Student",
            "education": "PG",
            "social_category": "ST",
            "state": "Andhra Pradesh"
        })
        assert res_ap_halpati["status"] == "ineligible", f"AP user must be ineligible for Halpati Housing, got {res_ap_halpati['status']}"
        
        # Check Gujarat user
        res_gj_halpati = evaluate_scheme(halpati_scheme, {
            "age": "26_35",
            "gender": "Female",
            "occupation": "Student",
            "education": "PG",
            "social_category": "ST",
            "state": "Gujarat"
        })
        assert res_gj_halpati["status"] in ["eligible", "possible_match"], f"Gujarat ST user should be potential match for Halpati, got {res_gj_halpati['status']}"
        print("[OK] Halpati Housing regression check passed.")
    else:
        print("[WARNING] Halpati Housing scheme not found in actual schemes.json database. Skipping regression check.")
    print("-" * 40)

    # ------------------------------------------------------------------
    # REGRESSION TEST: PG Indira Gandhi Scholarship
    # ------------------------------------------------------------------
    print("REGRESSION TEST: PG Indira Gandhi Scholarship For Single Girl Child")
    ig_scholarship = None
    for s in ALL_SCHEMES:
        if s["id"] == "pg-indira-gandhi-scholarship-sgc" or "single girl" in s["name"].lower():
            ig_scholarship = s
            break
            
    if ig_scholarship:
        normalized_ig = normalize_scheme_data(ig_scholarship)
        print("DEBUG Normalized IG Scholarship:")
        print(json.dumps(normalized_ig["eligibility"], indent=2))
        res_ap_ig = evaluate_scheme(ig_scholarship, {
            "age": "26",
            "gender": "Female",
            "occupation": "Student",
            "education": "PG",
            "state": "Andhra Pradesh"
        })
        assert res_ap_ig["status"] == "possible_match", f"Expected possible_match for AP female PG student, got {res_ap_ig['status']}"
        assert "single_girl_child" in res_ap_ig["missing_criteria"], f"Expected 'single_girl_child' to be in missing criteria, got {res_ap_ig['missing_criteria']}"
        
        res_male_ig = evaluate_scheme(ig_scholarship, {
            "age": "26",
            "gender": "Male",
            "occupation": "Student",
            "education": "PG",
            "state": "Andhra Pradesh"
        })
        assert res_male_ig["status"] == "ineligible", f"Expected male user to be ineligible for PG IG Scholarship, got {res_male_ig['status']}"
        
        res_age31_ig = evaluate_scheme(ig_scholarship, {
            "age": "31",
            "gender": "Female",
            "occupation": "Student",
            "education": "PG",
            "state": "Andhra Pradesh"
        })
        assert res_age31_ig["status"] == "ineligible", f"Expected age 31 user to be ineligible (max 30), got {res_age31_ig['status']}"
        print("[OK] PG Indira Gandhi Scholarship regression check passed.")
    else:
        print("[WARNING] PG Indira Gandhi Scholarship not found in actual schemes.json database. Skipping regression check.")
    
    print("="*60)
    print("All Regression Tests Passed successfully!")

if __name__ == "__main__":
    run_tests()
