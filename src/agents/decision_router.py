"""
Decision Router and Selective Replanner Agent
Routes verified decisions into Release or Review queues, and triggers
selective replanning when mid-run corrections or rule challenges occur.
"""

from typing import Dict, Any, List, Optional
from .state import AgentState
from ..models.schema import SubtitleDecision
from ..replanner.dependency_tracker import DependencyReplanner
from ..providers.base import LLMProvider


class DecisionRouterAgent:
    """
    Sixth agent in workflow:
    - Analyzes verified decisions
    - Routes:
      * SUPPORTED / APPROVED -> Release Bucket
      * HUMAN_REVIEW / INSUFFICIENT_EVIDENCE / REJECTED -> Specialist Review Queue
    - If a mid-run correction event is pending:
      * Invokes DependencyReplanner DAG
      * Selectively re-translates and re-verifies ONLY impacted subtitles
      * Leaves unaffected lines untouched
    """

    def __init__(self, replanner: DependencyReplanner, provider: LLMProvider):
        self.replanner = replanner
        self.provider = provider

    def run(self, state: AgentState) -> Dict[str, Any]:
        decisions = state.get("decisions", {})
        raw_subs = state.get("raw_subtitles", {})
        corrections = state.get("corrections", [])

        # Register dependencies in the DAG
        for d in decisions.values():
            self.replanner.register_decision_dependencies(d)

        # Handle any pending corrections for selective replanning
        replan_audit = None
        affected_subtitles = []
        affected_rules = []

        if corrections:
            for corr in corrections:
                affected_rule = corr.get("affected_rule_id")
                if affected_rule:
                    affected_rules.append(affected_rule)
                audit = self.replanner.execute_selective_replan(
                    correction_event=corr,
                    current_decisions=decisions,
                    episode_raw_subtitles=raw_subs
                )
                replan_audit = audit
                affected_subtitles.extend(audit.get("impacted_subtitle_ids", []))

        # Categorize into released vs review queue
        released: List[SubtitleDecision] = []
        review_queue: List[SubtitleDecision] = []

        for sub_id, d in decisions.items():
            if d.decision in ["APPROVED", "SUPPORTED"] and d.confidence >= 0.85:
                released.append(d)
            else:
                review_queue.append(d)

        return {
            "decisions": decisions,
            "released_subtitles": released,
            "review_queue": review_queue,
            "affected_rules": affected_rules,
            "affected_subtitles": affected_subtitles,
            "replan_audit": replan_audit,
            "current_step": "decisions_routed",
            "workflow_status": "COMPLETED"
        }
