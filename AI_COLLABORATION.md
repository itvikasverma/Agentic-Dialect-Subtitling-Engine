# AI Collaboration & Engineering Log

## Overview
This log documents the collaboration between the human engineer and AI coding assistants throughout the development of the Nadi-9 translation system. It highlights where AI provided leverage, where suggestions were challenged or rejected, and how outputs were verified.

---

## 1. Where AI Was Delegated Work
1. **Pydantic Schema Scaffolding:** Prompted the assistant to draft the strict `SubtitleDecision` schema adhering to the candidate brief's exact JSON keys (`confidence_reason`, `conflicts`, `review_question`).
2. **Deterministic Mock Generation:** Delegated the creation of offline mock structures so evaluators can run the test suite without requiring personal API keys.
3. **Adversarial Security Pattern Drafting:** Drafted regex patterns to catch prompt injections like `SYSTEM PROMPT OVERRIDE` and `ignore instructions`.
4. **Pytest Test Case Templating:** Drafted unit test fixtures verifying conflict resolution, abstention on ungrounded terms, and DAG invalidation.

---

## 2. AI Suggestions That Were Challenged or Rejected

### Case 1: Re-translating the entire episode upon linguist correction
- **AI Suggestion:** The assistant initially suggested a simple function `replan()` that cleared the decision dictionary and ran `process_episode()` from scratch.
- **Why Rejected:** The candidate brief explicitly flags this under *"What will score poorly: reprocessing everything after a small correction"*.
- **Engineering Action:** We rejected the re-execution loop and instead implemented a DAG-based `DependencyReplanner`. When a rule or lexical root is modified, only nodes directly connected to that dependency in the DAG are invalidated and re-evaluated.

### Case 2: Naive LLM self-evaluation loop
- **AI Suggestion:** The assistant proposed using the same prompt and model to generate the subtitle and then ask: *"Did you follow all grammar rules? Answer YES or NO."*
- **Why Rejected:** Self-evaluating LLMs suffer from high confirmation bias and will confidently validate their own hallucinations.
- **Engineering Action:** Decoupled verification into a dedicated `MultiPhaseVerifier` that combines deterministic rule audits (regex token verification, timing CPS formulas) with an independent prompt persona.

### Case 3: Automatic fallback translation for missing words
- **AI Suggestion:** The assistant recommended using phonetic transliteration or English loanwords when a word was not found in the dictionaries (e.g. for *"astrolabe"*).
- **Why Rejected:** Violates the core assignment principle: *"The system should behave like a careful junior linguist working with imperfect references, not like a general-purpose translator that always returns an answer."*
- **Engineering Action:** Enforced explicit abstention (`HUMAN_REVIEW` with `confidence < 0.20` and `nadi_9_text = null`).

---

## 3. Verification Protocol
All code and test fixtures generated with assistant support underwent the following verification gates:
- Run with strict typing checks and Pydantic v2 validation.
- Validated via `pytest -v` ensuring all 21 automated tests execute in ~0.8s without network dependencies.
- Verified against the provided CLI commands (`python -m src.cli learn`, `run --mock`, `run --mock --simulate-correction`, `replan`, `inspect`, `verify`).
- Verified against LangGraph stateful execution graph with typed `AgentState` models.
