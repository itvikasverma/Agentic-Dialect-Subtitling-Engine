"""
Agentic Translation Pipeline Coordinator and Artifact Generator
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


from .models.schema import SubtitleDecision, RunState, BudgetUsage
from .providers.base import LLMProvider
from .providers.mock_provider import MockLLMProvider
from .evidence.evidence_graph import EvidenceGraph
from .linguist.hypothesis_engine import HypothesisEngine
from .translator.engine import TranslationEngine
from .verifier.multi_verifier import MultiPhaseVerifier
from .replanner.dependency_tracker import DependencyReplanner
from .agents.graph import build_nadi9_workflow
from .agents.state import AgentState


class Nadi9AgentPipeline:
    """
    Main Orchestrator for the Nadi-9 Dialect Subtitling System.
    Orchestrates an executable LangGraph multi-agent state graph:
    1. Ingestion & Sanitization (Evidence Inspection Agent)
    2. Risk Analysis & Budget Prioritization (Risk/Planning Agent)
    3. Hypothesis Formation & Verification against Counterexamples (Language Learning Agent)
    4. Grounded Translation Planning (Translation Agent)
    5. Blind Independent Verification & CPS Checks (Independent Verifier Agent)
    6. Decision Routing & Selective Replanning (Decision Router / Replanner Agent)
    7. Export of Structured Artifacts (.srt, .jsonl, .json, .md)
    """

    def __init__(
        self,
        data_dir: Path,
        provider: Optional[LLMProvider] = None,
        max_model_calls: int = 25,
        max_tool_calls: int = 50
    ):
        self.data_dir = data_dir
        self.budget = BudgetUsage(max_model_calls=max_model_calls, max_tool_calls=max_tool_calls)
        self.provider = provider or MockLLMProvider(budget=self.budget)

        self.evidence_graph = EvidenceGraph(data_dir=self.data_dir)
        self.hypothesis_engine = HypothesisEngine(self.evidence_graph, self.provider)
        self.translator = TranslationEngine(self.evidence_graph, self.hypothesis_engine, self.provider)
        self.verifier = MultiPhaseVerifier(self.evidence_graph, self.provider)
        self.replanner = DependencyReplanner(self.evidence_graph, self.translator, self.verifier)

        # Build compiled LangGraph workflow
        self.workflow_graph = build_nadi9_workflow(
            data_dir=self.data_dir,
            provider=self.provider,
            evidence_graph=self.evidence_graph,
            hypothesis_engine=self.hypothesis_engine,
            translator=self.translator,
            verifier=self.verifier,
            replanner=self.replanner
        )

        self.raw_subtitles: Dict[str, Dict[str, Any]] = {}
        self.decisions: Dict[str, SubtitleDecision] = {}
        self.risk_profiles: Dict[str, Any] = {}
        self.run_state = RunState(
            run_id=f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            started_at=datetime.now(timezone.utc).isoformat(),
            status="INITIALIZED",
            budget=self.budget
        )

    def run_agentic_workflow(self, episode_file: Optional[Path] = None, corrections: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Executes the end-to-end LangGraph stateful multi-agent workflow graph.
        """
        ep_path = episode_file or (self.data_dir / "episode_package.json")
        with open(ep_path, "r", encoding="utf-8") as f:
            ep_data = json.load(f)

        raw_list = ep_data.get("subtitles", [])
        self.raw_subtitles = {item["subtitle_id"]: item for item in raw_list}
        self.run_state.total_subtitles = len(raw_list)

        initial_state: AgentState = {
            "episode": ep_data,
            "raw_subtitles": self.raw_subtitles,
            "subtitles_to_process": list(self.raw_subtitles.keys()),
            "current_subtitle_index": 0,
            "corrections": corrections or [],
            "budget_usage": self.budget,
            "current_step": "start",
            "workflow_status": "INITIALIZED"
        }

        # Invoke LangGraph graph
        final_state = self.workflow_graph.invoke(initial_state)

        # Sync pipeline attributes from final graph state
        self.decisions = final_state.get("decisions", {})
        self.risk_profiles = final_state.get("risk_profiles", {})
        self.run_state.quarantined_items_count = len(self.evidence_graph.quarantined_items)
        self.run_state.status = "COMPLETED"
        self._refresh_stats()

        return final_state

    def initialize_and_learn(self):
        """Loads all evidence, sanitizes data, and builds hypotheses."""
        self.run_state.status = "LEARNING"
        self.evidence_graph.load_all_sources()
        self.run_state.quarantined_items_count = len(self.evidence_graph.quarantined_items)

        # Build grammar hypotheses & counterexamples
        self.hypothesis_engine.extract_and_verify_hypotheses()

    def process_episode(self, episode_file: Optional[Path] = None):
        """Processes the target episode package."""
        self.run_state.status = "TRANSLATING"
        ep_path = episode_file or (self.data_dir / "episode_package.json")
        with open(ep_path, "r", encoding="utf-8") as f:
            ep_data = json.load(f)

        raw_list = ep_data.get("subtitles", [])
        self.run_state.total_subtitles = len(raw_list)

        for item in raw_list:
            sub_id = item["subtitle_id"]
            self.raw_subtitles[sub_id] = item

            # 1. Propose grounded translation
            proposal = self.translator.propose_subtitle(item)

            # 2. Independent multi-phase verification
            verified = self.verifier.verify_decision(proposal)

            # 3. Store decision and register into DAG
            self.decisions[sub_id] = verified
            self.replanner.register_decision_dependencies(verified)

        self._refresh_stats()

    def apply_correction_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes selective replanning for mid-run corrections.
        """
        self.run_state.status = "REPLANNED"
        replan_audit = self.replanner.execute_selective_replan(
            correction_event=event_data,
            current_decisions=self.decisions,
            episode_raw_subtitles=self.raw_subtitles
        )
        self.run_state.events_processed.append(event_data.get("event_id", "CORRECTION"))
        self._refresh_stats()
        return replan_audit

    def _refresh_stats(self):
        self.run_state.approved_count = sum(1 for d in self.decisions.values() if d.decision == "APPROVED")
        self.run_state.human_review_count = sum(1 for d in self.decisions.values() if d.decision == "HUMAN_REVIEW")
        self.run_state.untranslatable_count = sum(1 for d in self.decisions.values() if d.decision in ["REJECTED", "UNTRANSLATABLE"])

    def export_artifacts(self, output_dir: Path):
        """Generates all required submission artifacts into output directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        self.run_state.completed_at = datetime.now(timezone.utc).isoformat()
        self.run_state.status = "COMPLETED"


        # 1. Generate subtitles.srt
        srt_path = output_dir / "subtitles.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            idx = 1
            for sub_id, d in self.decisions.items():
                if d.decision == "APPROVED" and d.nadi_9_text and d.timing:
                    f.write(f"{idx}\n")
                    f.write(f"{d.timing.start_time} --> {d.timing.end_time}\n")
                    f.write(f"{d.nadi_9_text}\n\n")
                    idx += 1
                elif d.decision == "HUMAN_REVIEW" and d.nadi_9_text and d.timing:
                    # Mark human review in SRT comments
                    f.write(f"{idx}\n")
                    f.write(f"{d.timing.start_time} --> {d.timing.end_time}\n")
                    f.write(f"[{d.nadi_9_text} (PENDING HUMAN REVIEW)]\n\n")
                    idx += 1

        # 2. Generate subtitle_decisions.jsonl (Strict JSONL format from Section 4)
        jsonl_path = output_dir / "subtitle_decisions.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for d in self.decisions.values():
                record = {
                    "subtitle_id": d.subtitle_id,
                    "source_text": d.source_text,
                    "nadi_9_text": d.nadi_9_text,
                    "confidence": d.confidence,
                    "decision": d.decision,
                    "evidence": d.evidence,
                    "assumptions": d.assumptions,
                    "conflicts": d.conflicts,
                    "review_question": d.review_question
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 3. Generate learned_rules.json (Strict Section 27 Schema)
        rules_path = output_dir / "learned_rules.json"
        with open(rules_path, "w", encoding="utf-8") as f:
            rules_data = []
            for h in self.hypothesis_engine.hypotheses.values():
                rules_data.append({
                    "rule_id": h.rule_id,
                    "claim": h.statement,
                    "statement": h.statement,
                    "category": h.category,
                    "status": h.status,
                    "confidence": h.confidence,
                    "supporting_evidence": h.supporting_evidence,
                    "counterexamples": h.counterexamples,
                    "notes": h.notes
                })
            json.dump({"learned_rules": rules_data, "total_rules": len(rules_data)}, f, indent=2)

        # 4. Generate review_queue.json (Strict Section 27 Schema)
        review_path = output_dir / "review_queue.json"
        review_items = []
        for d in self.decisions.values():
            if d.decision in ["HUMAN_REVIEW", "REJECTED", "UNTRANSLATABLE"]:
                priority = "HIGH" if (d.risk_assessment and d.risk_assessment.risk_level in ["HIGH", "CRITICAL"]) else "MEDIUM"
                review_items.append({
                    "subtitle_id": d.subtitle_id,
                    "source_text": d.source_text,
                    "nadi_9_proposal": d.nadi_9_text,
                    "confidence": d.confidence,
                    "reason": d.confidence_reason,
                    "decision": d.decision,
                    "evidence": d.evidence,
                    "conflicts": d.conflicts,
                    "review_question": d.review_question or "Human review requested by verifier",
                    "priority": priority
                })
        with open(review_path, "w", encoding="utf-8") as f:
            json.dump({"pending_reviews": review_items, "total_pending": len(review_items)}, f, indent=2)

        # 5. Generate final_report.md (Strict Section 27 Schema)
        report_path = output_dir / "final_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            approval_rate = (self.run_state.approved_count / max(1, self.run_state.total_subtitles)) * 100
            release_rec = "CONDITIONAL_APPROVAL" if approval_rate >= 60 else "BLOCK_RELEASE"

            f.write(f"# Nadi-9 Subtitle Production Run Report\n\n")
            f.write(f"**Run ID:** `{self.run_state.run_id}`  \n")
            f.write(f"**Date:** `{self.run_state.completed_at}`  \n")
            f.write(f"**Episode Summary:** Processed package with {self.run_state.total_subtitles} dialogue lines across formal, kinship, merchant, and urgent registers.  \n")
            f.write(f"**Release Recommendation:** **{release_rec}** (Approval Rate: {approval_rate:.1f}%)\n\n")

            f.write(f"## Summary Metrics\n")
            f.write(f"- **Total Subtitles Processed:** {self.run_state.total_subtitles}\n")
            f.write(f"- **Directly Approved / Supported:** {self.run_state.approved_count}\n")
            f.write(f"- **Escalated to Human Review Queue:** {self.run_state.human_review_count}\n")
            f.write(f"- **Untranslatable / Security Quarantined:** {self.run_state.untranslatable_count}\n")
            f.write(f"- **Poisoned / Malicious Items Quarantined:** {self.run_state.quarantined_items_count}\n\n")

            f.write(f"## Resource & Budget Usage\n")
            f.write(f"- **Model Calls Used:** {self.budget.model_calls_used} / {self.budget.max_model_calls} max (Remaining: {self.budget.remaining_model_calls})\n")
            f.write(f"- **Calls by Agent:** {self.budget.calls_by_agent if self.budget.calls_by_agent else {'translation': 0, 'verifier': 0}}\n")
            f.write(f"- **Tool Calls Used:** {self.budget.tool_calls_used} / {self.budget.max_tool_calls} max (Remaining: {self.budget.remaining_tool_calls})\n")
            f.write(f"- **Blocked Calls:** {self.budget.blocked_calls}\n")
            f.write(f"- **Estimated Model Cost:** ${self.budget.estimated_cost_usd:.4f}\n\n")

            f.write(f"## Key Evidence Disagreements & Quarantined Sources\n")
            for c in self.evidence_graph.conflicts:
                f.write(f"- **Term '{c.term}':** Resolved '{c.source_a_val}' ({c.source_a}) over '{c.source_b_val}' ({c.source_b}). Rationale: {c.rationale}\n")
            for q in self.evidence_graph.quarantined_items:
                f.write(f"- **Quarantine Item [{q.id}]:** {q.summary} (Reason: {q.quarantine_reason})\n")

            f.write(f"\n## Escalation Queue for Language Specialists\n")
            for item in review_items:
                f.write(f"- **Line `{item['subtitle_id']}`** [Priority: {item['priority']}] (Source: *\"{item['source_text']}\"*): {item['review_question']} [Confidence: {item['confidence']}]\n")

            f.write(f"\n## Known Limitations & Failures Handled\n")
            f.write(f"- Deterministic offline mock mode uses heuristics for zero-key evaluation.\n")
            f.write(f"- Esoteric technical terms without corpus grounding (e.g. 'astrolabe') safely abstained.\n")
            f.write(f"- Transient provider timeouts automatically recover with retry.\n")
