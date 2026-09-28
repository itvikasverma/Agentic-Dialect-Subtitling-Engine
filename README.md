# Nadi-9 Agentic Dialect Subtitling Engine

**OTT Dialect Platform | AI Engineering Hiring Challenge: "Learn a Dialect That Does Not Exist"**

An evidence-grounded agentic engine that learns a fictional language (*Nadi-9*) from limited and conflicting sources, then produces calibrated, verifiable subtitles without hallucinating unsupported terms.

---

## Key Highlights

- **Epistemic Evidence Precedence:** Strict hierarchy across disparate sources (`Linguist Correction` > `Grammar Notes` > `Community Dict B` > `Audio` > `Approved Examples` > `Vendor Dict A` > `Viewer Feedback`).
- **Independent Verifier Architecture:** Generation and verification are strictly decoupled to prevent self-approving LLM loops.
- **DAG-Based Dependency Replanner:** When a linguist provides a correction mid-run, the dependency graph invalidates and reprocesses **only** the affected subtitle lines without re-running the entire episode.
- **Adversarial Security & Quarantine:** Detects prompt injections (`SYSTEM OVERRIDE`, `ignore instructions`) and poisoned dictionary entries, quarantining them before they can influence decisions.
- **Calibrated Abstention:** Low-confidence or ungrounded terms (e.g. esoteric technical concepts) cleanly escalate to `HUMAN_REVIEW` with precise review questions instead of hallucinating fluent-sounding inventions.
- **Zero-Key Deterministic Mock Mode:** Evaluators can run the entire test suite and CLI pipeline offline with zero external API key requirements.

---

## Required Submission Structure (Page 5 Compliance)

The repository layout strictly matches the assignment structure specified in the candidate brief:

```text
submission/ (Repository Root)
├── README.md                # Setup guide and usage instructions
├── ARCHITECTURE.md          # In-depth architectural specification and trust boundaries
├── AI_COLLABORATION.md      # Record of AI assistance, tool delegation, and critical reviews
├── KNOWN_LIMITATIONS.md     # Explicit catalog of intentional tradeoffs and future work
├── src/                     # Core agentic pipeline and models
│   ├── cli.py               # CLI entrypoint
│   ├── pipeline.py          # Master orchestrator & artifact exporter
│   ├── evidence/            # EvidenceGraph & EvidenceSanitizer
│   ├── linguist/            # Hypothesis formation & counterexample auditor
│   ├── models/              # Pydantic schemas (SubtitleDecision, BudgetUsage, etc.)
│   ├── providers/           # Base, Mock, and Live LLM providers
│   ├── replanner/           # DAG dependency tracker & selective replanner
│   ├── translator/          # Context-aware translation proposal engine
│   └── verifier/            # Multi-phase independent verifier & CPS auditor
├── tests/
│   └── test_nadi9_agent.py  # Pytest suite covering all mandatory evaluation criteria
├── data/                    # The Nadi-9 assignment data pack
│   ├── approved_examples.json
│   ├── audio_interviews.json
│   ├── dictionary_a.json    # Contains poisoned entries & injection payloads
│   ├── dictionary_b.json    # Community dictionary with conflicting terms
│   ├── expert_notes.json
│   ├── grammar_note.json
│   ├── viewer_feedback.json # Contains valuable signal + noise
│   ├── episode_package.json # Episode subtitles with scene/speaker metadata
│   └── surprise_events.json # Mid-run corrections, transient failures
└── sample_run/              # Verified execution outputs
    ├── subtitles.srt        # Production subtitle file
    ├── subtitle_decisions.jsonl # Required machine-readable decisions
    ├── learned_rules.json   # Extracted grammar hypotheses & counterexamples
    ├── review_queue.json    # Human linguist escalation items
    └── final_report.md      # Summary release recommendation & budget stats
```

---

## Model Execution Modes (Hosted, Local, or Mock/Replay)

As required by Section 7 & 8 of the candidate brief, the engine provides full provider flexibility:

1. **Mock / Replay Mode (Default - Zero API Key Needed):**
   - Runs 100% offline using deterministic linguistic heuristics and verifier audits.
   - Evaluators can run the entire test suite and CLI pipeline without spending a cent or configuring credentials.
   ```bash
   python -m src.cli run --mock
   ```

2. **Hosted Models (OpenAI, Anthropic, Gemini):**
   - Set your API key in the environment. The system routes calls with automatic backoff retries and enforces the **25 model call budget**.
   ```bash
   export OPENAI_API_KEY="sk-..."
   python -m src.cli run --mock=False
   ```

3. **Local Models (Ollama, vLLM, LM Studio):**
   - Connect any locally hosted open-weights model (e.g. LLaMA-3, Mistral, Qwen) running on your machine:
   ```bash
   export LOCAL_LLM_URL="http://localhost:11434"
   export LOCAL_MODEL_NAME="llama3"
   python -m src.cli run --mock=False
   ```

---

## Quickstart & Evaluation Guide


### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- `pip install pydantic pytest`

### 1. Run the Automated Test Suite
Runs the 6 automated tests covering the 4 mandatory assignment conditions:
```bash
python -m pytest -v
```

### 2. Inspect Extracted Hypotheses & Conflicts
Extracts grammatical rules, empirical counterexamples, and quarantines poisoned entries:
```bash
python -m src.cli learn
```

### 3. Run the Complete Subtitling Pipeline
Processes the episode, executes independent multi-phase verification, simulates a mid-run correction, and outputs all artifacts to `sample_run/`:
```bash
python -m src.cli run --simulate-correction
```

### 4. Test Selective Replanning
Injects a linguist correction and updates only impacted subtitles:
```bash
python -m src.cli replan
```

---

## Required Output Schema Compliance

Every subtitle line in `sample_run/subtitle_decisions.jsonl` strictly satisfies the Section 4 specification:
```json
{
  "subtitle_id": "S003",
  "source_text": "You came back, elder brother?",
  "nadi_9_text": "Ne ghum-va, vad-bhai?",
  "confidence": 0.79,
  "decision": "HUMAN_REVIEW",
  "evidence": ["correction:CORRECTION_01", "dictionary:B:elder brother", "example:E07", "grammar:respect-kinship"],
  "assumptions": ["Speaker 'Sister' addresses 'Elder Son' with relationship 'Kinship / Reconciled after long dispute'"],
  "conflicts": ["dictionary:B:elder brother vs dictionary:A:elder brother"],
  "review_question": "Verify subtitle timing or register nuance"
}
```