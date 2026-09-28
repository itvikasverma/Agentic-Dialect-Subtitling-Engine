"""
Command Line Interface for Nadi-9 Dialect Agentic Translation System
"""

import sys
import argparse
from pathlib import Path
import json

from .pipeline import Nadi9AgentPipeline
from .providers.mock_provider import MockLLMProvider
from .providers.live_provider import LiveLLMProvider


def main():
    parser = argparse.ArgumentParser(
        prog="nadi9-agent",
        description="Evidence-Grounded Agentic Translation Engine for Fictional Dialect Nadi-9"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Execute complete subtitling pipeline on episode package")
    run_parser.add_argument("--data-dir", default="data", help="Path to Nadi-9 assignment data directory")
    run_parser.add_argument("--output-dir", default="sample_run", help="Directory to save generated artifacts")
    run_parser.add_argument("--mock", action="store_true", default=True, help="Run in zero-key deterministic mock mode")
    run_parser.add_argument("--simulate-correction", action="store_true", help="Inject mid-run linguist correction to test replanning")

    # Command: learn
    learn_parser = subparsers.add_parser("learn", help="Inspect evidence, formulate hypotheses and detect conflicts")
    learn_parser.add_argument("--data-dir", default="data", help="Path to data directory")

    # Command: replan
    replan_parser = subparsers.add_parser("replan", help="Inject a surprise correction and selectively replan affected subtitles")
    replan_parser.add_argument("--data-dir", default="data", help="Path to data directory")
    replan_parser.add_argument("--output-dir", default="sample_run", help="Output directory")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    data_path = Path(args.data_dir).resolve()
    if not data_path.exists():
        print(f"Error: Data directory not found at {data_path}")
        sys.exit(1)

    is_mock = getattr(args, "mock", True)
    provider = MockLLMProvider() if is_mock else LiveLLMProvider()
    pipeline = Nadi9AgentPipeline(data_dir=data_path, provider=provider)


    if args.command == "learn":
        print("\n=======================================================")
        print("          NADI-9 LINGUISTIC HYPOTHESIS ENGINE          ")
        print("=======================================================\n")
        pipeline.initialize_and_learn()

        print(f"[+] Loaded {len(pipeline.evidence_graph.evidence_store)} evidence records.")
        print(f"[+] Quarantined {len(pipeline.evidence_graph.quarantined_items)} poisoned/flawed entries.")
        print(f"[+] Identified {len(pipeline.evidence_graph.conflicts)} cross-source conflicts.\n")

        print("--- EXTRACTED GRAMMATICAL HYPOTHESES & COUNTEREXAMPLES ---")
        for h in pipeline.hypothesis_engine.hypotheses.values():
            status_symbol = "[CONFIRMED]" if h.status == "CONFIRMED" else "[CHALLENGED]"
            print(f"\n* {status_symbol} {h.rule_id} (Confidence: {h.confidence})")
            print(f"  Statement: {h.statement}")
            print(f"  Supporting: {len(h.supporting_evidence)} items | Counterexamples: {h.counterexamples}")

        print("\n--- QUARANTINED EVIDENCE / INJECTION ALERTS ---")
        for q in pipeline.evidence_graph.quarantined_items:
            print(f"- [{q.id}]: {q.summary} ({q.quarantine_reason})")

    elif args.command == "run":
        out_path = Path(args.output_dir).resolve()
        print("\n=======================================================")
        print("       NADI-9 EPISODIC SUBTITLE PIPELINE EXECUTION    ")
        print("=======================================================\n")

        print("[Step 1/5] Ingesting multi-source evidence and resolving precedence...")
        pipeline.initialize_and_learn()

        print("[Step 2/5] Grounded translation and context analysis...")
        pipeline.process_episode()

        if args.simulate_correction:
            print("\n[Step 3/5] Simulating Surprise Event: Mid-run Linguist Correction...")
            events_file = data_path / "surprise_events.json"
            if events_file.exists():
                with open(events_file, "r", encoding="utf-8") as f:
                    events = json.load(f).get("events", [])
                    corr = next((e for e in events if e.get("event_type") == "linguist_correction"), None)
                    if corr:
                        audit = pipeline.apply_correction_event(corr)
                        print(f"  -> DAG identified {len(audit['impacted_subtitle_ids'])} impacted subtitle(s): {audit['impacted_subtitle_ids']}")
                        print(f"  -> Unaffected lines preserved untouched: {audit['unaffected_count']}")
                        for r in audit["reprocessed"]:
                            print(f"  -> Updated {r['subtitle_id']}: '{r['previous_nadi_9']}' -> '{r['new_nadi_9']}' ({r['confidence_change']})")

        print("\n[Step 4/5] Multi-phase verification & CPS audit completed.")

        print(f"[Step 5/5] Exporting structured run artifacts to {out_path}...")
        pipeline.export_artifacts(out_path)

        print("\n=======================================================")
        print("                   EXECUTION SUMMARY                   ")
        print("=======================================================")
        print(f"Total Subtitles:        {pipeline.run_state.total_subtitles}")
        print(f"Directly Approved:      {pipeline.run_state.approved_count}")
        print(f"Escalated to Review:    {pipeline.run_state.human_review_count}")
        print(f"Untranslatable/Blocked: {pipeline.run_state.untranslatable_count}")
        print(f"Model Budget Calls:     {pipeline.budget.model_calls_used}/{pipeline.budget.max_model_calls}")
        print(f"Tool Invocations:       {pipeline.budget.tool_calls_used}/{pipeline.budget.max_tool_calls}")
        print(f"Artifacts Created in:   {out_path}")
        print("  -> subtitles.srt")
        print("  -> subtitle_decisions.jsonl")
        print("  -> learned_rules.json")
        print("  -> review_queue.json")
        print("  -> final_report.md\n")

    elif args.command == "replan":
        out_path = Path(args.output_dir).resolve()
        pipeline.initialize_and_learn()
        pipeline.process_episode()

        events_file = data_path / "surprise_events.json"
        with open(events_file, "r", encoding="utf-8") as f:
            events = json.load(f).get("events", [])
            corr = next((e for e in events if e.get("event_type") == "linguist_correction"), None)

        if corr:
            audit = pipeline.apply_correction_event(corr)
            print("\n[DAG Replanning Audit]")
            print(json.dumps(audit, indent=2))
            pipeline.export_artifacts(out_path)
            print(f"\nUpdated artifacts written to {out_path}")


if __name__ == "__main__":
    main()
