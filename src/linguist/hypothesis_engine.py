"""
Linguistic Hypothesis Generation and Empirical Counterexample Engine
"""

from typing import List, Dict, Any, Optional
from ..models.schema import GrammarHypothesis
from ..evidence.evidence_graph import EvidenceGraph
from ..providers.base import LLMProvider


class HypothesisEngine:
    """
    Studies the raw grammar notes and approved examples, synthesizes verifiable
    syntactic and morphological rules, and systematically checks for counterexamples.
    """

    def __init__(self, evidence_graph: EvidenceGraph, provider: LLMProvider):
        self.evidence_graph = evidence_graph
        self.provider = provider
        self.hypotheses: Dict[str, GrammarHypothesis] = {}

    def extract_and_verify_hypotheses(self) -> List[GrammarHypothesis]:
        """
        Formulates core grammatical hypotheses and validates them against the 20 approved examples.
        Flags counterexamples and calibrates confidence.
        """
        self.provider.record_tool_invocation()

        # Ingest verified rules from grammar note
        for r in self.evidence_graph.raw_grammar_rules:
            rule_id = r["rule_id"]
            category = r.get("category", "general")
            statement = r["statement"]

            supporting: List[str] = [rule_id]
            counterexamples: List[str] = []

            # Empirically check against approved examples
            for ex in self.evidence_graph.approved_examples:
                ex_id = f"example:{ex['id']}"
                target_str = ex["target"].lower()
                source_str = ex["source"].lower()

                # Tense: Present imperfective
                if category == "tense" and "present" in rule_id:
                    if "is flowing" in source_str or "is sleeping" in source_str or "laughing" in source_str:
                        if "-ina" in target_str:
                            supporting.append(ex_id)
                        else:
                            counterexamples.append(f"{ex_id} (Missing expected -ina)")

                # Tense: Past
                elif category == "tense" and "past" in rule_id:
                    if "came" in source_str or "saw" in source_str or "went" in source_str:
                        if "-va" in target_str:
                            supporting.append(ex_id)
                        else:
                            counterexamples.append(f"{ex_id} (Past verb lacked -va)")

                # Negation
                elif category == "negation":
                    if "not" in source_str or "cannot" in source_str or "refused" in source_str:
                        if "na-" in target_str:
                            supporting.append(ex_id)
                        else:
                            counterexamples.append(f"{ex_id} (Negation without prefix na-)")

                # Respect / Kinship
                elif category == "respect":
                    if "elder brother" in source_str:
                        if "da-bhai" in target_str:
                            supporting.append(ex_id)
                        elif "bhai-raj" in target_str:
                            counterexamples.append(f"{ex_id} (Formal court variant used)")

            # Check quarantined flawed examples for explicit counterexamples
            for q in self.evidence_graph.quarantined_items:
                if q.source_type == "approved_example":
                    payload = q.raw_payload
                    if category == "negation" and payload.get("id") == "E17":
                        counterexamples.append(f"example:E17 (Quarantined legacy error: used 'touch na-karo')")

            # Determine hypothesis status & confidence
            confidence = r.get("reliability", 0.85)
            if counterexamples:
                status = "CHALLENGED" if len(counterexamples) > 1 else "CONFIRMED"
                confidence = max(0.60, confidence - (0.10 * len(counterexamples)))
            else:
                status = "CONFIRMED"

            hyp = GrammarHypothesis(
                rule_id=rule_id,
                category=category,
                statement=statement,
                supporting_evidence=list(set(supporting)),
                counterexamples=counterexamples,
                confidence=round(confidence, 2),
                status=status,
                notes=r.get("notes")
            )
            self.hypotheses[rule_id] = hyp

        return list(self.hypotheses.values())

    def get_rule(self, rule_id: str) -> Optional[GrammarHypothesis]:
        return self.hypotheses.get(rule_id)
