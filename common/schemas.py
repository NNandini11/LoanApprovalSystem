"""Pydantic models shared across the gateway, orchestrator, and agents."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


EmploymentType = Literal["salaried", "self_employed", "contractor", "unemployed", "retired"]
Classification = Literal["Approved", "Rejected", "Requires Manual Review"]
RiskLevel = Literal["low", "medium", "high"]


class LoanApplication(BaseModel):
    applicant_id: str
    age: int = Field(ge=18, le=100)
    annual_income: float = Field(gt=0)
    employment_type: EmploymentType
    credit_score: int = Field(ge=300, le=850)
    loan_amount: float = Field(gt=0)
    loan_tenure_months: int = Field(ge=6, le=480)
    existing_liabilities: float = Field(ge=0)
    location: str
    application_timestamp: datetime = Field(default_factory=_utcnow)


class ApplicantProfileResult(BaseModel):
    income_stability_score: float
    employment_risk: RiskLevel
    credit_history_summary: str
    application_completeness_flags: list[str]


class FinancialRiskResult(BaseModel):
    debt_to_income_ratio: float
    credit_score_risk_level: RiskLevel
    loan_amount_risk: RiskLevel
    anomaly_detection: list[str]
    reasoning: str


class LoanDecisionResult(BaseModel):
    classification: Classification
    risk_score: int = Field(ge=0, le=100)
    confidence_level: float = Field(ge=0.0, le=1.0)
    key_decision_factors: list[str]
    explanation: str


class ComplianceActionResult(BaseModel):
    action_taken: str
    notification_sent: bool
    case_id: str
    timestamp: datetime
    summary: str


class FinalDecision(BaseModel):
    application: LoanApplication
    profile: ApplicantProfileResult
    risk: FinancialRiskResult
    decision: LoanDecisionResult
    compliance: ComplianceActionResult
