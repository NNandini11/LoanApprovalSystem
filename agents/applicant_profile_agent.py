"""Applicant Profile Agent (FastAPI :8001)

Responsibilities:
  * Pull applicant record + credit history from ApplicantDB MCP (:9001).
  * Compute income-stability score, employment risk, completeness flags.
  * Surface a human-readable credit history summary.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.logging_utils import get_logger
from common.mcp_client import call_tool
from common.schemas import ApplicantProfileResult, LoanApplication

APPLICANT_DB_PORT = 9001

log = get_logger("applicant_profile_agent")
app = FastAPI(title="Applicant Profile Agent")


def _employment_risk(employment_type: str, stable_months: int) -> str:
    if employment_type == "unemployed":
        return "high"
    if employment_type in {"contractor", "self_employed"} and stable_months < 24:
        return "high"
    if stable_months < 12:
        return "high"
    if stable_months < 36:
        return "medium"
    return "low"


def _income_stability_score(stable_months: int, variance_pct: float) -> float:
    # Higher tenure -> higher score; higher variance -> lower score. Bounded 0..1.
    tenure_component = min(stable_months / 60.0, 1.0)
    variance_component = max(0.0, 1.0 - (variance_pct / 50.0))
    return round(0.6 * tenure_component + 0.4 * variance_component, 3)


def _completeness_flags(applicant_record: dict | None, application: LoanApplication) -> list[str]:
    flags: list[str] = []
    if applicant_record is None:
        flags.append("applicant_record_not_found")
        return flags
    if not applicant_record.get("email"):
        flags.append("missing_email")
    if not applicant_record.get("phone"):
        flags.append("missing_phone")
    if application.existing_liabilities < 0:
        flags.append("invalid_existing_liabilities")
    return flags


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": "applicant_profile"}


@app.post("/analyze", response_model=ApplicantProfileResult)
async def analyze(application: LoanApplication) -> ApplicantProfileResult:
    log.info("analyze applicant_id=%s", application.applicant_id)
    record = await call_tool(APPLICANT_DB_PORT, "get_applicant", {"applicant_id": application.applicant_id})

    if record is None:
        log.warning("applicant %s not found in ApplicantDB", application.applicant_id)
        return ApplicantProfileResult(
            income_stability_score=0.0,
            employment_risk="high",
            credit_history_summary="Applicant record not found in ApplicantDB.",
            application_completeness_flags=["applicant_record_not_found"],
        )

    income_history = record.get("income_history", {})
    credit_history = record.get("credit_history", {})

    result = ApplicantProfileResult(
        income_stability_score=_income_stability_score(
            stable_months=income_history.get("stable_months", 0),
            variance_pct=income_history.get("salary_variance_pct", 100.0),
        ),
        employment_risk=_employment_risk(
            application.employment_type, income_history.get("stable_months", 0)
        ),
        credit_history_summary=credit_history.get("summary", "No credit history available."),
        application_completeness_flags=_completeness_flags(record, application),
    )
    log.info("profile result: %s", result.model_dump())
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
