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


class Nadi9AgentPipeline:
    """
    Main Orchestrator for the Nadi-9 Dialect Subtitling System.
    Executes:
    1. Ingestion & Sanitization
    2. Hypothesis Formation & Verification against Counterexamples
    3. Grounded Translation Planning
    4. Independent Verification & CPS Checks
    5. Selective Replanning on Correction Events
    6. Export of Structured Artifacts (.srt, .jsonl, .json, .md)
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

        self.raw_subtitles: Dict[str, Dict[str, Any]] = {}
        self.decisions: Dict[str, SubtitleDecision] = {}
        self.run_state = RunState(
            run_id=f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            started_at=datetime.now(timezone.utc).isoformat(),
            status="INITIALIZED",
            budget=self.budget
        )


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

        # 3. Generate learned_rules.json
        rules_path = output_dir / "learned_rules.json"
        with open(rules_path, "w", encoding="utf-8") as f:
            rules_data = [h.model_dump() for h in self.hypothesis_engine.hypotheses.values()]
            json.dump({"learned_rules": rules_data}, f, indent=2)

        # 4. Generate review_queue.json
        review_path = output_dir / "review_queue.json"
        review_items = [
            d.model_dump() for d in self.decisions.values() if d.decision == "HUMAN_REVIEW"
        ]
        with open(review_path, "w", encoding="utf-8") as f:
            json.dump({"pending_reviews": review_items, "total_pending": len(review_items)}, f, indent=2)

        # 5. Generate final_report.md
        report_path = output_dir / "final_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            approval_rate = (self.run_state.approved_count / max(1, self.run_state.total_subtitles)) * 100
            release_rec = "CONDITIONAL_APPROVAL" if approval_rate >= 60 else "BLOCK_RELEASE"

            f.write(f"# Nadi-9 Subtitle Production Run Report\n\n")
            f.write(f"**Run ID:** `{self.run_state.run_id}`  \n")
            f.write(f"**Date:** `{self.run_state.completed_at}`  \n")
            f.write(f"**Release Recommendation:** **{release_rec}** (Approval Rate: {approval_rate:.1f}%)\n\n")

            f.write(f"## Summary Metrics\n")
            f.write(f"- **Total Subtitles Processed:** {self.run_state.total_subtitles}\n")
            f.write(f"- **Directly Approved:** {self.run_state.approved_count}\n")
            f.write(f"- **Escalated to Human Review:** {self.run_state.human_review_count}\n")
            f.write(f"- **Untranslatable / Security Quarantined:** {self.run_state.untranslatable_count}\n")
            f.write(f"- **Poisoned / Malicious Items Quarantined:** {self.run_state.quarantined_items_count}\n\n")

            f.write(f"## Resource & Budget Usage\n")
            f.write(f"- **Model Calls Used:** {self.budget.model_calls_used} / {self.budget.max_model_calls} max\n")
            f.write(f"- **Tool Calls Used:** {self.budget.tool_calls_used} / {self.budget.max_tool_calls} max\n")
            f.write(f"- **Estimated Model Cost:** ${self.budget.estimated_cost_usd:.4f}\n\n")

            f.write(f"## Key Evidence Disagreements & Quarantined Sources\n")
            for c in self.evidence_graph.conflicts:
                f.write(f"- **Term '{c.term}':** Resolved '{c.source_a_val}' ({c.source_a}) over '{c.source_b_val}' ({c.source_b}). Rationale: {c.rationale}\n")
            for q in self.evidence_graph.quarantined_items:
                f.write(f"- **Quarantine Item [{q.id}]:** {q.summary} (Reason: {q.quarantine_reason})\n")

            f.write(f"\n## Escalation Queue for Language Specialists\n")
            for item in review_items:
                f.write(f"- **Line `{item['subtitle_id']}`** (Source: *\"{item['source_text']}\"*): {item['review_question']} [Confidence: {item['confidence']}]\n")
