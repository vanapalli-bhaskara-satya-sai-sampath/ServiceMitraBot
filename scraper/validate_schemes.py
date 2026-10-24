import os
import json
import urllib.parse
import sys

# Add parent directory to path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import STATES

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SCHEMES_FILE = os.path.join(DATA_DIR, "schemes.json")

def validate_schemes():
    # Validates ServiceMitra schemes dataset compiled from UMANG portal.
    if not os.path.exists(SCHEMES_FILE):
        print(f"ERROR: schemes.json not found at {SCHEMES_FILE}")
        sys.exit(1)
        
    with open(SCHEMES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if isinstance(data, dict) and "schemes" in data:
        schemes = data["schemes"]
        metadata = data.get("metadata", {})
        print(f"Loaded schemes.json with metadata: {metadata}")
    else:
        schemes = data
        print("Loaded schemes.json (Legacy plain list format)")
        
    total_count = len(schemes)
    
    unique_ids = set()
    unique_urls = set()
    
    valid_count = 0
    warning_count = 0
    invalid_count = 0
    
    warnings_list = []
    errors_list = []
    
    for idx, s in enumerate(schemes):
        errors = []
        warnings = []
        
        # 1. Check ID
        s_id = s.get("id")
        if not s_id:
            errors.append("Missing scheme ID")
        else:
            if s_id in unique_ids:
                errors.append(f"Duplicate scheme ID: '{s_id}'")
            unique_ids.add(s_id)
            
        # 2. Check Name
        name = s.get("name")
        if not name or not isinstance(name, str) or not name.strip():
            errors.append("Missing or invalid scheme Name")
            
        # 3. Check Category
        category = s.get("category")
        if not category or not isinstance(category, str) or not category.strip():
            errors.append("Missing or invalid Category")
            
        # 4. Check Source URL
        source_url = s.get("source_url")
        if not source_url:
            errors.append("Missing source_url")
        else:
            if source_url in unique_urls:
                warnings.append(f"Duplicate source_url: '{source_url}'")
            unique_urls.add(source_url)
            
            parsed = urllib.parse.urlparse(source_url)
            if not parsed.scheme or not parsed.netloc:
                errors.append(f"Malformed source_url: '{source_url}'")
                
        # 5. Check Applicability state names and contradictions
        applicability = s.get("applicability") or {}
        scope = applicability.get("scope")
        applicable_states = applicability.get("states") or []
        
        if not scope:
            warnings.append("Missing applicability scope")
        else:
            if scope not in ["central", "state", "multi_state", "unknown"]:
                errors.append(f"Invalid applicability scope value: '{scope}'")
                
            if scope == "central" and len(applicable_states) > 0:
                warnings.append(f"Contradictory state data: scope is 'central' but 'states' is not empty: {applicable_states}")
                
            if scope == "state" and len(applicable_states) == 0:
                errors.append("Contradictory state data: scope is 'state' but 'states' list is empty")
                
            if scope == "state" and len(applicable_states) > 1:
                warnings.append(f"scope is 'state' but multiple states listed: {applicable_states}")
                
            # Verify state names against config.STATES list
            from services.eligibility_service import normalize_state
            for st in applicable_states:
                if normalize_state(st) not in STATES:
                    errors.append(f"Invalid state name in applicability: '{st}' (not in canonical states list)")
                    
            # Check for suspicious geographic restrictions in eligibility text
            elig_text_low = (s.get("eligibility_text") or "").lower()
            desc_text_low = (s.get("description") or "").lower()
            title_text_low = (s.get("name") or "").lower()
            combined_text = title_text_low + " " + desc_text_low + " " + elig_text_low
            
            if scope == "central" and len(applicable_states) == 0:
                for st in STATES:
                    st_low = st.lower()
                    if f"residents of {st_low}" in combined_text or f"residing in {st_low}" in combined_text:
                        warnings.append(f"Potential geographic contradiction: scope is 'central' but text restricts to '{st}' residency")
                        
                ne_kws = ["north eastern", "north-eastern", "northeast", "north east region"]
                if any(kw in combined_text for kw in ne_kws):
                    warnings.append("Potential regional classification: scope is 'central' but text mentions North Eastern states")
                    
        # 6. Check malformed eligibility fields
        eligibility = s.get("eligibility") or {}
        
        # Helper to check type
        def check_field_type(field, expected_type, nullable=True):
            val = eligibility.get(field)
            if val is None:
                if not nullable:
                    errors.append(f"Eligibility field '{field}' cannot be null")
            else:
                if not isinstance(val, expected_type):
                    type_name = expected_type.__name__ if hasattr(expected_type, '__name__') else str(expected_type)
                    errors.append(f"Eligibility field '{field}' must be of type {type_name}, got {type(val).__name__}")
                    
        check_field_type("age_min", (int, float))
        check_field_type("age_max", (int, float))
        check_field_type("income_max", (int, float))
        check_field_type("gender", list)
        check_field_type("occupation", list)
        check_field_type("state", list)
        check_field_type("education", list)
        check_field_type("social_category", list)
        
        # Tally results
        scheme_label = f"#{idx} ({s_id or 'No ID'}: '{name or 'No Name'}')"
        if errors:
            invalid_count += 1
            errors_list.append(f"INVALID: {scheme_label}\n  - " + "\n  - ".join(errors))
        elif warnings:
            warning_count += 1
            valid_count += 1
            warnings_list.append(f"WARNING: {scheme_label}\n  - " + "\n  - ".join(warnings))
        else:
            valid_count += 1
            
    # Output results
    print("\n" + "="*50)
    print("================ SCHEMA VALIDATION ================")
    print("="*50)
    print(f"Total schemes evaluated: {total_count}")
    print(f"Valid schemes:           {valid_count} (including warnings)")
    print(f"Warnings:                {warning_count}")
    print(f"Invalid schemes:         {invalid_count}")
    print("="*50)
    
    if warnings_list:
        print("\nWarnings Details:")
        for w in warnings_list[:15]:  # show up to 15
            print(w)
        if len(warnings_list) > 15:
            print(f"... and {len(warnings_list) - 15} more warnings.")
            
    if errors_list:
        print("\nErrors Details:")
        for e in errors_list[:15]:  # show up to 15
            print(e)
        if len(errors_list) > 15:
            print(f"... and {len(errors_list) - 15} more errors.")
            
    print("="*50 + "\n")
    
    if invalid_count > 0:
        print(f"FAIL: Schema validation failed. {invalid_count} schemes are invalid.")
        return False
    else:
        print("SUCCESS: All schemes passed schema validation!")
        return True

if __name__ == "__main__":
    success = validate_schemes()
    sys.exit(0 if success else 1)
