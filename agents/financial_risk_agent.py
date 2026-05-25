"""Financial Risk Analysis Agent (FastAPI :8002)

Pulls thresholds from RiskRulesDB MCP (:9002), computes deterministic risk
metrics, then asks Claude for a short reasoning paragraph.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.llm import call_claude
from common.logging_utils import get_logger
from common.mcp_client import call_tool
from common.schemas import ApplicantProfileResult, FinancialRiskResult, LoanApplication

RISK_RULES_DB_PORT = 9002

log = get_logger("financial_risk_agent")
app = FastAPI(title="Financial Risk Analysis Agent")


class RiskInput(BaseModel):
    application: LoanApplication
    profile: ApplicantProfileResult


SYSTEM_PROMPT = (
    "You are the Financial Risk Reasoning component of a loan approval system. "
    "You are given a deterministic risk snapshot (DTI ratio, credit-score band, "
    "loan-amount risk, anomaly flags) plus the applicant profile. "
    "Return a SHORT (2-3 sentence) plain-English paragraph that explains the "
    "overall financial risk picture for a human reviewer. "
    "Do NOT include disclaimers, markdown, or bullet points. Just the paragraph."
)


def _credit_score_risk_level(score: int, bands: list[dict]) -> str:
    for band in bands:
        if band["min"] <= score <= band["max"]:
            return band["risk_level"]
    return "high"


def _loan_amount_risk(loan_amount: float, annual_income: float, rules: dict) -> str:
    if annual_income <= 0:
        return "high"
    multiplier = loan_amount / annual_income
    if multiplier <= rules["low_multiplier_of_income_max"]:
        return "low"
    if multiplier <= rules["medium_multiplier_of_income_max"]:
        return "medium"
    return "high"


def _monthly_new_payment(loan_amount: float, tenure_months: int) -> float:
    # Simple straight-line approximation (no interest) — fine for risk DTI estimate.
    return loan_amount / max(tenure_months, 1)


def _detect_anomalies(application: LoanApplication, profile: ApplicantProfileResult,
                     anomaly_rules: list[dict]) -> list[str]:
    triggered: list[str] = []
    if application.employment_type == "unemployed":
        triggered.append("UNEMPLOYED_APPLICANT")
    if application.loan_amount > application.annual_income * 10:
        triggered.append("LOAN_VS_INCOME_EXTREME")
    if application.age > 60 and application.loan_tenure_months > 120:
        triggered.append("AGE_RETIRED_LONG_TENURE")
    # Income variance signal arrives via profile.income_stability_score (lower => more variance).
    if profile.income_stability_score < 0.4:
        triggered.append("INCOME_VARIANCE_HIGH")
    return triggered


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": "financial_risk"}


@app.post("/analyze", response_model=FinancialRiskResult)
async def analyze(payload: RiskInput) -> FinancialRiskResult:
    application = payload.application
    profile = payload.profile

    dti_thresholds = await call_tool(RISK_RULES_DB_PORT, "get_dti_thresholds")
    bands = await call_tool(RISK_RULES_DB_PORT, "get_credit_score_bands")
    loan_rules = await call_tool(RISK_RULES_DB_PORT, "get_loan_amount_rules")
    anomaly_rules = await call_tool(RISK_RULES_DB_PORT, "get_anomaly_rules")

    monthly_new = _monthly_new_payment(application.loan_amount, application.loan_tenure_months)
    annualized_new = monthly_new * 12
    dti = round(
        (application.existing_liabilities + annualized_new) / max(application.annual_income, 1.0),
        3,
    )

    credit_risk = _credit_score_risk_level(application.credit_score, bands)
    loan_risk = _loan_amount_risk(application.loan_amount, application.annual_income, loan_rules)
    anomalies = _detect_anomalies(application, profile, anomaly_rules)

    user_message = (
        "Risk snapshot:\n"
        f"- DTI ratio: {dti} (thresholds: {dti_thresholds})\n"
        f"- Credit score: {application.credit_score} -> {credit_risk} risk band\n"
        f"- Loan amount: {application.loan_amount} on income {application.annual_income}"
        f" -> {loan_risk} risk\n"
        f"- Anomaly flags: {anomalies or 'none'}\n"
        f"- Profile: income_stability={profile.income_stability_score}, "
        f"employment_risk={profile.employment_risk}, credit_history={profile.credit_history_summary}\n"
    )

    log.info("risk inputs: %s", user_message.replace("\n", " | "))
    reasoning = call_claude(SYSTEM_PROMPT, user_message, max_tokens=400, temperature=0.3).strip()

    result = FinancialRiskResult(
        debt_to_income_ratio=dti,
        credit_score_risk_level=credit_risk,
        loan_amount_risk=loan_risk,
        anomaly_detection=anomalies,
        reasoning=reasoning,
    )
    log.info("risk result: %s", result.model_dump())
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8002)
