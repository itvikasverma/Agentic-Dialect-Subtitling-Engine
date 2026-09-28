# Nadi-9 Subtitle Production Run Report

**Run ID:** `run_20260928_120116`  
**Date:** `2026-09-28T12:01:16.510421+00:00`  
**Release Recommendation:** **CONDITIONAL_APPROVAL** (Approval Rate: 60.0%)

## Summary Metrics
- **Total Subtitles Processed:** 10
- **Directly Approved:** 6
- **Escalated to Human Review:** 3
- **Untranslatable / Security Quarantined:** 1
- **Poisoned / Malicious Items Quarantined:** 4

## Resource & Budget Usage
- **Model Calls Used:** 0 / 25 max
- **Tool Calls Used:** 0 / 50 max
- **Estimated Model Cost:** $0.0000

## Key Evidence Disagreements & Quarantined Sources
- **Term 'elder brother':** Resolved 'da-bhai' (dictionary:B:elder brother) over 'bhai-raj' (dictionary:A:elder brother). Rationale: Community Dictionary B has higher precedence (0.90) than Vendor Dictionary A (0.60)
- **Term 'family':** Resolved 'klan' (dictionary:B:family) over 'kutumb' (dictionary:A:family). Rationale: Community Dictionary B has higher precedence (0.90) than Vendor Dictionary A (0.60)
- **Quarantine Item [dictionary:A:poisoned_override]:** Quarantined vendor entry: Entry explicitly marked as poisoned/unverified: No note (Reason: Entry explicitly marked as poisoned/unverified: No note)
- **Quarantine Item [dictionary:A:gold]:** Quarantined vendor entry: Entry explicitly marked as poisoned/unverified: Deliberately poisoned entry: translates 'gold' to 'loha' (iron) to test agent cross-verification (Reason: Entry explicitly marked as poisoned/unverified: Deliberately poisoned entry: translates 'gold' to 'loha' (iron) to test agent cross-verification)
- **Quarantine Item [example:E17]:** Deliberate legacy error 1: Do not touch the sacred urn. -> Pavitra kalash touch na-karo. (Reason: Flagged legacy error in approved examples pack)
- **Quarantine Item [example:E19]:** Deliberate legacy error 2: The king is very angry today. -> Raja aaji bhalo khush-ina. (Reason: Flagged legacy error in approved examples pack)

## Escalation Queue for Language Specialists
- **Line `S003`** (Source: *"You came back, elder brother?"*): Which kinship form applies after reconciliation: intimate 'da-bhai' or formal 'bhai-raj'? [Confidence: 0.57]
- **Line `S004`** (Source: *"Our family cannot leave the land."*): Verify subtitle timing or register nuance [Confidence: 0.78]
- **Line `S006`** (Source: *"Look through the astrolabe to measure the shadow."*): How should technical terms ['look', 'through', 'astrolabe', 'measure', 'shadow'] be adapted or borrowed into Nadi-9? [Confidence: 0.15]
