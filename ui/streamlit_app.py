"""Streamlit chatbot UI for the loan-approval system."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx
import streamlit as st

GATEWAY_URL = os.environ.get("LOAN_GATEWAY_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Agentic Loan Approval", page_icon="🏦", layout="wide")
st.title("🏦 Agentic AI Loan Approval System")
st.caption(
    "Multi-agent workflow: Applicant Profile → Financial Risk → Loan Decision → Compliance."
)

with st.sidebar:
    st.header("Demo applicants")
    st.markdown(
        "- **A001** — strong file, expected **Approved**\n"
        "- **A004** — borderline, expected **Manual Review**\n"
        "- **A007** — distressed, expected **Rejected**\n"
    )
    st.divider()
    st.caption(f"Gateway: `{GATEWAY_URL}`")


with st.form("loan_application", clear_on_submit=False):
    col_a, col_b = st.columns(2)
    with col_a:
        applicant_id = st.text_input("Applicant ID", value="A001")
        age = st.number_input("Age", min_value=18, max_value=100, value=34)
        annual_income = st.number_input("Annual income", min_value=1.0, value=120_000.0, step=1_000.0)
        employment_type = st.selectbox(
            "Employment type",
            ["salaried", "self_employed", "contractor", "unemployed", "retired"],
            index=0,
        )
        credit_score = st.slider("Credit score", min_value=300, max_value=850, value=780)
    with col_b:
        loan_amount = st.number_input("Loan amount", min_value=1.0, value=250_000.0, step=1_000.0)
        loan_tenure_months = st.number_input(
            "Loan tenure (months)", min_value=6, max_value=480, value=120
        )
        existing_liabilities = st.number_input(
            "Existing liabilities (annual)", min_value=0.0, value=10_000.0, step=500.0
        )
        location = st.text_input("Location", value="Mumbai, IN")

    submitted = st.form_submit_button("Submit application", use_container_width=True, type="primary")


def _badge(label: str) -> str:
    colors = {
        "Approved": "#1f883d",
        "Rejected": "#cf222e",
        "Requires Manual Review": "#bf8700",
    }
    color = colors.get(label, "#6e7781")
    return (
        f"<span style='background:{color};color:white;padding:4px 10px;"
        f"border-radius:6px;font-weight:600'>{label}</span>"
    )


if submitted:
    payload = {
        "applicant_id": applicant_id,
        "age": int(age),
        "annual_income": float(annual_income),
        "employment_type": employment_type,
        "credit_score": int(credit_score),
        "loan_amount": float(loan_amount),
        "loan_tenure_months": int(loan_tenure_months),
        "existing_liabilities": float(existing_liabilities),
        "location": location,
        "application_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with st.spinner("Agents are evaluating your application…"):
        try:
            response = httpx.post(f"{GATEWAY_URL}/loan/apply", json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPStatusError as exc:
            st.error(f"Gateway returned {exc.response.status_code}: {exc.response.text}")
            st.stop()
        except httpx.HTTPError as exc:
            st.error(f"Could not reach gateway at {GATEWAY_URL}: {exc}")
            st.stop()

    decision = result["decision"]
    compliance = result["compliance"]
    profile = result["profile"]
    risk = result["risk"]

    st.markdown("## Decision")
    st.markdown(_badge(decision["classification"]), unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Risk score", decision["risk_score"])
    c2.metric("Confidence", f"{decision['confidence_level']:.2f}")
    c3.metric("Case ID", compliance["case_id"])

    st.markdown("### Why this decision")
    st.write(decision["explanation"])
    st.markdown("**Key factors:**")
    for f in decision["key_decision_factors"]:
        st.markdown(f"- {f}")

    st.divider()
    st.markdown("## Agent outputs (audit trail)")

    with st.expander("1. Applicant Profile Agent", expanded=False):
        st.json(profile)
    with st.expander("2. Financial Risk Analysis Agent", expanded=False):
        st.json(risk)
    with st.expander("3. Loan Decision Agent", expanded=False):
        st.json(decision)
    with st.expander("4. Compliance & Action Agent", expanded=True):
        st.json(compliance)
