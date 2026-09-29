"""
Evidence Inspection Agent
Inspects multi-source dialect materials, sanitizes untrusted inputs,
extracts structural claims, and records cross-source conflicts.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from .state import AgentState
from ..evidence.evidence_graph import EvidenceGraph
from ..providers.base import LLMProvider


class EvidenceInspectionAgent:
    """
    First agent in workflow:
    - Ingests all sources (approved examples, audio interviews, grammar notes, Dict A & B, expert notes, viewer feedback)
    - Separates untrusted evidence from instructions
    - Sanitizes and quarantines poisoned or injection payloads
    - Extracts terms, claims, register info, grammar observations
    - Resolves and records conflicts with explicit precedence rationale
    """

    def __init__(self, data_dir: Path, provider: LLMProvider, evidence_graph: Optional[EvidenceGraph] = None):
        self.data_dir = data_dir
        self.provider = provider
        self.evidence_graph = evidence_graph or EvidenceGraph(data_dir=self.data_dir)

    def run(self, state: AgentState) -> Dict[str, Any]:
        self.provider.record_tool_invocation()

        self.evidence_graph.load_all_sources()

        # Build source metadata dictionary
        source_metadata = {
            "precedence_policy": self.evidence_graph.SOURCE_PRECEDENCE,
            "total_records": len(self.evidence_graph.evidence_store),
            "quarantined_count": len(self.evidence_graph.quarantined_items),
            "conflict_count": len(self.evidence_graph.conflicts),
            "sources_loaded": [
                "grammar_note",
                "dictionary_b",
                "dictionary_a",
                "approved_examples",
                "audio_interviews",
                "expert_notes",
                "viewer_feedback"
            ]
        }

        return {
            "evidence": self.evidence_graph.evidence_store,
            "source_metadata": source_metadata,
            "quarantined_items": self.evidence_graph.quarantined_items,
            "conflicts": self.evidence_graph.conflicts,
            "current_step": "evidence_inspected",
            "workflow_status": "INSPECTED"
        }
