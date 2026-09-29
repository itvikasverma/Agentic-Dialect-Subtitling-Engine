"""
Typed AgentState Schema for LangGraph Stateful Workflow
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from ..models.schema import (
    SubtitleDecision,
    EvidenceReference,
    ConflictItem,
    GrammarHypothesis,
    SubtitleRisk,
    BudgetUsage,
)


class AgentState(TypedDict, total=False):
    """
    Shared structured state maintained across all agents in the LangGraph workflow.
    """
    # Ingested evidence & metadata
    evidence: Dict[str, EvidenceReference]
    source_metadata: Dict[str, Any]
    quarantined_items: List[EvidenceReference]
    conflicts: List[ConflictItem]

    # Learned linguistic rules
    hypotheses: Dict[str, GrammarHypothesis]
    tested_hypotheses: List[str]
    counterexamples: List[str]

    # Episode input & Subtitle queues
    episode: Dict[str, Any]
    raw_subtitles: Dict[str, Dict[str, Any]]
    subtitles_to_process: List[str]
    current_subtitle_index: int

    # Risk planning
    risk_profiles: Dict[str, SubtitleRisk]
    high_risk_subtitles: List[str]

    # Proposals & Independent Verification
    subtitle_proposals: Dict[str, SubtitleDecision]
    verification_results: Dict[str, SubtitleDecision]

    # Final Routing & Releases
    decisions: Dict[str, SubtitleDecision]
    review_queue: List[SubtitleDecision]
    released_subtitles: List[SubtitleDecision]

    # Selective Replanning & Corrections
    corrections: List[Dict[str, Any]]
    affected_rules: List[str]
    affected_subtitles: List[str]
    replan_audit: Optional[Dict[str, Any]]

    # Operational Tracking
    budget_usage: BudgetUsage
    current_step: str
    workflow_status: str
    errors: List[str]
