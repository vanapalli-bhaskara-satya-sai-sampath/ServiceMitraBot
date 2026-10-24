from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AgentDecision(BaseModel):
    selected_agent: Literal["supervisor", "scheme_research", "eligibility", "verification", "language", "fallback"]
    intent: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str
    missing_fields: List[str] = Field(default_factory=list)


class SchemeSearchResult(BaseModel):
    query: str
    results: List[Dict[str, Any]] = Field(default_factory=list)
    source_count: int = 0


class EligibilityAssessment(BaseModel):
    status: Literal["eligible", "ineligible", "possible_match", "insufficient_information"]
    scheme_id: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)
    matched_criteria: List[str] = Field(default_factory=list)
    missing_criteria: List[str] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=1.0)


class VerificationResult(BaseModel):
    supported: bool
    issues: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    summary: str = ""


class FinalResponse(BaseModel):
    answer: str
    selected_agent: str = "supervisor"
    voice_request: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ConversationState(BaseModel):
    user_id: str
    language: str = "en-IN"
    intent: str = "unknown"
    selected_agent: str = "supervisor"
    profile: Dict[str, Any] = Field(default_factory=dict)
    history: List[str] = Field(default_factory=list)
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    step_count: int = 0


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
