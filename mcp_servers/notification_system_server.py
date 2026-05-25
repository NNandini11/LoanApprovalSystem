"""NotificationSystem MCP server — emits user-facing notifications and mints case IDs."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "notifications.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("NotificationSystem", host="127.0.0.1", port=9004)


@mcp.tool()
def mint_case_id() -> str:
    """Return a fresh, unique case identifier."""
    return "CASE-" + uuid.uuid4().hex[:10].upper()


@mcp.tool()
def send_notification(recipient: str, subject: str, body: str, channel: str = "email") -> dict:
    """Send (mock) a notification and persist it to the audit log."""
    record = {
        "sent_at": datetime.utcnow().isoformat() + "Z",
        "channel": channel,
        "recipient": recipient,
        "subject": subject,
        "body": body,
    }
    with open(LOG_FILE, "a") as fh:
        fh.write(json.dumps(record) + "\n")
    return {"delivered": True, **record}


@mcp.tool()
def get_recent_notifications(n: int = 10) -> list[dict]:
    """Return the last N notifications dispatched."""
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE) as fh:
        lines = fh.readlines()
    return [json.loads(line) for line in lines[-n:]][::-1]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
