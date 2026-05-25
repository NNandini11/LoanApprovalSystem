"""DecisionSynthesis MCP server — persists and retrieves decision records.

Each decision is appended as a JSON line to data/decisions.log so the
demo can show a tamper-evident audit trail.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "decisions.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("DecisionSynthesis", host="127.0.0.1", port=9003)


@mcp.tool()
def log_decision(decision: dict) -> dict:
    """Append a decision record (JSON line) and return the stored envelope."""
    envelope = {"logged_at": datetime.utcnow().isoformat() + "Z", "decision": decision}
    with open(LOG_FILE, "a") as fh:
        fh.write(json.dumps(envelope) + "\n")
    return envelope


@mcp.tool()
def get_recent_decisions(n: int = 10) -> list[dict]:
    """Return the last N decisions logged (most recent first)."""
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE) as fh:
        lines = fh.readlines()
    return [json.loads(line) for line in lines[-n:]][::-1]


@mcp.tool()
def get_decision_template() -> dict:
    """Return the canonical decision JSON shape for prompt grounding."""
    return {
        "classification": "Approved | Rejected | Requires Manual Review",
        "risk_score": "integer 0..100",
        "confidence_level": "float 0.0..1.0",
        "key_decision_factors": ["string", "..."],
        "explanation": "concise rationale",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
