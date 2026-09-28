"""
Abstract Base Class and Budget Enforcement for LLM Providers
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from ..models.schema import BudgetUsage


class LLMProvider(ABC):
    def __init__(self, budget: Optional[BudgetUsage] = None):
        self.budget = budget or BudgetUsage()

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        call_purpose: str = "general"
    ) -> str:
        """Execute a text generation call and record budget usage."""
        pass

    def check_and_record_budget(self, estimated_cost: float = 0.001):
        self.budget.record_model_call(cost=estimated_cost)

    def record_tool_invocation(self):
        self.budget.record_tool_call()
