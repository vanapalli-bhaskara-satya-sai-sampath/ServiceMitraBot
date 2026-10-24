import os
import sys
import json
import time
import argparse
import logging
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Add parent directory to path so we can import config and services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import STATES, SCRAPE_DELAY, MAX_RETRIES, HEADLESS
from services.gemini_service import parse_eligibility_offline

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("umang_scraper")

# Constants
UMANG_API_KEY = os.getenv("UMANG_API_KEY", "hOMSczmhIg32lHy0jJHHW6P2Eg7skS1V9cI3skBc")
LIST_API_URL = "https://cache.umang.gov.in/scheme/core/api/scheme/v1/schemes-list?lang=en"
DETAIL_API_URL = "https://myscheme-prod-api.umangapp.in/schemes/v7/public/schemes?slug={slug}&lang=en"

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "x-api-key": UMANG_API_KEY,
    "accept": "application/json",
    "referer": "https://web.umang.gov.in/"
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
RAW_FILE = os.path.join(RAW_DIR, "umang_raw_schemes.json")
SCHEMES_FILE = os.path.join(DATA_DIR, "schemes.json")
CATEGORIES_FILE = os.path.join(DATA_DIR, "categories.json")
FAILURES_FILE = os.path.join(DATA_DIR, "scrape_failures.json")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

# Helper: Parse markdown list
def parse_markdown_list(md_text):
    if not md_text:
        return []
    lines = md_text.split("\n")
    items = []
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        # Remove bullet points/markers
        if line_strip.startswith(("*", "-", "+", ">")):
            line_strip = line_strip[1:].strip()
        else:
            # Check if it starts with number like "1. ", "2) "
            parts = line_strip.split(".", 1)
            if parts[0].isdigit() and len(parts) > 1:
                line_strip = parts[1].strip()
            else:
                parts = line_strip.split(")", 1)
                if parts[0].isdigit() and len(parts) > 1:
                    line_strip = parts[1].strip()
        
        # Strip markdown formatting
        line_strip = line_strip.replace("**", "").replace("`", "").replace("_", "").strip()
        if line_strip:
            items.append(line_strip)
    return items

# Helper: Normalize category name to match config.py sectors
def normalize_category(categories_list):
    if not categories_list:
        return "Social Welfare & Empowerment"  # Default fallback
    
    canonical_sectors = [
        "Education & Learning",
        "Agriculture, Rural & Environment",
        "Health & Wellness",
        "Social Welfare & Empowerment",
        "Skills & Employment",
        "Business & Entrepreneurship"
    ]
    
    for cat in categories_list:
        cat_clean = cat.replace(" ", "").replace(",", "").lower()
        for sect in canonical_sectors:
            sect_clean = sect.replace(" ", "").replace(",", "").lower()
            if cat_clean == sect_clean or sect_clean in cat_clean or cat_clean in sect_clean:
                return sect
                
    return categories_list[0].title()

# Helper: Normalize state names to match config.py STATES
def normalize_state(state_name):
    s_clean = state_name.strip().lower()
    if s_clean in ["all", "central", "national", "india"]:
        return "All"
    
    for canonical in STATES:
        c_clean = canonical.lower()
        if c_clean in s_clean or s_clean in c_clean:
            return canonical
        if s_clean.replace("&", "and") in c_clean or c_clean.replace("&", "and") in s_clean:
            return canonical
    return None

# Helper: Classify state applicability
def determine_applicability(beneficiary_states):
    if not beneficiary_states:
        return {"scope": "unknown", "states": []}
    
    normalized_states = []
    is_central = False
    
    for st in beneficiary_states:
        norm = normalize_state(st)
        if norm == "All":
            is_central = True
        elif norm:
            normalized_states.append(norm)
            
    if is_central:
        return {"scope": "central", "states": []}
    elif len(normalized_states) == 1:
        return {"scope": "state", "states": normalized_states}
    elif len(normalized_states) > 1:
        return {"scope": "multi_state", "states": list(set(normalized_states))}
    else:
        return {"scope": "unknown", "states": []}

def run_debug():
    print("========================================")
    print("UMANG SCHEME SCRAPER — DEBUG MODE")
    print("========================================")
    
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Navigating to UMANG Scheme Dashboard...")
        page.goto("https://web.umang.gov.in/landing/scheme/dashboard", wait_until="networkidle")
        
        print(f"Page Title: {page.title()}")
        print(f"Current URL: {page.url}")
        
        # Extract filters / categories if present in DOM
        filters = page.evaluate("""
            () => {
                const arr = [];
                const elList = document.querySelectorAll('.filter-section, .filters, .tag-container');
                for (const el of elList) {
                    arr.push(el.innerText.substring(0, 100));
                }
                return arr.slice(0, 5);
            }
        """)
        print(f"\nDiscovered Categories/Filters from DOM (Top 5):")
        for f in filters:
            print(f" - {repr(f.strip())}")
            
        # Discover scheme links
        links = page.evaluate("""
            () => {
                const arr = [];
                const anchorElements = document.querySelectorAll('a');
                for (const a of anchorElements) {
                    if (a.href.includes('detail') || a.href.includes('scheme')) {
                        arr.push({text: a.innerText, href: a.href});
                    }
                }
                return arr.slice(0, 5);
            }
        """)
        print(f"\nDiscovered Scheme Links from DOM (Top 5):")
        for l in links:
            print(f" - Text: {repr(l['text'].strip())}, Href: {l['href']}")
            
        # Call the public schemes-list API to check connectivity
        print("\nChecking public API endpoints...")
        try:
            res = requests.get(LIST_API_URL, headers=API_HEADERS, timeout=10)
            print(f" - Scheme List API: {LIST_API_URL}")
            print(f" - Status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                total = data.get("data", {}).get("hits", {}).get("summary", {}).get("total", 0)
                items_count = len(data.get("data", {}).get("hits", {}).get("items", []))
                print(f" - Total Schemes Reported by Portal: {total}")
                print(f" - Schemes in First Payload: {items_count}")
        except Exception as e:
            print(f" - Error connecting to Scheme List API: {e}")
            
        browser.close()
        print("========================================\n")

def fetch_all_schemes_list():
    logger.info("Fetching complete scheme list from API...")
    try:
        res = requests.get(LIST_API_URL, headers=API_HEADERS, timeout=15)
        if res.status_code != 200:
            logger.error(f"Failed to fetch scheme list. Status: {res.status_code}")
            return []
        
        data = res.json()
        items = data.get("data", {}).get("hits", {}).get("items", [])
        return items
    except Exception as e:
        logger.error(f"Error fetching scheme list: {e}")
        return []

def fetch_scheme_detail(slug, max_retries=MAX_RETRIES):
    url = DETAIL_API_URL.format(slug=slug)
    for attempt in range(max_retries):
        try:
            res = requests.get(url, headers=API_HEADERS, timeout=15)
            if res.status_code == 200:
                detail_data = res.json()
                if detail_data.get("status") == "Success" and detail_data.get("data") is not None:
                    return detail_data["data"]
            elif res.status_code == 403:
                logger.warning(f"403 Forbidden on slug {slug}. Retrying with delay...")
            time.sleep(SCRAPE_DELAY * (attempt + 1))
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed for slug {slug}: {e}")
            time.sleep(SCRAPE_DELAY * (attempt + 1))
    return None

def scrape_pipeline(limit=None):
    print("========================================")
    print("UMANG SCHEME SCRAPER")
    print("========================================")
    
    # Step 1: Fetch list
    items = fetch_all_schemes_list()
    total_portal_count = len(items)
    print(f"Dashboard loaded.\nTotal Schemes Available: {total_portal_count}")
    
    if not items:
        print("No schemes found. Exiting.")
        return
        
    # Deduplicate categories and states for reporting
    categories_set = set()
    states_set = set()
    for item in items:
        fields = item.get("fields", {})
        for cat in fields.get("schemeCategory", []):
            categories_set.add(cat)
        for st in fields.get("beneficiaryState", []):
            norm_st = normalize_state(st)
            if norm_st and norm_st != "All":
                states_set.add(norm_st)
                
    print(f"Categories discovered: {len(categories_set)}")
    print(f"States discovered: {len(states_set)}")
    print(f"Unique scheme records discovered: {len(items)}")
    print("----------------------------------------")
    
    # Load raw cache to support resume
    raw_cache = {}
    if os.path.exists(RAW_FILE):
        try:
            with open(RAW_FILE, "r", encoding="utf-8") as f:
                raw_cache = json.load(f)
            print(f"Loaded {len(raw_cache)} schemes from raw cache.")
        except Exception as e:
            logger.warning(f"Failed to load raw cache: {e}")
            
    # Load failures
    failures = []
    if os.path.exists(FAILURES_FILE):
        try:
            with open(FAILURES_FILE, "r", encoding="utf-8") as f:
                failures = json.load(f)
        except Exception:
            pass
            
    # Limit if specified
    if limit:
        items = items[:limit]
        print(f"Running in TEST/LIMIT mode. Processing first {limit} schemes.")
        
    scraped_count = 0
    success_count = 0
    failed_urls = []
    
    # Step 2: Fetch details and normalize
    normalized_schemes = []
    
    print("\nScraping details:\n")
    for idx, item in enumerate(items):
        fields = item.get("fields", {})
        slug = fields.get("slug")
        scheme_name = fields.get("schemeName")
        scheme_id = item.get("id")
        
        if not slug:
            logger.warning(f"No slug for scheme ID {scheme_id}. Skipping.")
            continue
            
        try:
            print(f"[{idx+1}/{len(items)}] {scheme_name}")
        except UnicodeEncodeError:
            safe_name = scheme_name.encode("ascii", "ignore").decode("ascii")
            print(f"[{idx+1}/{len(items)}] {safe_name}")
        
        detail_data = None
        # Check cache first
        if slug in raw_cache:
            detail_data = raw_cache[slug]
        else:
            detail_data = fetch_scheme_detail(slug)
            if detail_data:
                raw_cache[slug] = detail_data
                # Save periodically to prevent loss
                if scraped_count % 10 == 0:
                    with open(RAW_FILE, "w", encoding="utf-8") as f:
                        json.dump(raw_cache, f, indent=4, ensure_ascii=False)
            time.sleep(SCRAPE_DELAY)
            
        if not detail_data:
            logger.error(f"Failed to fetch details for slug: {slug}")
            failed_urls.append(DETAIL_API_URL.format(slug=slug))
            continue
            
        success_count += 1
        
        # Extract English contents
        en_content = detail_data.get("en", {})
        basic_details = en_content.get("basicDetails", {})
        scheme_content = en_content.get("schemeContent", {})
        
        desc = scheme_content.get("detailedDescription_md", fields.get("briefDescription", ""))
        benefits = scheme_content.get("benefits_md", "")
        
        # Eligibility description is under eligibilityCriteria block
        elig_text = en_content.get("eligibilityCriteria", {}).get("eligibilityDescription_md", "")
        
        # Structuring eligibility with Gemini
        elig_structured = parse_eligibility_offline(elig_text) if elig_text else {
            "age_min": None,
            "age_max": None,
            "gender": [],
            "occupation": [],
            "income_max": None,
            "state": [],
            "education": [],
            "social_category": []
        }
        
        # Required documents - UMANG details API does not provide a separate documents list field.
        # Fallback to empty list, which is handled gracefully by the bot.
        docs_list = []
        
        # Application steps are under applicationProcess block
        app_process = en_content.get("applicationProcess", [])
        steps_raw = app_process[0].get("process_md", "") if isinstance(app_process, list) and len(app_process) > 0 else ""
        steps_list = parse_markdown_list(steps_raw)
        
        # Official link
        ref_list = scheme_content.get("references", [])
        official_link = ref_list[0].get("url") if ref_list else ""
        if not official_link:
            # Fallback to ministry URL label if available
            nodal_min = basic_details.get("nodalMinistryName", {})
            official_link = nodal_min.get("url", "") if isinstance(nodal_min, dict) else ""
            
        # Help center / FAQ is not present as a separate field, fallback to empty string
        help_center = ""
        
        # State applicability
        beneficiary_states = fields.get("beneficiaryState", [])
        applicability = determine_applicability(beneficiary_states)
        
        normalized_scheme = {
            "id": scheme_id,
            "name": scheme_name,
            "category": normalize_category(fields.get("schemeCategory", [])),
            "description": desc,
            "benefits": benefits,
            "eligibility_text": elig_text,
            "eligibility": elig_structured,
            "required_documents": docs_list,
            "application_steps": steps_list,
            "official_link": official_link,
            "help_center": help_center,
            "applicability": applicability,
            "source_url": DETAIL_API_URL.format(slug=slug)
        }
        normalized_schemes.append(normalized_scheme)
        scraped_count += 1

    # Save final raw cache
    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(raw_cache, f, indent=4, ensure_ascii=False)
        
    # Save failures
    if failed_urls:
        with open(FAILURES_FILE, "w", encoding="utf-8") as f:
            json.dump(failed_urls, f, indent=4, ensure_ascii=False)
            
    # Deduplicate and merge schemes
    merged_schemes = {}
    duplicates_count = 0
    for s in normalized_schemes:
        s_id = s["id"]
        if s_id in merged_schemes:
            # Merge states
            existing = merged_schemes[s_id]
            existing_states = existing["applicability"]["states"]
            new_states = s["applicability"]["states"]
            
            existing_scope = existing["applicability"]["scope"]
            new_scope = s["applicability"]["scope"]
            
            if existing_scope == "central" or new_scope == "central":
                merged_scope = "central"
                merged_states_list = []
            else:
                merged_states_list = list(set(existing_states + new_states))
                if len(merged_states_list) == 1:
                    merged_scope = "state"
                elif len(merged_states_list) > 1:
                    merged_scope = "multi_state"
                else:
                    merged_scope = "unknown"
                    
            existing["applicability"] = {
                "scope": merged_scope,
                "states": merged_states_list
            }
            duplicates_count += 1
        else:
            merged_schemes[s_id] = s
            
    final_schemes_list = list(merged_schemes.values())
    
    # Save output
    output_data = {
        "metadata": {
            "source": "umang.gov.in",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_schemes": len(final_schemes_list)
        },
        "schemes": final_schemes_list
    }
    
    target_file = schemes_test_file = os.path.join(DATA_DIR, "schemes_test.json") if limit else SCHEMES_FILE
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
        
    # Compile category statistics
    cat_counts = {}
    for s in final_schemes_list:
        cat = s["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        
    categories_data = []
    for cat_name, count in cat_counts.items():
        categories_data.append({
            "name": cat_name,
            "scheme_count": count
        })
        
    if not limit:
        with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(categories_data, f, indent=4, ensure_ascii=False)
            
    # Count stats
    with_elig = sum(1 for s in final_schemes_list if s["eligibility_text"])
    without_elig = len(final_schemes_list) - with_elig
    
    central_count = sum(1 for s in final_schemes_list if s["applicability"]["scope"] == "central")
    state_count = sum(1 for s in final_schemes_list if s["applicability"]["scope"] == "state")
    multi_state_count = sum(1 for s in final_schemes_list if s["applicability"]["scope"] == "multi_state")
    unknown_count = sum(1 for s in final_schemes_list if s["applicability"]["scope"] == "unknown")
    
    print("----------------------------------------")
    print("COMPLETED\n")
    print(f"Discovered: {total_portal_count}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(failed_urls)}")
    print(f"Duplicates removed: {duplicates_count}")
    print()
    print(f"With eligibility: {with_elig}")
    print(f"Without eligibility: {without_elig}")
    print()
    print(f"Central: {central_count}")
    print(f"State-specific: {state_count}")
    print(f"Multi-state: {multi_state_count}")
    print(f"Unknown: {unknown_count}")
    print("========================================")
    
    # Check coverage warning
    if not limit and len(final_schemes_list) < total_portal_count:
        missing = total_portal_count - len(final_schemes_list) - duplicates_count
        if missing > 0:
            print(f"\nWARNING:\nThe scraper discovered fewer schemes than the portal reports.\nPortal:\n{total_portal_count}\nScraped:\n{len(final_schemes_list)}\nMissing:\n{missing}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UMANG Scheme Scraper")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode to inspect dashboard browser traffic")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of schemes scraped (for testing)")
    parser.add_argument("--force", action="store_true", help="Force scrape without using cached raw details")
    args = parser.parse_args()
    
    if args.force and os.path.exists(RAW_FILE):
        try:
            os.remove(RAW_FILE)
            logger.info("Cleared raw cache due to --force flag.")
        except Exception as e:
            logger.error(f"Failed to clear raw cache: {e}")
            
    if args.debug:
        run_debug()
    else:
        scrape_pipeline(limit=args.limit)
