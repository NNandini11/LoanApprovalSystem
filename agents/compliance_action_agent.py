"""Compliance & Action Orchestrator Agent (FastAPI :8004)

Mints a case ID, dispatches the appropriate notification via NotificationSystem
MCP, and returns the compliance/action summary.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.logging_utils import get_logger
from common.mcp_client import call_tool
from common.schemas import (
    ApplicantProfileResult,
    ComplianceActionResult,
    FinancialRiskResult,
    LoanApplication,
    LoanDecisionResult,
)

NOTIFICATION_PORT = 9004

log = get_logger("compliance_action_agent")
app = FastAPI(title="Compliance & Action Orchestrator Agent")


class ComplianceInput(BaseModel):
    application: LoanApplication
    profile: ApplicantProfileResult
    risk: FinancialRiskResult
    decision: LoanDecisionResult
    recipient_email: str | None = None


SUBJECT_BY_CLASS = {
    "Approved": "Your loan application has been approved",
    "Rejected": "Update on your loan application",
    "Requires Manual Review": "Your loan application is under manual review",
}


def _build_body(decision: LoanDecisionResult, application: LoanApplication, case_id: str) -> str:
    bullets = "\n".join(f"  - {f}" for f in decision.key_decision_factors)
    return (
        f"Case ID: {case_id}\n"
        f"Applicant: {application.applicant_id}\n"
        f"Loan amount: {application.loan_amount}\n"
        f"Decision: {decision.classification}\n"
        f"Risk score: {decision.risk_score}\n"
        f"Confidence: {decision.confidence_level}\n\n"
        f"Key factors:\n{bullets}\n\n"
        f"Explanation:\n{decision.explanation}\n"
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": "compliance_action"}


@app.post("/analyze", response_model=ComplianceActionResult)
async def analyze(payload: ComplianceInput) -> ComplianceActionResult:
    case_id = await call_tool(NOTIFICATION_PORT, "mint_case_id")
    if not isinstance(case_id, str):
        case_id = f"CASE-{payload.application.applicant_id}"

    recipient = payload.recipient_email or f"{payload.application.applicant_id.lower()}@example.com"
    subject = SUBJECT_BY_CLASS.get(payload.decision.classification, "Loan application update")
    body = _build_body(payload.decision, payload.application, case_id)

    notification_sent = False
    try:
        notif = await call_tool(
            NOTIFICATION_PORT,
            "send_notification",
            {"recipient": recipient, "subject": subject, "body": body, "channel": "email"},
        )
        notification_sent = bool(notif and notif.get("delivered"))
    except Exception as exc:  # noqa: BLE001 — best-effort
        log.warning("notification dispatch failed: %s", exc)

    action_taken = {
        "Approved": "Approval recorded; disbursement workflow queued.",
        "Rejected": "Application closed with rejection notice issued.",
        "Requires Manual Review": "Routed to underwriter queue for manual review.",
    }[payload.decision.classification]

    result = ComplianceActionResult(
        action_taken=action_taken,
        notification_sent=notification_sent,
        case_id=case_id,
        timestamp=datetime.now(timezone.utc),
        summary=(
            f"Case {case_id}: {payload.decision.classification} for applicant "
            f"{payload.application.applicant_id}. Notification {'sent' if notification_sent else 'NOT sent'} "
            f"to {recipient}."
        ),
    )
    log.info("compliance result: %s", result.model_dump(mode="json"))
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8004)
