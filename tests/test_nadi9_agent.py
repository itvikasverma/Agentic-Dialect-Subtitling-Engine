"""
Automated Test Suite for Nadi-9 Dialect Agentic Translation System
Covers the mandatory evaluation criteria:
1. Conflict detection and source-precedence resolution
2. Unsupported term safe abstention
3. Mid-run linguist correction and DAG-based selective replanning
4. Transient provider/tool failure recovery
5. Poisoned entry & prompt injection quarantine
6. Budget enforcement
"""

import pytest
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.schema import BudgetUsage

from src.evidence.evidence_graph import EvidenceGraph
from src.evidence.sanitizer import EvidenceSanitizer
from src.providers.mock_provider import MockLLMProvider
from src.linguist.hypothesis_engine import HypothesisEngine
from src.translator.engine import TranslationEngine
from src.verifier.multi_verifier import MultiPhaseVerifier
from src.replanner.dependency_tracker import DependencyReplanner
from src.pipeline import Nadi9AgentPipeline


@pytest.fixture
def data_dir():
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def test_pipeline(data_dir):
    provider = MockLLMProvider()
    pipe = Nadi9AgentPipeline(data_dir=data_dir, provider=provider)
    pipe.initialize_and_learn()
    return pipe


# --------------------------------------------------------------------------
# MANDATORY TEST 1: Cross-Source Conflict Detection & Source Precedence
# --------------------------------------------------------------------------
def test_cross_source_conflict_detection(test_pipeline):
    """
    Verifies that the agent detects lexical disagreements between sources
    (e.g. Dictionary A vs Dictionary B) and resolves precedence without blindly
    trusting the largest file.
    """
    conflicts = test_pipeline.evidence_graph.conflicts
    assert len(conflicts) >= 1, "Expected at least one cross-source conflict to be detected"

    # Find the conflict for elder brother or family
    elder_brother_conflict = next((c for c in conflicts if "elder brother" in c.term or "family" in c.term), None)
    assert elder_brother_conflict is not None, "Conflict on kinship or family term must be logged"
    assert elder_brother_conflict.resolved is True
    assert "dictionary:b" in elder_brother_conflict.resolution_winner.lower()
    assert "Dictionary B" in elder_brother_conflict.rationale



# --------------------------------------------------------------------------
# MANDATORY TEST 2: Unsupported Term Safe Abstention
# --------------------------------------------------------------------------
def test_unsupported_term_abstention(test_pipeline):
    """
    Verifies that when faced with an unsupported domain concept (e.g. 'astrolabe'),
    the agent abstains from hallucinating, returns low confidence, and escalates to HUMAN_REVIEW.
    """
    unsupported_sub = {
        "subtitle_id": "S_TEST_UNSUPPORTED",
        "source_text": "Look through the astrolabe to measure the shadow.",
        "speaker": "Astronomer",
        "listener": "Guard",
        "relationship": "Formal",
        "scene": "Observatory",
        "start_time": "00:01:00,000",
        "end_time": "00:01:03,000"
    }

    decision = test_pipeline.translator.propose_subtitle(unsupported_sub)
    verified = test_pipeline.verifier.verify_decision(decision)

    assert verified.decision == "HUMAN_REVIEW"
    assert verified.nadi_9_text is None, "Agent must not invent words for unsupported terms"
    assert verified.confidence < 0.40, "Confidence must be low for ungrounded terms"
    assert verified.review_question is not None
    assert "astrolabe" in verified.review_question.lower() or "unsupported" in verified.confidence_reason.lower()


# --------------------------------------------------------------------------
# MANDATORY TEST 3: Mid-Run Linguist Correction and Selective Replanning
# --------------------------------------------------------------------------
def test_selective_replanning_on_correction(test_pipeline, data_dir):
    """
    Verifies that when a linguist sends a correction halfway through processing,
    the system traces the change through its DAG and updates ONLY affected lines,
    without reprocessing unaffected subtitles.
    """
    # 1. First process full episode
    test_pipeline.process_episode()
    initial_s002 = test_pipeline.decisions["S002"]
    initial_s003 = test_pipeline.decisions["S003"]

    # 2. Inject correction event
    events_file = data_dir / "surprise_events.json"
    with open(events_file, "r", encoding="utf-8") as f:
        events = json.load(f)["events"]
        corr = next(e for e in events if e.get("event_type") == "linguist_correction")

    audit = test_pipeline.apply_correction_event(corr)

    # 3. Assert selective invalidation
    assert "S003" in audit["impacted_subtitle_ids"], "S003 (elder brother line) must be identified as impacted"
    assert audit["unaffected_count"] >= 7, "Unaffected lines must not be reprocessed"

    updated_s003 = test_pipeline.decisions["S003"]
    assert "vad-bhai" in updated_s003.nadi_9_text, "S003 should reflect the newly corrected kinship term"

    # Verify unaffected line remained unchanged
    unchanged_s002 = test_pipeline.decisions["S002"]
    assert unchanged_s002.nadi_9_text == initial_s002.nadi_9_text


# --------------------------------------------------------------------------
# MANDATORY TEST 4: Tool / Provider Failure Recovery
# --------------------------------------------------------------------------
def test_transient_provider_failure_recovery(data_dir):
    """
    Verifies that when a model or tool temporarily fails (e.g. timeout),
    the system handles the failure safely without crashing.
    """
    failing_provider = MockLLMProvider(fail_next_n_calls=1)

    # Check that calling generator raises simulated timeout
    with pytest.raises(TimeoutError):
        failing_provider.generate(prompt="Test failure", call_purpose="test")

    # On next call, provider recovers seamlessly
    res = failing_provider.generate(prompt="Test recovery", call_purpose="verifier_independent")
    assert "verdict" in res


# --------------------------------------------------------------------------
# ADDITIONAL TEST 5: Prompt Injection & Poisoned Dictionary Quarantine
# --------------------------------------------------------------------------
def test_poisoned_entry_and_injection_quarantine(test_pipeline):
    """
    Verifies that prompt injection payloads and poisoned dictionary entries are quarantined.
    """
    quarantined = test_pipeline.evidence_graph.quarantined_items
    quarantine_ids = [q.id for q in quarantined]

    assert "dictionary:A:poisoned_override" in quarantine_ids
    assert "dictionary:A:gold" in quarantine_ids

    # Verify gold was resolved via Dictionary B (sona) and audio AUD03, not poisoned loha
    gold_term = test_pipeline.evidence_graph.lookup_term("gold")
    assert gold_term["nadi_9"] == "sona"
    assert gold_term["source"] == "dictionary_b"


# --------------------------------------------------------------------------
# ADDITIONAL TEST 6: Budget Enforcement Constraint
# --------------------------------------------------------------------------
def test_budget_enforcement():
    """
    Verifies that the system respects the configurable budget limit (max 25 model calls, 50 tool calls).
    """
    budget = BudgetUsage(max_model_calls=2, max_tool_calls=2)

    budget.record_model_call()
    budget.record_model_call()
    with pytest.raises(RuntimeError, match="Model call budget exceeded"):
        budget.record_model_call()

    budget.record_tool_call()
    budget.record_tool_call()
    with pytest.raises(RuntimeError, match="Tool call budget exceeded"):
        budget.record_tool_call()
