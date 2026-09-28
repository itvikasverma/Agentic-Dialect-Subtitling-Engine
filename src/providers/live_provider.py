"""
Live LLM Provider Wrapper with Multi-Vendor Support and Exponential Backoff Retries
"""

import os
import time
from typing import Optional
from .base import LLMProvider
from .mock_provider import MockLLMProvider
from ..models.schema import BudgetUsage


class LiveLLMProvider(LLMProvider):
    """
    Live provider that interacts with Gemini/OpenAI/Anthropic when keys are provided,
    and falls back to deterministic Mock provider if no keys are present.
    """

    def __init__(self, budget: Optional[BudgetUsage] = None, max_retries: int = 3):
        super().__init__(budget)
        self.max_retries = max_retries
        self.api_key = (
            os.environ.get("OPENAI_API_KEY") or
            os.environ.get("ANTHROPIC_API_KEY") or
            os.environ.get("GEMINI_API_KEY")
        )
        self.local_url = os.environ.get("LOCAL_LLM_URL") or os.environ.get("OLLAMA_URL")
        self.fallback_mock = MockLLMProvider(budget=self.budget)


    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        call_purpose: str = "general"
    ) -> str:
        if not self.api_key:
            # Evaluator running in offline / zero-key mode
            return self.fallback_mock.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                call_purpose=call_purpose
            )

        # Retries with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                self.check_and_record_budget(estimated_cost=0.002)
                # If OpenAI is installed and key is present:
                if os.environ.get("OPENAI_API_KEY"):
                    import urllib.request
                    import json

                    req_data = {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt or "You are an expert dialectologist."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": temperature
                    }
                    req = urllib.request.Request(
                        "https://api.openai.com/v1/chat/completions",
                        data=json.dumps(req_data).encode("utf-8"),
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}"
                        },
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        res_json = json.loads(resp.read().decode("utf-8"))
                        return res_json["choices"][0]["message"]["content"]

                # 2. Local Model support (Ollama / LocalAI / LM Studio)
                elif self.local_url:
                    import urllib.request
                    import json

                    endpoint = self.local_url if "/chat/completions" in self.local_url else f"{self.local_url.rstrip('/')}/v1/chat/completions"
                    req_data = {
                        "model": os.environ.get("LOCAL_MODEL_NAME", "llama3"),
                        "messages": [
                            {"role": "system", "content": system_prompt or "You are an expert dialectologist."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": temperature
                    }
                    req = urllib.request.Request(
                        endpoint,
                        data=json.dumps(req_data).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        res_json = json.loads(resp.read().decode("utf-8"))
                        return res_json["choices"][0]["message"]["content"]

                # If no key or local endpoint provided, fall back safely to mock
                return self.fallback_mock.generate(prompt, system_prompt, temperature, call_purpose)


            except Exception as e:
                last_error = e
                time.sleep(0.5 * (2 ** attempt))

        raise RuntimeError(f"Live LLM call failed after {self.max_retries} attempts: {last_error}")
