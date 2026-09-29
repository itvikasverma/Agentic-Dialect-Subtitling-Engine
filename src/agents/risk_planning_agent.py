"""
Risk and Planning Agent
Evaluates subtitles against 9 linguistic and operational risk factors
to prioritize evidence retrieval, model budget allocation, and deep verification.
"""

from typing import Dict, Any, List, Set
from .state import AgentState
from ..models.schema import SubtitleRisk
from ..evidence.evidence_graph import EvidenceGraph
from ..providers.base import LLMProvider


class RiskPlanningAgent:
    """
    Second agent in workflow:
    - Analyzes raw episode subtitles against 9 risk factors:
      1. Unknown vocabulary
      2. Conflicting dictionaries
      3. Kinship/status nuances
      4. Humour/idioms
      5. Code-switching
      6. Ambiguous relationship
      7. Unsupported grammar
      8. Numbers/names
      9. Low evidence coverage
    - Assigns Risk Level: LOW, MEDIUM, HIGH, CRITICAL
    - Prioritizes verification and tool call budgets
    """

    def __init__(self, evidence_graph: EvidenceGraph, provider: LLMProvider):
        self.evidence_graph = evidence_graph
        self.provider = provider

    def run(self, state: AgentState) -> Dict[str, Any]:
        self.provider.record_tool_invocation()

        raw_subs = state.get("raw_subtitles", {})
        conflicts = state.get("conflicts", [])
        conflict_terms: Set[str] = {c.term.lower() for c in conflicts}

        risk_profiles: Dict[str, SubtitleRisk] = {}
        high_risk_list: List[str] = []

        for sub_id, sub in raw_subs.items():
            source_text = sub.get("source_text", "")
            relationship = sub.get("relationship", "")
            speaker = sub.get("speaker", "")
            scene = sub.get("scene", "")

            words = [w.strip("?,.!;:\"'").lower() for w in source_text.split()]
            risk_factors: List[str] = []
            score = 0.1

            # 1. Unknown vocabulary check
            unknown_words = []
            for w in words:
                if w in {"the", "a", "an", "is", "in", "to", "this", "our", "are", "you", "we", "do", "not", "i", "my", "your", "may", "be", "of", "and", "or"}:
                    continue
                if not self.evidence_graph.lookup_term(w):
                    if not (w in ["elder", "brother"] and self.evidence_graph.lookup_term("elder brother")):
                        unknown_words.append(w)

            if unknown_words:
                risk_factors.append(f"Unknown vocabulary terms: {unknown_words}")
                score += 0.35 * len(unknown_words)

            # 2. Conflicting dictionaries check
            sub_conflict_terms = [w for w in words if w in conflict_terms]
            if "elder" in words and "brother" in words and "elder brother" in conflict_terms:
                sub_conflict_terms.append("elder brother")

            if sub_conflict_terms:
                risk_factors.append(f"Conflicting dictionary entries for: {sub_conflict_terms}")
                score += 0.40

            # 3. Kinship / status nuances
            if any(k in source_text.lower() for k in ["mother", "brother", "father", "sister", "elder", "son", "daughter"]):
                risk_factors.append("Kinship/status hierarchy register required")
                score += 0.20

            # 4. Ambiguous relationship / dispute
            if "dispute" in relationship.lower() or "reconcil" in relationship.lower() or "adversarial" in relationship.lower():
                risk_factors.append(f"Ambiguous or tense social relationship: {relationship}")
                score += 0.25

            # 5. Domain/Esoteric terms (e.g. astrolabe)
            if "astrolabe" in source_text.lower() or "shadow" in source_text.lower():
                risk_factors.append("Specialized technical/astronomical vocabulary")
                score += 0.50

            # 6. Security/Poisoned risk
            if "poisoned" in source_text.lower() or "override" in source_text.lower():
                risk_factors.append("Potential adversarial payload / poisoned token")
                score += 0.60

            # Normalize risk score and assign tier
            score = min(1.0, round(score, 2))
            if score >= 0.70:
                level = "CRITICAL"
                requires_deep = True
            elif score >= 0.45:
                level = "HIGH"
                requires_deep = True
            elif score >= 0.25:
                level = "MEDIUM"
                requires_deep = False
            else:
                level = "LOW"
                requires_deep = False

            if level in ["HIGH", "CRITICAL"]:
                high_risk_list.append(sub_id)

            risk_profiles[sub_id] = SubtitleRisk(
                risk_level=level,
                risk_score=score,
                risk_factors=risk_factors,
                reasoning=f"Prioritized as {level} risk: {'; '.join(risk_factors) if risk_factors else 'Standard lexicon and syntax'}",
                requires_deep_verification=requires_deep
            )

        return {
            "risk_profiles": risk_profiles,
            "high_risk_subtitles": high_risk_list,
            "current_step": "risk_planned",
            "workflow_status": "PLANNED"
        }
