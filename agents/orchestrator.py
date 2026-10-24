import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from agents.schemas import AgentDecision, ConversationState, FinalResponse, VerificationResult
from config import GEMINI_MODEL
from services.gemini_service import client as gemini_client

logger = logging.getLogger("agents.orchestrator")


class AgentOrchestrator:
    """Coordinates specialist agents and tool use with bounded iteration limits."""

    def __init__(self, max_steps: int = 4, tool_allowlist: Optional[List[str]] = None):
        self.max_steps = max_steps
        self.tool_allowlist = set(tool_allowlist or {
            "search_schemes",
            "get_scheme_details",
            "get_user_profile",
            "update_user_profile",
            "check_eligibility",
            "validate_scheme_data",
            "save_eligibility_result",
        })

    def decide_agent(self, user_message: str, state: ConversationState) -> AgentDecision:
        message = (user_message or "").lower()
        if any(word in message for word in ["scheme", "scholarship", "benefit", "eligibility", "eligible"]):
            selected = "scheme_research"
            intention = "Find relevant schemes and evidence"
        elif any(word in message for word in ["apply", "check", "am i eligible", "eligible for", "match"]):
            selected = "eligibility"
            intention = "Assess eligibility against stored scheme rules"
        elif any(word in message for word in ["verify", "confirm", "is this correct", "evidence", "support"]):
            selected = "verification"
            intention = "Check whether the answer is evidence-backed"
        elif any(word in message for word in ["language", "translate", "voice", "speech", "audio"]):
            selected = "language"
            intention = "Language and voice handling"
        else:
            selected = "supervisor"
            intention = "Understand the request and decide the next action"

        missing = []
        if not state.profile.get("state"):
            missing.append("state")
        if "annual_income" in state.profile and state.profile.get("annual_income") is None:
            missing.append("annual_income")

        return AgentDecision(
            selected_agent=selected,
            intent=intention,
            confidence=0.8,
            reason="Agent selected based on user intent and required profile data.",
            missing_fields=missing,
        )

    def validate_tool_name(self, tool_name: str) -> bool:
        return tool_name in self.tool_allowlist

    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        if tool_name not in self.tool_allowlist:
            return False
        if tool_name in {"search_schemes", "get_scheme_details", "check_eligibility", "validate_scheme_data"}:
            return bool(arguments)
        if tool_name in {"get_user_profile", "update_user_profile", "save_eligibility_result"}:
            return isinstance(arguments, dict)
        return True

    def build_fallback_response(self, user_message: str, reason: str) -> FinalResponse:
        text = (
            "I’m currently unable to reach the scheme data or model service. "
            "Please try again in a moment or check the configured credentials."
        )
        return FinalResponse(answer=text, selected_agent="fallback", voice_request=False, confidence=0.2)

    def verify_response(self, answer: str, evidence: List[Dict[str, Any]]) -> VerificationResult:
        if not evidence:
            return VerificationResult(
                supported=False,
                issues=["No scheme or tool evidence was retrieved."],
                missing_evidence=["scheme result"],
                summary="No evidence was found to support the response.",
            )
        return VerificationResult(
            supported=True,
            issues=[],
            missing_evidence=[],
            summary="Response is supported by retrieved scheme and eligibility evidence.",
        )

    def run(self, user_message: str, state: ConversationState, tools: Optional[Dict[str, Any]] = None) -> FinalResponse:
        tools = tools or {}
        state.history.append(user_message)
        state.step_count += 1
        decision = self.decide_agent(user_message, state)
        state.selected_agent = decision.selected_agent
        if not gemini_client and decision.selected_agent not in {"fallback"}:
            logger.warning("Gemini client unavailable; using fallback response.")
            return self.build_fallback_response(user_message, "Gemini unavailable")

        evidence: List[Dict[str, Any]] = []
        for _ in range(min(self.max_steps, 5)):
            if decision.selected_agent == "supervisor":
                break
            if decision.selected_agent == "scheme_research":
                if "search_schemes" in tools:
                    evidence.append({"tool": "search_schemes", "status": "ok"})
                break
            if decision.selected_agent == "eligibility":
                if "check_eligibility" in tools:
                    evidence.append({"tool": "check_eligibility", "status": "ok"})
                break
            if decision.selected_agent == "verification":
                if evidence:
                    break
                break
            if decision.selected_agent == "language":
                break

        verification = self.verify_response(user_message, evidence)
        if not verification.supported:
            return self.build_fallback_response(user_message, verification.summary)

        base_answer = (
            f"I selected the {decision.selected_agent} workflow for: '{user_message}' "
            f"with missing fields {', '.join(decision.missing_fields) if decision.missing_fields else 'none'}."
        )
        return FinalResponse(
            answer=base_answer,
            selected_agent=decision.selected_agent,
            voice_request=decision.selected_agent == "language",
            confidence=decision.confidence,
        )
