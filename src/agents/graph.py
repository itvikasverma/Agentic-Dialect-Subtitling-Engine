"""
LangGraph Workflow Definition for Nadi-9 Dialect Decision Engine
"""

from typing import Dict, Any
from pathlib import Path
from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .evidence_inspection_agent import EvidenceInspectionAgent
from .risk_planning_agent import RiskPlanningAgent
from .language_learning_agent import LanguageLearningAgent
from .translation_agent import TranslationAgent
from .verification_agent import IndependentVerificationAgent
from .decision_router import DecisionRouterAgent

from ..evidence.evidence_graph import EvidenceGraph
from ..linguist.hypothesis_engine import HypothesisEngine
from ..translator.engine import TranslationEngine
from ..verifier.multi_verifier import MultiPhaseVerifier
from ..replanner.dependency_tracker import DependencyReplanner
from ..providers.base import LLMProvider


def build_nadi9_workflow(
    data_dir: Path,
    provider: LLMProvider,
    evidence_graph: EvidenceGraph,
    hypothesis_engine: HypothesisEngine,
    translator: TranslationEngine,
    verifier: MultiPhaseVerifier,
    replanner: DependencyReplanner
) -> StateGraph:
    """
    Constructs the compiled LangGraph state graph.
    Flow:
      START
        ↓
      Evidence Inspection Agent
        ↓
      Risk / Planning Agent
        ↓
      Language Learning Agent
        ↓
      Translation Agent
        ↓
      Independent Verification Agent
        ↓
      Decision Router (Release / Review Queue / Selective Replanning)
        ↓
      END
    """
    # Instantiate agents
    inspection_agent = EvidenceInspectionAgent(data_dir=data_dir, provider=provider, evidence_graph=evidence_graph)
    risk_agent = RiskPlanningAgent(evidence_graph=evidence_graph, provider=provider)
    learning_agent = LanguageLearningAgent(hypothesis_engine=hypothesis_engine, provider=provider)
    translation_agent = TranslationAgent(translation_engine=translator, provider=provider)
    verification_agent = IndependentVerificationAgent(verifier=verifier, provider=provider)
    router_agent = DecisionRouterAgent(replanner=replanner, provider=provider)

    # Define Node Callables
    def node_evidence_inspection(state: AgentState) -> Dict[str, Any]:
        return inspection_agent.run(state)

    def node_risk_planning(state: AgentState) -> Dict[str, Any]:
        return risk_agent.run(state)

    def node_language_learning(state: AgentState) -> Dict[str, Any]:
        return learning_agent.run(state)

    def node_translation(state: AgentState) -> Dict[str, Any]:
        return translation_agent.run(state)

    def node_independent_verification(state: AgentState) -> Dict[str, Any]:
        return verification_agent.run(state)

    def node_decision_router(state: AgentState) -> Dict[str, Any]:
        return router_agent.run(state)

    # Initialize LangGraph StateGraph
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("evidence_inspection", node_evidence_inspection)
    workflow.add_node("risk_planning", node_risk_planning)
    workflow.add_node("language_learning", node_language_learning)
    workflow.add_node("translation", node_translation)
    workflow.add_node("independent_verification", node_independent_verification)
    workflow.add_node("decision_router", node_decision_router)

    # Add Edges
    workflow.add_edge(START, "evidence_inspection")
    workflow.add_edge("evidence_inspection", "risk_planning")
    workflow.add_edge("risk_planning", "language_learning")
    workflow.add_edge("language_learning", "translation")
    workflow.add_edge("translation", "independent_verification")
    workflow.add_edge("independent_verification", "decision_router")
    workflow.add_edge("decision_router", END)

    return workflow.compile()
