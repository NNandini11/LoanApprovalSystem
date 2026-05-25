"""FastAPI gateway (:8000) — public entry point for the loan-approval system.

The Streamlit UI POSTs LoanApplication payloads here; the gateway invokes the
LangGraph orchestrator and returns a FinalDecision.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.logging_utils import get_logger
from common.schemas import FinalDecision, LoanApplication
from orchestrator.graph import run_workflow

log = get_logger("gateway")
app = FastAPI(title="Loan Approval Gateway")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "gateway"}


@app.post("/loan/apply", response_model=FinalDecision)
async def apply(application: LoanApplication) -> FinalDecision:
    log.info("received application: applicant=%s amount=%s",
             application.applicant_id, application.loan_amount)
    try:
        state = await run_workflow(application)
    except Exception as exc:  # noqa: BLE001
        log.exception("workflow failed")
        raise HTTPException(status_code=500, detail=f"Workflow failure: {exc}") from exc

    missing = [k for k in ("profile", "risk", "decision", "compliance") if not state.get(k)]
    if missing:
        log.error("workflow produced incomplete state, missing=%s", missing)
        raise HTTPException(status_code=500, detail=f"Workflow incomplete: missing {missing}")

    return FinalDecision(
        application=application,
        profile=state["profile"],
        risk=state["risk"],
        decision=state["decision"],
        compliance=state["compliance"],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
