"""RiskRulesDB MCP server — exposes risk thresholds and rules."""
from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "risk_rules.json"

mcp = FastMCP("RiskRulesDB", host="127.0.0.1", port=9002)


def _load() -> dict:
    with open(DATA_FILE) as fh:
        return json.load(fh)


@mcp.tool()
def get_dti_thresholds() -> dict:
    """Return DTI risk thresholds."""
    return _load()["dti_thresholds"]


@mcp.tool()
def get_credit_score_bands() -> list[dict]:
    """Return credit-score → risk-level bands."""
    return _load()["credit_score_bands"]


@mcp.tool()
def get_loan_amount_rules() -> dict:
    """Return loan-amount vs income rules."""
    return _load()["loan_amount_rules"]


@mcp.tool()
def get_anomaly_rules() -> list[dict]:
    """Return the anomaly-detection rule catalogue."""
    return _load()["anomaly_rules"]


@mcp.tool()
def get_decision_policy() -> dict:
    """Return the auto-approve / auto-reject policy thresholds."""
    return _load()["decision_policy"]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
