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

    # Command: inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect all loaded evidence sources, precedence weights, and security quarantine")
    inspect_parser.add_argument("--data-dir", default="data", help="Path to data directory")

    # Command: verify
    verify_parser = subparsers.add_parser("verify", help="Run independent multi-phase verifier on episode subtitles")
    verify_parser.add_argument("--data-dir", default="data", help="Path to data directory")
    verify_parser.add_argument("--mock", action="store_true", default=True, help="Run in mock mode")

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
            status_symbol = f"[{h.status}]"
            print(f"\n* {status_symbol} {h.rule_id} (Confidence: {h.confidence})")
            print(f"  Statement: {h.statement}")
            print(f"  Supporting: {len(h.supporting_evidence)} items | Counterexamples: {h.counterexamples}")

        print("\n--- QUARANTINED EVIDENCE / INJECTION ALERTS ---")
        for q in pipeline.evidence_graph.quarantined_items:
            print(f"- [{q.id}]: {q.summary} ({q.quarantine_reason})")

    elif args.command == "run":
        out_path = Path(args.output_dir).resolve()
        print("\n=======================================================")
        print("    NADI-9 AGENTIC SUBTITLE DECISION ENGINE (LANGGRAPH) ")
        print("=======================================================\n")

        # Load any pending corrections if simulated
        corrections = []
        if args.simulate_correction:
            events_file = data_path / "surprise_events.json"
            if events_file.exists():
                with open(events_file, "r", encoding="utf-8") as f:
                    events = json.load(f).get("events", [])
                    corr = next((e for e in events if e.get("event_type") == "linguist_correction"), None)
                    if corr:
                        corrections.append(corr)

        print("[Agent 1/6] Evidence Inspection Agent: Ingesting sources & resolving precedence...")
        pipeline.evidence_graph.load_all_sources()
        print(f"  -> Ingested {len(pipeline.evidence_graph.evidence_store)} records from 7 distinct sources")
        print(f"  -> Quarantined {len(pipeline.evidence_graph.quarantined_items)} adversarial / poisoned entries")
        print(f"  -> Discovered & logged {len(pipeline.evidence_graph.conflicts)} cross-source dictionary conflicts")

        print("\n[Agent 2/6] Language Learning Agent: Forming hypotheses & checking counterexamples...")
        hypotheses = pipeline.hypothesis_engine.extract_and_verify_hypotheses()
        print(f"  -> Formulated {len(hypotheses)} grammatical hypotheses across word order, tenses, and honorifics")
        for h in hypotheses:
            ce_count = len(h.counterexamples)
            ce_str = f"({ce_count} counterexamples found)" if ce_count else "(0 counterexamples)"
            print(f"     * {h.rule_id}: {h.status} [Confidence: {h.confidence}] {ce_str}")

        print("\n[Agent 3/6] Risk & Planning Agent: Evaluating 9-dimensional linguistic risk profile...")
        # Execute workflow
        state = pipeline.run_agentic_workflow(corrections=corrections)
        risk_profiles = state.get("risk_profiles", {})
        for sub_id, r in risk_profiles.items():
            print(f"  -> Subtitle {sub_id}: Tier {r.risk_level} (Score: {r.risk_score}) | {r.reasoning}")

        print("\n[Agent 4/6] Translation Agent: Generating evidence-grounded proposals line-by-line...")
        print(f"  -> Processed {len(pipeline.raw_subtitles)} subtitle proposals with strict lexical abstention")

        print("\n[Agent 5/6] Independent Verification Agent: Multi-phase blind audit completed...")
        print("  -> Independently checked lexical grounding, morphology, reading speed (CPS <= 20.0), and conflicts")

        print("\n[Agent 6/6] Decision Router: Categorizing release vs review queues...")
        print(f"  -> Released to Production: {pipeline.run_state.approved_count}")
        print(f"  -> Escalated to Human Review: {pipeline.run_state.human_review_count}")
        print(f"  -> Blocked / Untranslatable: {pipeline.run_state.untranslatable_count}")

        if args.simulate_correction:
            replan_audit = state.get("replan_audit")
            if replan_audit:
                print("\n[Selective Replanning Agent: DAG Invalidation Trace]")
                print(f"  -> Event: {replan_audit.get('event_id')} - {replan_audit.get('description')}")
                print(f"  -> DAG Impacted Subtitles: {replan_audit.get('impacted_subtitle_ids')}")
                print(f"  -> Unaffected Subtitles Untouched: {replan_audit.get('unaffected_count')}")
                for r in replan_audit.get("reprocessed", []):
                    print(f"     * Updated {r['subtitle_id']}: '{r['previous_nadi_9']}' -> '{r['new_nadi_9']}' ({r['confidence_change']})")

        print(f"\n[Export Agent] Writing structured artifacts to {out_path}...")
        pipeline.export_artifacts(out_path)

        print("\n=======================================================")
        print("                   EXECUTION SUMMARY                   ")
        print("=======================================================")
        print(f"Total Subtitles:        {pipeline.run_state.total_subtitles}")
        print(f"Directly Approved:      {pipeline.run_state.approved_count}")
        print(f"Escalated to Review:    {pipeline.run_state.human_review_count}")
        print(f"Untranslatable/Blocked: {pipeline.run_state.untranslatable_count}")
        print(f"Model Budget Calls:     {pipeline.budget.model_calls_used} / {pipeline.budget.max_model_calls}")
        print(f"Tool Invocations:       {pipeline.budget.tool_calls_used} / {pipeline.budget.max_tool_calls}")
        print(f"Artifacts Created in:   {out_path}")
        print("  -> subtitles.srt")
        print("  -> subtitle_decisions.jsonl")
        print("  -> learned_rules.json")
        print("  -> review_queue.json")
        print("  -> final_report.md\n")

    elif args.command == "replan":
        out_path = Path(args.output_dir).resolve()
        events_file = data_path / "surprise_events.json"
        corrections = []
        if events_file.exists():
            with open(events_file, "r", encoding="utf-8") as f:
                events = json.load(f).get("events", [])
                corr = next((e for e in events if e.get("event_type") == "linguist_correction"), None)
                if corr:
                    corrections.append(corr)

        state = pipeline.run_agentic_workflow(corrections=corrections)
        replan_audit = state.get("replan_audit")
        print("\n[DAG Replanning Audit]")
        print(json.dumps(replan_audit, indent=2))
        pipeline.export_artifacts(out_path)
        print(f"\nUpdated artifacts written to {out_path}")

    elif args.command == "inspect":
        print("\n=======================================================")
        print("          NADI-9 EVIDENCE REPOSITORY INSPECTION        ")
        print("=======================================================\n")
        pipeline.evidence_graph.load_all_sources()
        print(f"[+] Total Evidence Records: {len(pipeline.evidence_graph.evidence_store)}")
        print(f"[+] Lexicon Entries Indexed: {len(pipeline.evidence_graph.lexicon)}")
        print(f"[+] Quarantined Items: {len(pipeline.evidence_graph.quarantined_items)}")
        print(f"[+] Active Cross-Source Conflicts: {len(pipeline.evidence_graph.conflicts)}\n")

        print("--- SOURCE AUTHORITY PRECEDENCE MATRIX ---")
        for src, weight in pipeline.evidence_graph.SOURCE_PRECEDENCE.items():
            print(f"  * {src:22s} -> Authority Weight: {weight:.2f}")

        print("\n--- DETECTED CONFLICTS & RESOLUTIONS ---")
        for c in pipeline.evidence_graph.conflicts:
            print(f"  * Term '{c.term}': {c.source_a} ('{c.source_a_val}') vs {c.source_b} ('{c.source_b_val}')")
            print(f"    Winner: {c.resolution_winner} | Rationale: {c.rationale}")

        print("\n--- SECURITY QUARANTINE LOG ---")
        for q in pipeline.evidence_graph.quarantined_items:
            print(f"  * [{q.id}]: {q.summary} | Reason: {q.quarantine_reason}")

    elif args.command == "verify":
        print("\n=======================================================")
        print("    NADI-9 INDEPENDENT VERIFIER AUDIT (BLIND PHASE)    ")
        print("=======================================================\n")
        pipeline.initialize_and_learn()
        pipeline.process_episode()

        print(f"[+] Verified {len(pipeline.decisions)} Subtitle Lines Independently\n")
        for sub_id, d in pipeline.decisions.items():
            cps_info = f"{d.timing.characters_per_second:.1f} cps" if d.timing else "N/A"
            status_tag = f"[{d.decision}]"
            print(f"  * {sub_id} {status_tag:16s} (Conf: {d.confidence:.2f}, Speed: {cps_info})")
            print(f"    Source: \"{d.source_text}\"")
            print(f"    Nadi-9: \"{d.nadi_9_text or '[ABSTAINED - NO INVENTION]'}\"")
            if d.decision != "APPROVED":
                print(f"    Reason: {d.confidence_reason}")
                if d.review_question:
                    print(f"    Review Question: {d.review_question}")
            print()


if __name__ == "__main__":
    main()
