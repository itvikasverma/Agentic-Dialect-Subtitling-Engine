"""
Translation Agent
Produces grounded subtitle translation proposals line-by-line.
Abstains from hallucinating unsupported terms and attaches rigorous epistemic citations.
"""

from typing import Dict, Any, List
from .state import AgentState
from ..models.schema import SubtitleDecision
from ..translator.engine import TranslationEngine
from ..providers.base import LLMProvider


class TranslationAgent:
    """
    Fourth agent in workflow:
    - Iterates over subtitles (or batch)
    - Checks lexical grounding, grammar support, and register
    - Generates grounded proposals with explicit evidence citations
    - Safely abstains on unknown terms (INSUFFICIENT_EVIDENCE / HUMAN_REVIEW)
    - Incorporates risk metadata into the proposal
    """

    def __init__(self, translation_engine: TranslationEngine, provider: LLMProvider):
        self.translation_engine = translation_engine
        self.provider = provider

    def run(self, state: AgentState) -> Dict[str, Any]:
        raw_subs = state.get("raw_subtitles", {})
        risk_profiles = state.get("risk_profiles", {})
        proposals: Dict[str, SubtitleDecision] = {}

        for sub_id, sub_data in raw_subs.items():
            proposal = self.translation_engine.propose_subtitle(sub_data)
            # Attach risk assessment if available
            if sub_id in risk_profiles:
                proposal.risk_assessment = risk_profiles[sub_id]
            proposals[sub_id] = proposal

        return {
            "subtitle_proposals": proposals,
            "current_step": "translations_proposed",
            "workflow_status": "TRANSLATED"
        }
