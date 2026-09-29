"""
Evidence Graph and Epistemic Source Precedence Engine
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from ..models.schema import EvidenceReference, ConflictItem
from .sanitizer import EvidenceSanitizer


class EvidenceGraph:
    """
    Maintains structured knowledge from disparate, conflicting sources with calibrated trust weights:
    - Grammar notes: 0.95 (field-verified morphology)
    - Dictionary B (community): 0.90
    - Audio interviews: 0.85
    - Approved examples: 0.80 (2 known legacy errors quarantined)
    - Expert notes: 0.75
    - Dictionary A (vendor): 0.60 (unverified, subject to quarantine)
    - Viewer feedback: 0.40 (requires noise filtering)
    """

    SOURCE_PRECEDENCE = {
        "linguist_correction": 0.98,
        "grammar_note": 0.95,
        "dictionary_b": 0.90,
        "audio_interview": 0.85,
        "approved_example": 0.80,
        "expert_note": 0.75,
        "dictionary_a": 0.60,
        "viewer_feedback": 0.40,
    }

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.sanitizer = EvidenceSanitizer()
        self.evidence_store: Dict[str, EvidenceReference] = {}
        self.lexicon: Dict[str, Dict[str, Any]] = {}
        self.conflicts: List[ConflictItem] = []
        self.quarantined_items: List[EvidenceReference] = []
        self.raw_grammar_rules: List[Dict[str, Any]] = []
        self.approved_examples: List[Dict[str, Any]] = []

    def load_all_sources(self):
        """Loads and ingests all provided assignment materials."""
        self._load_grammar_notes()
        self._load_dictionaries()
        self._load_approved_examples()
        self._load_audio_interviews()
        self._load_expert_notes()
        self._load_viewer_feedback()

    def _load_grammar_notes(self):
        path = self.data_dir / "grammar_note.json"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            author = data.get("author", "Dr. A. Sharma")
            date = data.get("date", "2026-01-15")
            scope = data.get("scope", "Morphosyntax and honorifics")
            for rule in data.get("rules", []):
                ref_id = rule["rule_id"]
                ref = EvidenceReference(
                    id=ref_id,
                    source_type="grammar_note",
                    author=author,
                    date=date,
                    scope=scope,
                    reliability_weight=self.SOURCE_PRECEDENCE["grammar_note"],
                    summary=rule["statement"],
                    raw_payload=rule,
                    claims=[rule["statement"]],
                    grammar_observations=[rule["statement"]],
                    register_info=rule.get("category"),
                )
                self.evidence_store[ref_id] = ref
                self.raw_grammar_rules.append(rule)

    def _load_dictionaries(self):
        # 1. Load Dictionary B first (higher community precedence)
        dict_b_path = self.data_dir / "dictionary_b.json"
        if dict_b_path.exists():
            with open(dict_b_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                compiler = data.get("compiler", "Community Elders Assembly")
                date = data.get("date", "2025-11-20")
                scope = data.get("scope", "Living conversational lexicon")
                for term, details in data.get("terms", {}).items():
                    safe, reason = self.sanitizer.audit_dictionary_entry(term, details)
                    ref_id = f"dictionary:B:{term}"
                    if not safe:
                        q_ref = EvidenceReference(
                            id=ref_id,
                            source_type="dictionary_b",
                            author=compiler,
                            date=date,
                            scope=scope,
                            reliability_weight=0.0,
                            summary=f"Quarantined: {reason}",
                            raw_payload=details,
                            quarantined=True,
                            quarantine_reason=reason,
                        )
                        self.quarantined_items.append(q_ref)
                        continue

                    ref = EvidenceReference(
                        id=ref_id,
                        source_type="dictionary_b",
                        author=compiler,
                        date=date,
                        scope=scope,
                        reliability_weight=self.SOURCE_PRECEDENCE["dictionary_b"],
                        summary=f"{term} -> {details.get('nadi_9')}",
                        raw_payload=details,
                        terms={term: details.get("nadi_9", "")},
                        claims=[f"Definition: {details.get('nadi_9')}"],
                        register_info=details.get("notes"),
                    )
                    self.evidence_store[ref_id] = ref
                    self.lexicon[term.lower()] = {
                        "nadi_9": details.get("nadi_9"),
                        "pos": details.get("pos"),
                        "source": "dictionary_b",
                        "evidence_id": ref_id,
                        "reliability": self.SOURCE_PRECEDENCE["dictionary_b"],
                        "notes": details.get("notes", ""),
                    }

        # 2. Load Dictionary A (vendor, lower precedence, cross-reference conflicts)
        dict_a_path = self.data_dir / "dictionary_a.json"
        if dict_a_path.exists():
            with open(dict_a_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                compiler = data.get("compiler", "Vendor Harvester Corp")
                date = data.get("date", "2024-06-10")
                scope = data.get("scope", "Automated lexical scrape")
                for term, details in data.get("terms", {}).items():
                    norm_term = term.lower()
                    safe, reason = self.sanitizer.audit_dictionary_entry(term, details)
                    ref_id = f"dictionary:A:{term}"

                    if not safe:
                        q_ref = EvidenceReference(
                            id=ref_id,
                            source_type="dictionary_a",
                            author=compiler,
                            date=date,
                            scope=scope,
                            reliability_weight=0.0,
                            summary=f"Quarantined vendor entry: {reason}",
                            raw_payload=details,
                            quarantined=True,
                            quarantine_reason=reason,
                        )
                        self.quarantined_items.append(q_ref)
                        continue

                    ref = EvidenceReference(
                        id=ref_id,
                        source_type="dictionary_a",
                        author=compiler,
                        date=date,
                        scope=scope,
                        reliability_weight=self.SOURCE_PRECEDENCE["dictionary_a"],
                        summary=f"{term} -> {details.get('nadi_9')}",
                        raw_payload=details,
                        terms={term: details.get("nadi_9", "")},
                        claims=[f"Vendor mapping: {details.get('nadi_9')}"],
                        register_info=details.get("notes"),
                    )
                    self.evidence_store[ref_id] = ref

                    # Check for conflicts against existing Dictionary B
                    if norm_term in self.lexicon:
                        existing = self.lexicon[norm_term]
                        if existing["nadi_9"] != details.get("nadi_9"):
                            conflict = ConflictItem(
                                term=norm_term,
                                source_a=existing["evidence_id"],
                                source_a_val=existing["nadi_9"],
                                source_b=ref_id,
                                source_b_val=details.get("nadi_9"),
                                impact="Lexical disagreement between community consensus and vendor harvester",
                                resolved=True,
                                resolution_winner=existing["evidence_id"],
                                rationale="Community Dictionary B has higher precedence (0.90) than Vendor Dictionary A (0.60)",
                            )
                            self.conflicts.append(conflict)
                    else:
                        # Uncontested term from Dictionary A
                        self.lexicon[norm_term] = {
                            "nadi_9": details.get("nadi_9"),
                            "pos": details.get("pos"),
                            "source": "dictionary_a",
                            "evidence_id": ref_id,
                            "reliability": self.SOURCE_PRECEDENCE["dictionary_a"],
                            "notes": details.get("notes", ""),
                        }

    def _load_approved_examples(self):
        path = self.data_dir / "approved_examples.json"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            author = data.get("author", "STAGE Dialect Board")
            date = data.get("date", "2025-08-01")
            for ex in data.get("examples", []):
                ref_id = f"example:{ex['id']}"
                # Flag known legacy flaws
                is_flawed = "FLAWED" in ex.get("notes", "") or ex["id"] in ["E17", "E19"]
                weight = 0.20 if is_flawed else self.SOURCE_PRECEDENCE["approved_example"]
                ref = EvidenceReference(
                    id=ref_id,
                    source_type="approved_example",
                    author=author,
                    date=date,
                    scope="Corpus benchmark",
                    reliability_weight=weight,
                    summary=f"{ex['source']} -> {ex['target']}",
                    raw_payload=ex,
                    claims=[f"Translation: {ex['source']} -> {ex['target']}"],
                    quarantined=is_flawed,
                    quarantine_reason="Flagged legacy error in approved examples pack" if is_flawed else None,
                )
                self.evidence_store[ref_id] = ref
                if not is_flawed:
                    self.approved_examples.append(ex)
                else:
                    self.quarantined_items.append(ref)

    def _load_audio_interviews(self):
        path = self.data_dir / "audio_interviews.json"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            date = data.get("date", "2026-02-10")
            for aud in data.get("interviews", []):
                ref_id = f"audio:{aud['id']}"
                ref = EvidenceReference(
                    id=ref_id,
                    source_type="audio_interview",
                    author=aud.get("speaker", "Native Speaker"),
                    date=date,
                    scope="Spoken phonology and dialect register",
                    reliability_weight=self.SOURCE_PRECEDENCE["audio_interview"],
                    summary=f"Native audio discussion on {aud['topic']}",
                    raw_payload=aud,
                    claims=[aud.get("key_phrase", aud.get("topic", ""))],
                )
                self.evidence_store[ref_id] = ref

    def _load_expert_notes(self):
        path = self.data_dir / "expert_notes.json"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            date = data.get("date", "2026-02-14")
            for exp in data.get("experts", []):
                ref_id = f"expert:{exp['expert_id']}"
                ref = EvidenceReference(
                    id=ref_id,
                    source_type="expert_note",
                    author=exp["name"],
                    date=date,
                    scope="Dialectology analysis",
                    reliability_weight=self.SOURCE_PRECEDENCE["expert_note"],
                    summary=exp["notes"],
                    raw_payload=exp,
                    claims=[exp["notes"]],
                )
                self.evidence_store[ref_id] = ref

    def _load_viewer_feedback(self):
        path = self.data_dir / "viewer_feedback.json"
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            date = data.get("date", "2026-03-01")
            for fb in data.get("feedback_items", []):
                ref_id = f"feedback:{fb['id']}"
                is_signal = fb.get("valuable_signal", False)
                ref = EvidenceReference(
                    id=ref_id,
                    source_type="viewer_feedback",
                    author=fb["user"],
                    date=date,
                    scope="Audience perception",
                    reliability_weight=self.SOURCE_PRECEDENCE["viewer_feedback"] if is_signal else 0.05,
                    summary=fb["text"],
                    raw_payload=fb,
                    claims=[fb["text"]],
                    quarantined=not is_signal,
                    quarantine_reason="Viewer noise / ungrounded opinion" if not is_signal else None,
                )
                self.evidence_store[ref_id] = ref

    def lookup_term(self, term: str) -> Optional[Dict[str, Any]]:
        norm = term.lower().strip("?,.!")
        return self.lexicon.get(norm)

    def apply_linguist_correction(self, correction_event: Dict[str, Any]):
        """
        Dynamically applies a mid-run correction from a human linguist,
        updating affected entries with top precedence (0.98).
        """
        event_id = correction_event.get("event_id", "CORRECTION_EVENT")
        details = correction_event.get("correction_details", {})
        term = details.get("term", "").lower()
        new_val = details.get("new_value")
        ref_id = f"correction:{event_id}"

        ref = EvidenceReference(
            id=ref_id,
            source_type="linguist_correction",
            author=correction_event.get("author", "Lead Field Linguist"),
            reliability_weight=self.SOURCE_PRECEDENCE["linguist_correction"],
            summary=correction_event.get("description", "Linguist override"),
            raw_payload=correction_event,
        )
        self.evidence_store[ref_id] = ref

        # If it affects an existing term or registers
        if term:
            self.lexicon[term] = {
                "nadi_9": new_val,
                "pos": "corrected",
                "source": "linguist_correction",
                "evidence_id": ref_id,
                "reliability": self.SOURCE_PRECEDENCE["linguist_correction"],
                "notes": correction_event.get("description", ""),
            }

        return ref_id
