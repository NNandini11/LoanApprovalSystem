"""Loan Decision Agent (FastAPI :8003)

Synthesises profile + risk outputs into a final decision via Claude
(Sonnet 4.6, cached rubric), then writes the decision to DecisionSynthesis MCP.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.llm import call_claude, extract_json
from common.logging_utils import get_logger
from common.mcp_client import call_tool
from common.schemas import (
    ApplicantProfileResult,
    FinancialRiskResult,
    LoanApplication,
    LoanDecisionResult,
)

DECISION_SYNTHESIS_PORT = 9003

log = get_logger("loan_decision_agent")
app = FastAPI(title="Loan Decision Agent")


class DecisionInput(BaseModel):
    application: LoanApplication
    profile: ApplicantProfileResult
    risk: FinancialRiskResult


SYSTEM_PROMPT = """You are the Loan Decision Agent in a multi-agent loan approval system.
You receive a structured snapshot of a loan application and two upstream analyses:
the Applicant Profile (income stability, employment risk, credit history) and the
Financial Risk Analysis (DTI ratio, credit-score risk level, loan-amount risk,
anomaly flags, and short reasoning).

Your job: classify the application and explain the decision.

Decision rubric (apply in order):
1. APPROVE when ALL of the following hold:
   - credit_score >= 720
   - debt_to_income_ratio <= 0.35
   - no anomaly flags
   - employment_risk is "low"
2. REJECT when ANY of the following holds:
   - credit_score < 580
   - debt_to_income_ratio > 0.65
   - "LOAN_VS_INCOME_EXTREME" in anomalies
   - employment_risk is "high" AND credit_score < 650
3. Otherwise classify as "Requires Manual Review".

Scoring guidance:
- risk_score: integer 0..100 where 0 is safest and 100 is riskiest. Weight credit
  score (40%), DTI (30%), anomalies (20%), employment/income stability (10%).
- confidence_level: float 0.0..1.0. Use < 0.7 for any "Requires Manual Review"
  decision; use >= 0.85 for clear approvals/rejections.
- key_decision_factors: 2-5 short bullet-style strings.
- explanation: 2-4 sentences in plain English for a human reviewer.

RESPOND ONLY with a JSON object of this exact shape (no markdown, no preface):
{
  "classification": "Approved" | "Rejected" | "Requires Manual Review",
  "risk_score": <int 0-100>,
  "confidence_level": <float 0.0-1.0>,
  "key_decision_factors": ["...", "..."],
  "explanation": "..."
}
"""


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": "loan_decision"}


@app.post("/analyze", response_model=LoanDecisionResult)
async def analyze(payload: DecisionInput) -> LoanDecisionResult:
    user_message = json.dumps(
        {
            "application": payload.application.model_dump(mode="json"),
            "profile": payload.profile.model_dump(),
            "risk": payload.risk.model_dump(),
        },
        indent=2,
        default=str,
    )

    log.info("calling Claude for decision on applicant=%s", payload.application.applicant_id)
    raw = call_claude(SYSTEM_PROMPT, user_message, max_tokens=1500, temperature=0.1)
    log.info("raw LLM output (%d chars): %s", len(raw), raw.replace("\n", " "))

    try:
        decision_dict = extract_json(raw)
        decision = LoanDecisionResult(**decision_dict)
    except (ValidationError, ValueError) as exc:
        log.error("decision parse failed (%s); falling back to manual review", exc)
        decision = LoanDecisionResult(
            classification="Requires Manual Review",
            risk_score=70,
            confidence_level=0.3,
            key_decision_factors=["LLM output could not be parsed reliably"],
            explanation=(
                "The decision agent could not parse the LLM response into the required schema. "
                "Routing to manual review as a safety fallback."
            ),
        )

    # Audit trail — write the decision to the DecisionSynthesis MCP server.
    audit_envelope = {
        "applicant_id": payload.application.applicant_id,
        "loan_amount": payload.application.loan_amount,
        "decision": decision.model_dump(),
    }
    try:
        await call_tool(DECISION_SYNTHESIS_PORT, "log_decision", {"decision": audit_envelope})
    except Exception as exc:  # noqa: BLE001 — best-effort audit
        log.warning("failed to log decision to MCP: %s", exc)

    log.info("decision: %s (score=%s, conf=%s)",
             decision.classification, decision.risk_score, decision.confidence_level)
    return decision


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8003)
