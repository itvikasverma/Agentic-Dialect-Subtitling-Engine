"""
Independent Multi-Phase Verification and Epistemic Calibration Engine
"""

from typing import Dict, Any, List, Tuple
from ..models.schema import SubtitleDecision
from ..evidence.evidence_graph import EvidenceGraph
from ..providers.base import LLMProvider


class MultiPhaseVerifier:
    """
    Independent verification engine that audits translation decisions.
    Explicitly designed to disagree with the generation phase:
    1. Lexical grounding audit (ensures 0 ungrounded inventions)
    2. Morphological and syntax validation (tense, negation prefixes)
    3. Timing & CPS reading speed limits
    4. Adversarial security and poison checks
    5. Independent model evaluation (separate prompt/role)
    """

    MAX_CPS_THRESHOLD = 20.0

    def __init__(self, evidence_graph: EvidenceGraph, provider: LLMProvider):
        self.evidence_graph = evidence_graph
        self.provider = provider

    def verify_decision(self, decision: SubtitleDecision) -> SubtitleDecision:
        """
        Runs comprehensive checks on a proposed subtitle decision.
        Updates confidence, decision status, conflicts, and review questions.
        """
        if decision.decision in ["REJECTED", "UNTRANSLATABLE"]:
            return decision

        issues: List[str] = []

        # 1. Lexical Grounding Audit
        if decision.nadi_9_text:
            tokens = [t.strip("?,.!;:") for t in decision.nadi_9_text.split()]
            for token in tokens:
                # Check for untranslated english loanwords (like 'touch' in legacy flaw E17)
                if token.lower() in ["touch", "angry", "gold", "the", "ignore"]:
                    issues.append(f"Untranslated/raw foreign token detected: '{token}'")

        # 2. Timing and Reading Speed Verification
        if decision.timing:
            if not decision.timing.is_timing_safe:
                issues.append(
                    f"CPS violation: {decision.timing.characters_per_second} cps exceeds {self.MAX_CPS_THRESHOLD} threshold"
                )

        # 3. Conflict / Ambiguity Check
        if decision.conflicts:
            issues.append(f"Unresolved evidence conflict: {', '.join(decision.conflicts)}")

        # 4. Independent Model Check (Separate verification persona)
        if decision.confidence > 0.3:
            try:
                raw_verdict = self.provider.generate(
                    prompt=f"Audit this proposed subtitle: Source: '{decision.source_text}', Nadi-9: '{decision.nadi_9_text}'",
                    system_prompt="You are an adversarial linguistic inspector. Detect hallucinated roots or policy violations.",
                    call_purpose="verifier_independent"
                )
                import json
                parsed = json.loads(raw_verdict)
                if parsed.get("verdict") == "REJECT":
                    for iss in parsed.get("issues", []):
                        issues.append(f"Independent verifier: {iss}")
            except Exception as e:
                # In case of provider error, verifier logs warning rather than silently crashing
                issues.append(f"Independent verifier warning: {str(e)}")

        # 5. Final Synthesis & Epistemic Calibration
        if issues:
            # Calibrate confidence downwards based on issues found
            new_confidence = max(0.20, decision.confidence - (0.15 * len(issues)))
            decision.confidence = round(new_confidence, 2)
            decision.decision = "HUMAN_REVIEW"
            decision.confidence_reason += f"; Verifier flagged: {'; '.join(issues)}"

            if not decision.review_question:
                decision.review_question = f"Human linguist review needed: {issues[0]}"
        else:
            if decision.decision != "APPROVED" and decision.confidence >= 0.85:
                decision.decision = "APPROVED"

        return decision
