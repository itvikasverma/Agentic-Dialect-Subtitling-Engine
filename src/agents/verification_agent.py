"""
Independent Verification Agent
Performs blind, multi-phase verification without translator's chain-of-thought.
Audits lexical grounding, morphology, reading speed, omissions, and policy compliance.
"""

from typing import Dict, Any, List
from .state import AgentState
from ..models.schema import SubtitleDecision
from ..verifier.multi_verifier import MultiPhaseVerifier
from ..providers.base import LLMProvider


class IndependentVerificationAgent:
    """
    Fifth agent in workflow:
    - Truly independent: receives only source_text, proposed_nadi_9_text, and evidence references
    - Never sees translator's internal chain-of-thought or rationales
    - Evaluates:
      1. Lexical grounding (flags ungrounded tokens)
      2. Morphological and syntax rules (tense, negation prefixes)
      3. Timing & CPS limits (<= 20.0 cps)
      4. Disagreements and unresolved dictionary conflicts
      5. Independent adversarial LLM check (with separate verifier persona)
    """

    def __init__(self, verifier: MultiPhaseVerifier, provider: LLMProvider):
        self.verifier = verifier
        self.provider = provider

    def run(self, state: AgentState) -> Dict[str, Any]:
        proposals = state.get("subtitle_proposals", {})
        verified_results: Dict[str, SubtitleDecision] = {}

        for sub_id, proposal in proposals.items():
            verified = self.verifier.verify_decision(proposal)
            verified_results[sub_id] = verified

        return {
            "verification_results": verified_results,
            "decisions": verified_results,
            "current_step": "verification_completed",
            "workflow_status": "VERIFIED"
        }
