"""ApplicantDB MCP server — exposes applicant lookups over MCP (streamable-http).

Tools:
  - get_applicant(applicant_id)        -> applicant profile dict (or null)
  - get_credit_history(applicant_id)   -> credit history dict (or null)
  - list_applicants()                  -> [applicant_id, ...] (for demo discovery)
"""
from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "applicants.json"

mcp = FastMCP("ApplicantDB", host="127.0.0.1", port=9001)


def _load() -> dict:
    with open(DATA_FILE) as fh:
        return json.load(fh)


@mcp.tool()
def get_applicant(applicant_id: str) -> dict | None:
    """Fetch the full applicant record by ID."""
    return _load().get(applicant_id)


@mcp.tool()
def get_credit_history(applicant_id: str) -> dict | None:
    """Fetch only the credit_history block for an applicant."""
    rec = _load().get(applicant_id)
    return rec["credit_history"] if rec else None


@mcp.tool()
def list_applicants() -> list[str]:
    """Return all known applicant IDs (for demo dropdowns)."""
    return sorted(_load().keys())


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
