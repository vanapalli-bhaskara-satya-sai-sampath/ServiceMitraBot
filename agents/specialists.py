import logging
from typing import Any, Dict, List

from services.eligibility_service import evaluate_scheme, find_matching_schemes

logger = logging.getLogger("agents.specialists")


class SchemeResearchAgent:
    def handle(self, query: str, schemes: List[Dict[str, Any]], limit: int = 5) -> Dict[str, Any]:
        tokens = (query or "").lower().split()
        matches = []
        for scheme in schemes:
            text = " ".join([
                scheme.get("name") or "",
                scheme.get("description") or "",
                scheme.get("category") or "",
            ]).lower()
            score = sum(1 for token in tokens if token in text)
            if score or not tokens:
                matches.append((score, scheme))
        matches.sort(key=lambda x: x[0], reverse=True)
        results = [scheme for _, scheme in matches[:limit]]
        return {"results": results, "count": len(results)}


class EligibilityAgent:
    def handle(self, scheme: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        result = evaluate_scheme(scheme, profile)
        return {"status": result["status"], "score": result["score"], "missing_criteria": result["missing_criteria"]}


class VerificationAgent:
    def handle(self, claims: List[str], evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        issues = []
        if not evidence:
            issues.append("No evidence was retrieved for the claims.")
        for claim in claims:
            if not any(claim.lower() in str(item).lower() for item in evidence):
                issues.append(f"Claim not supported: {claim}")
        return {"supported": not issues, "issues": issues}
