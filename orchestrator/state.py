"""LangGraph state schema for the loan-approval workflow."""
from __future__ import annotations

from typing import Optional, TypedDict

from common.schemas import (
    ApplicantProfileResult,
    ComplianceActionResult,
    FinancialRiskResult,
    LoanApplication,
    LoanDecisionResult,
)


class LoanState(TypedDict, total=False):
    application: LoanApplication
    profile: Optional[ApplicantProfileResult]
    risk: Optional[FinancialRiskResult]
    decision: Optional[LoanDecisionResult]
    compliance: Optional[ComplianceActionResult]
    error: Optional[str]
