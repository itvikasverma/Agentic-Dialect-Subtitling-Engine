"""
Nadi-9 Dialect Agentic Translation Engine
Core Data Models and Type Definitions
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class SubtitleTiming(BaseModel):
    start_time: str
    end_time: str
    duration_seconds: float
    characters_per_second: float
    is_timing_safe: bool = True
    timing_warning: Optional[str] = None


class SubtitleDecision(BaseModel):
    """
    Required machine-readable output for every subtitle line.
    Matches the schema strictly defined in Section 4 of the candidate brief.
    """
    subtitle_id: str
    source_text: str
    nadi_9_text: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_reason: str = Field(..., description="Short explanation of confidence; number alone is not enough.")
    decision: Literal["APPROVED", "HUMAN_REVIEW", "REJECTED", "UNTRANSLATABLE"]
    evidence: List[str] = Field(default_factory=list, description="Evidence references that another person can inspect")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions about speaker, relationship, tone or scene context")
    conflicts: List[str] = Field(default_factory=list, description="Conflicting evidence that could change the decision")
    review_question: Optional[str] = Field(None, description="Clear, focused question when review is needed")
    timing: Optional[SubtitleTiming] = None
    applied_rules: List[str] = Field(default_factory=list)
    lexical_dependencies: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())



class EvidenceReference(BaseModel):
    id: str
    source_type: Literal[
        "approved_example",
        "grammar_note",
        "dictionary_a",
        "dictionary_b",
        "expert_note",
        "viewer_feedback",
        "audio_interview",
        "linguist_correction"
    ]
    author: Optional[str] = None
    reliability_weight: float = Field(ge=0.0, le=1.0)
    summary: str
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    quarantined: bool = False
    quarantine_reason: Optional[str] = None


class ConflictItem(BaseModel):
    term: str
    source_a: str
    source_a_val: str
    source_b: str
    source_b_val: str
    impact: str
    resolved: bool = False
    resolution_winner: Optional[str] = None
    rationale: Optional[str] = None


class GrammarHypothesis(BaseModel):
    rule_id: str
    category: str
    statement: str
    supporting_evidence: List[str]
    counterexamples: List[str] = Field(default_factory=list)
    confidence: float
    status: Literal["HYPOTHESIS", "CONFIRMED", "CHALLENGED", "SUPERSEDED"]
    notes: Optional[str] = None


class BudgetUsage(BaseModel):
    max_model_calls: int = 25
    max_tool_calls: int = 50
    model_calls_used: int = 0
    tool_calls_used: int = 0
    estimated_cost_usd: float = 0.0

    def record_model_call(self, cost: float = 0.001):
        if self.model_calls_used >= self.max_model_calls:
            raise RuntimeError(f"Model call budget exceeded: {self.model_calls_used}/{self.max_model_calls}")
        self.model_calls_used += 1
        self.estimated_cost_usd += cost

    def record_tool_call(self):
        if self.tool_calls_used >= self.max_tool_calls:
            raise RuntimeError(f"Tool call budget exceeded: {self.tool_calls_used}/{self.max_tool_calls}")
        self.tool_calls_used += 1


class RunState(BaseModel):
    run_id: str
    started_at: str
    completed_at: Optional[str] = None
    status: Literal["INITIALIZED", "LEARNING", "TRANSLATING", "VERIFYING", "COMPLETED", "REPLANNED"]
    budget: BudgetUsage = Field(default_factory=BudgetUsage)
    total_subtitles: int = 0
    approved_count: int = 0
    human_review_count: int = 0
    untranslatable_count: int = 0
    quarantined_items_count: int = 0
    events_processed: List[str] = Field(default_factory=list)
