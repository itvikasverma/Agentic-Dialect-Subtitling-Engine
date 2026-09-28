"""
Deterministic Mock Provider for Offline Evaluation and Reproducible Testing
"""

from typing import Optional, Dict, Any, List
from .base import LLMProvider
from ..models.schema import BudgetUsage
import json


class MockLLMProvider(LLMProvider):
    """
    Mock provider that generates structured responses for Nadi-9 tasks without network calls.
    Allows testing error injection, budget exhaustion, and offline reproducibility.
    """

    def __init__(
        self,
        budget: Optional[BudgetUsage] = None,
        fail_next_n_calls: int = 0,
        failure_exception_type: type = TimeoutError
    ):
        super().__init__(budget)
        self.fail_next_n_calls = fail_next_n_calls
        self.failure_exception_type = failure_exception_type
        self.call_history: List[Dict[str, Any]] = []

    def trigger_transient_failure(self, count: int = 1):
        self.fail_next_n_calls = count

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        call_purpose: str = "general"
    ) -> str:
        # Check simulated failure
        if self.fail_next_n_calls > 0:
            self.fail_next_n_calls -= 1
            raise self.failure_exception_type("Simulated transient connection timeout to LLM provider.")

        # Enforce budget
        self.check_and_record_budget(estimated_cost=0.0005)

        self.call_history.append({
            "purpose": call_purpose,
            "prompt_length": len(prompt),
            "system_prompt": system_prompt
        })

        # Purpose-driven deterministic mock responses
        if call_purpose == "extract_hypotheses":
            return json.dumps({
                "hypotheses": [
                    {
                        "rule_id": "grammar:word-order",
                        "category": "word_order",
                        "statement": "Canonical SOV word order. Adverbs precede verbs.",
                        "confidence": 0.95
                    },
                    {
                        "rule_id": "grammar:tense-present",
                        "category": "tense",
                        "statement": "Present continuous marker is -ina suffix on verb root.",
                        "confidence": 0.95
                    },
                    {
                        "rule_id": "grammar:respect-kinship",
                        "category": "respect",
                        "statement": "Elder brother intimate register uses da- prefix; formal register uses bhai-raj.",
                        "confidence": 0.85
                    }
                ]
            })

        if call_purpose == "verifier_independent":
            # Check prompt content to generate realistic verifier decision
            if "astrolabe" in prompt.lower():
                return json.dumps({
                    "verdict": "REJECT",
                    "issues": ["Term 'astrolabe' has zero grounding in Dictionary A, B, or approved examples."],
                    "risk_level": "CRITICAL"
                })
            elif "poisoned_override" in prompt.lower():
                return json.dumps({
                    "verdict": "REJECT",
                    "issues": ["Suspicious prompt injection payload detected in source text."],
                    "risk_level": "SECURITY_ALERT"
                })
            else:
                return json.dumps({
                    "verdict": "PASS",
                    "issues": [],
                    "risk_level": "LOW"
                })

        return json.dumps({"status": "acknowledged", "purpose": call_purpose})
