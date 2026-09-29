"""
Language Learning Agent
Forms grammatical hypotheses from evidence notes, empirically verifies them
against the approved corpus, flags counterexamples, and adjusts status & confidence.
"""

from typing import Dict, Any, List
from .state import AgentState
from ..linguist.hypothesis_engine import HypothesisEngine
from ..evidence.evidence_graph import EvidenceGraph
from ..providers.base import LLMProvider


class LanguageLearningAgent:
    """
    Third agent in workflow:
    - Synthesizes grammar rules from notes (Word Order, Tenses, Negation, Honorifics)
    - Tests hypotheses against 20 approved examples
    - Retains and reports counterexamples (e.g. legacy flaw E17)
    - Updates hypothesis status: SUPPORTED -> CONTESTED -> REJECTED
    - Calibrates empirical confidence
    """

    def __init__(self, hypothesis_engine: HypothesisEngine, provider: LLMProvider):
        self.hypothesis_engine = hypothesis_engine
        self.provider = provider

    def run(self, state: AgentState) -> Dict[str, Any]:
        self.provider.record_tool_invocation()

        hypotheses_list = self.hypothesis_engine.extract_and_verify_hypotheses()
        hypotheses_dict = {h.rule_id: h for h in hypotheses_list}

        tested_ids = list(hypotheses_dict.keys())
        all_counterexamples = []
        for h in hypotheses_list:
            all_counterexamples.extend(h.counterexamples)

        return {
            "hypotheses": hypotheses_dict,
            "tested_hypotheses": tested_ids,
            "counterexamples": all_counterexamples,
            "current_step": "hypotheses_learned",
            "workflow_status": "LEARNED"
        }
