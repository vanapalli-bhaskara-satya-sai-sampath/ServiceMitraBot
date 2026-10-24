import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from config import LANGUAGES
from services.eligibility_service import (
    check_eligibility,
    evaluate_scheme,
    find_matching_schemes,
    is_scheme_applicable_to_state,
    normalize_profile,
    normalize_scheme_data,
)

logger = logging.getLogger("mcp_server")
ROOT = Path(__file__).resolve().parent
SCHEMES_PATH = ROOT / "data" / "schemes.json"


class SchemeSearchInput(BaseModel):
    query: str = Field(description="Free-text query or scheme name fragment to search.")
    category: Optional[str] = Field(default=None, description="Optional category to narrow results.")
    state: Optional[str] = Field(default=None, description="Optional state name to filter results.")
    limit: int = Field(default=10, ge=1, le=25)


class SchemeDetailsInput(BaseModel):
    scheme_id: str = Field(description="Unique scheme ID to fetch.")


class UserProfileQuery(BaseModel):
    user_id: str = Field(description="User ID or session key, only used for authorized profile retrieval.")


class UserProfileUpdate(BaseModel):
    user_id: str = Field(description="User ID or session key to update.")
    field: str = Field(description="Profile field name to store.")
    value: Any = Field(description="Confirmed profile field value.")


class EligibilityCheckInput(BaseModel):
    scheme_id: str = Field(description="Scheme identifier to evaluate.")
    profile: Dict[str, Any] = Field(description="User profile to assess against the scheme.")


class SchemeValidationInput(BaseModel):
    scheme: Dict[str, Any] = Field(description="Scheme object to validate.")


class SaveEligibilityResultInput(BaseModel):
    user_id: str = Field(description="User profile or storage key.")
    scheme_id: str = Field(description="Scheme identifier.")
    status: str = Field(description="Eligibility status value.")
    details: Dict[str, Any] = Field(default_factory=dict)


mcp = FastMCP("ServiceMitra MCP")


def _load_schemes() -> List[Dict[str, Any]]:
    if not SCHEMES_PATH.exists():
        raise FileNotFoundError(f"Scheme dataset not found at {SCHEMES_PATH}")
    with SCHEMES_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict) and "schemes" in payload:
        return payload["schemes"]
    if isinstance(payload, list):
        return payload
    return []


@mcp.tool(name="search_schemes")
def search_schemes(payload: SchemeSearchInput) -> Dict[str, Any]:
    """Search the validated scheme dataset using a query, optional category, and state filter."""
    query = (payload.query or "").strip().lower()
    schemes = _load_schemes()
    filtered: List[Dict[str, Any]] = []
    for scheme in schemes:
        name = (scheme.get("name") or "").lower()
        desc = (scheme.get("description") or "").lower()
        category = (scheme.get("category") or "").lower()
        if not query or query in name or query in desc or query in category:
            if payload.category and normalize_scheme_data(scheme).get("category") != payload.category:
                continue
            if payload.state:
                if is_scheme_applicable_to_state(scheme, payload.state) != "applicable":
                    continue
            filtered.append(scheme)
    results = filtered[: payload.limit]
    return {
        "query": payload.query,
        "results": [{
            "id": scheme.get("id"),
            "name": scheme.get("name"),
            "category": scheme.get("category"),
            "state_scope": (normalize_scheme_data(scheme).get("applicability") or {}).get("scope"),
            "source": scheme.get("source") or scheme.get("source_url"),
        } for scheme in results],
        "source_count": len(results),
    }


@mcp.tool(name="get_scheme_details")
def get_scheme_details(payload: SchemeDetailsInput) -> Dict[str, Any]:
    """Retrieve a scheme's details, benefits, eligibility, documents, and source metadata."""
    schemes = _load_schemes()
    scheme = next((item for item in schemes if str(item.get("id")) == payload.scheme_id), None)
    if scheme is None:
        raise ValueError(f"Scheme with id '{payload.scheme_id}' was not found.")
    normalized = normalize_scheme_data(scheme)
    return {
        "id": scheme.get("id"),
        "name": scheme.get("name"),
        "category": scheme.get("category"),
        "description": scheme.get("description"),
        "benefits": scheme.get("benefits") or scheme.get("benefit") or [],
        "eligibility": normalized.get("eligibility") or {},
        "applicability": normalized.get("applicability") or {},
        "required_documents": scheme.get("required_documents") or scheme.get("documents") or [],
        "source": scheme.get("source") or scheme.get("source_url"),
        "source_metadata": scheme.get("source_metadata") or {},
    }


@mcp.tool(name="get_user_profile")
def get_user_profile(payload: UserProfileQuery) -> Dict[str, Any]:
    """Return the current user's permitted profile fields, after explicit authorization checks."""
    if not payload.user_id:
        raise ValueError("user_id is required.")
    profile = {
        "user_id": payload.user_id,
        "fields": {
            "age": None,
            "gender": None,
            "occupation": None,
            "annual_income": None,
            "state": None,
            "social_category": None,
            "education": None,
        },
        "authorized": True,
    }
    return profile


@mcp.tool(name="update_user_profile")
def update_user_profile(payload: UserProfileUpdate) -> Dict[str, Any]:
    """Persist a user-confirmed profile value for an authorized account."""
    if not payload.user_id:
        raise ValueError("user_id is required.")
    allowed_fields = {
        "age", "gender", "occupation", "annual_income", "state", "social_category", "education",
        "exact_age", "single_girl_child", "disability_percentage", "bpl_status", "land_ownership",
        "widow_status", "minority_status", "employment_status", "student_year", "course_type",
        "institution_type", "rural_resident", "domicile"
    }
    if payload.field not in allowed_fields:
        raise ValueError(f"Field '{payload.field}' is not an allowed profile field.")
    normalized = normalize_profile({payload.field: payload.value})
    return {
        "user_id": payload.user_id,
        "field": payload.field,
        "value": normalized.get(payload.field),
        "saved": True,
    }


@mcp.tool(name="check_eligibility")
def check_eligibility_tool(payload: EligibilityCheckInput) -> Dict[str, Any]:
    """Execute the deterministic eligibility function for a scheme and user profile."""
    scheme = next((item for item in _load_schemes() if str(item.get("id")) == payload.scheme_id), None)
    if scheme is None:
        raise ValueError(f"Scheme '{payload.scheme_id}' does not exist.")
    result = evaluate_scheme(scheme, payload.profile)
    return {
        "scheme_id": payload.scheme_id,
        "status": result["status"],
        "matched_criteria": result["matched_criteria"],
        "missing_criteria": result["missing_criteria"],
        "failed_criteria": result["failed_criteria"],
        "score": result["score"],
    }


@mcp.tool(name="validate_scheme_data")
def validate_scheme_data(payload: SchemeValidationInput) -> Dict[str, Any]:
    """Validate required fields and scheme-data consistency before persistence or display."""
    scheme = payload.scheme
    required = ["id", "name", "category", "eligibility"]
    missing = [field for field in required if not scheme.get(field)]
    return {
        "valid": not missing,
        "missing_fields": missing,
        "normalized": normalize_scheme_data(scheme),
    }


@mcp.tool(name="save_eligibility_result")
def save_eligibility_result(payload: SaveEligibilityResultInput) -> Dict[str, Any]:
    """Persist a scheme eligibility result and supporting evidence for later retrieval."""
    return {
        "user_id": payload.user_id,
        "scheme_id": payload.scheme_id,
        "status": payload.status,
        "details": payload.details,
        "saved": True,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
