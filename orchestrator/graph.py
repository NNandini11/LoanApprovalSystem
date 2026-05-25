"""LangGraph state machine wiring the 4 loan-approval agents.

Linear flow: profile -> risk -> decision -> compliance.
Each node POSTs to a FastAPI agent and merges the response into LoanState.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.logging_utils import get_logger
from common.schemas import (
    ApplicantProfileResult,
    ComplianceActionResult,
    FinancialRiskResult,
    LoanApplication,
    LoanDecisionResult,
)
from orchestrator.state import LoanState

log = get_logger("orchestrator")

AGENT_URLS = {
    "profile": "http://127.0.0.1:8001/analyze",
    "risk": "http://127.0.0.1:8002/analyze",
    "decision": "http://127.0.0.1:8003/analyze",
    "compliance": "http://127.0.0.1:8004/analyze",
}

HTTP_TIMEOUT = httpx.Timeout(60.0, connect=5.0)


async def _post(url: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


async def profile_node(state: LoanState) -> LoanState:
    log.info("[node:profile] start applicant=%s", state["application"].applicant_id)
    data = await _post(AGENT_URLS["profile"], state["application"].model_dump(mode="json"))
    return {"profile": ApplicantProfileResult(**data)}


async def risk_node(state: LoanState) -> LoanState:
    log.info("[node:risk] start")
    payload = {
        "application": state["application"].model_dump(mode="json"),
        "profile": state["profile"].model_dump(),
    }
    data = await _post(AGENT_URLS["risk"], payload)
    return {"risk": FinancialRiskResult(**data)}


async def decision_node(state: LoanState) -> LoanState:
    log.info("[node:decision] start")
    payload = {
        "application": state["application"].model_dump(mode="json"),
        "profile": state["profile"].model_dump(),
        "risk": state["risk"].model_dump(),
    }
    data = await _post(AGENT_URLS["decision"], payload)
    return {"decision": LoanDecisionResult(**data)}


async def compliance_node(state: LoanState) -> LoanState:
    log.info("[node:compliance] start")
    payload = {
        "application": state["application"].model_dump(mode="json"),
        "profile": state["profile"].model_dump(),
        "risk": state["risk"].model_dump(),
        "decision": state["decision"].model_dump(),
    }
    data = await _post(AGENT_URLS["compliance"], payload)
    return {"compliance": ComplianceActionResult(**data)}


def build_graph():
    graph = StateGraph(LoanState)
    graph.add_node("profile", profile_node)
    graph.add_node("risk", risk_node)
    graph.add_node("decision", decision_node)
    graph.add_node("compliance", compliance_node)

    graph.add_edge(START, "profile")
    graph.add_edge("profile", "risk")
    graph.add_edge("risk", "decision")
    graph.add_edge("decision", "compliance")
    graph.add_edge("compliance", END)

    return graph.compile()


async def run_workflow(application: LoanApplication) -> LoanState:
    app_graph = build_graph()
    final_state = await app_graph.ainvoke({"application": application})
    return final_state
