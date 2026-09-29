"""
Sanitization, Poison Detection, and Prompt Injection Defense Engine
"""

import re
from typing import Dict, Any, Tuple, Optional


class EvidenceSanitizer:
    """
    Protects the agent against adversarial attacks embedded in retrieved knowledge:
    1. Prompt injection attempts ('ignore rules', 'system prompt override', etc.)
    2. Poisoned dictionary translations (e.g., vendor corruptions)
    """

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous\s+)?instructions",
        r"system\s+(prompt\s+)?override",
        r"emit\s+english",
        r"ignore\s+the\s+assignment\s+rules",
        r"disregard\s+(the\s+)?assignment",
        r"reveal\s+(your\s+)?prompt",
        r"disregard\s+all\s+prior",
        r"output\s+confidence\s+1\.0",
    ]

    def __init__(self):
        self.compiled_patterns = [
            re.compile(pat, re.IGNORECASE) for pat in self.INJECTION_PATTERNS
        ]

    def scan_for_injection(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Scans any input text for prompt injection keywords.
        Returns (is_suspicious, matched_pattern).
        """
        if not text:
            return False, None
        for pat in self.compiled_patterns:
            match = pat.search(text)
            if match:
                return True, match.group(0)
        return False, None

    def audit_dictionary_entry(
        self, term: str, entry_data: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Audits a dictionary entry for malicious payloads or known poisoning.
        Returns (is_safe, reason).
        """
        # 1. Check explicit poisoned flag
        if entry_data.get("poisoned", False):
            return False, f"Entry explicitly marked as poisoned/unverified: {entry_data.get('notes', 'No note')}"

        # 2. Check for injection payloads inside values or notes
        serialized = f"{term} {entry_data.get('nadi_9', '')} {entry_data.get('payload', '')} {entry_data.get('notes', '')}"
        is_inj, pattern = self.scan_for_injection(serialized)
        if is_inj:
            return False, f"Prompt injection payload matched pattern: '{pattern}'"

        return True, "Safe"
