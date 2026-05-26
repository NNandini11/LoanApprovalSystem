# Loan Approval System — Project Guide

Multi-agent Agentic AI loan-approval pipeline. Built per the "Agentic AI Intelligent
Loan Approval System" case study. Classifies a loan application as
**Approved / Rejected / Requires Manual Review** with an explainable, audited trail.

## Architecture (10 processes)

```
Streamlit UI :8501
    └── FastAPI gateway :8000
            └── LangGraph orchestrator (in-process)
                    ├── Applicant Profile  agent :8001 ─► ApplicantDB        MCP :9001
                    ├── Financial Risk     agent :8002 ─► RiskRulesDB        MCP :9002
                    ├── Loan Decision      agent :8003 ─► DecisionSynthesis  MCP :9003
                    └── Compliance Action  agent :8004 ─► NotificationSystem MCP :9004
                                                                │
                                                                ▼
                                                Anthropic Claude Sonnet 4.6
                                                (cached system prompts)
```

Linear LangGraph flow: `profile → risk → decision → compliance`.

## Folder map

| Path | Role |
| --- | --- |
| `common/` | Pydantic schemas (`schemas.py`), Anthropic client + JSON extractor (`llm.py`), MCP client helper (`mcp_client.py`), logging |
| `mcp_servers/` | 4 standalone FastMCP servers (streamable-http, ports 9001–9004) |
| `agents/` | 4 FastAPI agent services, each owning one MCP server |
| `orchestrator/` | LangGraph `StateGraph` wiring (`graph.py`) + `LoanState` TypedDict |
| `microservice/` | FastAPI gateway (`main.py`) — single public entry point at `POST /loan/apply` |
| `ui/` | Streamlit chatbot (`streamlit_app.py`) |
| `data/` | Mock JSON DBs (`applicants.json`, `risk_rules.json`) + append-only audit logs (`decisions.log`, `notifications.log`) |
| `tests/` | pytest suite — unit tests for pure functions + integration tests against the live gateway |

## Run / stop / verify

```bash
# install (once)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# bring everything up — 10 processes, PIDs in .pids/, logs in logs/
bash start_all.sh

# health-check everything
for p in 8000 8001 8002 8003 8004; do curl -s http://127.0.0.1:$p/health; done

# stop everything
bash stop_all.sh
```

UI is at <http://localhost:8501>, gateway docs at <http://localhost:8000/docs>.

## Tests

```bash
.venv/bin/python -m pytest tests/ -v    # 66 tests, ~37s when the stack is up
```

Integration tests in `tests/test_integration_gateway.py` auto-skip when the
gateway isn't reachable, so the unit suite works without the stack running.

## How decisions are made

Two layers:

1. **Deterministic risk math** in `agents/financial_risk_agent.py` and
   thresholds in `data/risk_rules.json` — DTI, credit-score bands, loan/income
   ratio, anomaly flags.
2. **LLM rubric** in `agents/loan_decision_agent.py:SYSTEM_PROMPT` — Claude
   classifies based on the rubric:
   - **Approved** when credit ≥ 720, DTI ≤ 0.35, no anomalies, low employment risk
   - **Rejected** when any: credit < 580, DTI > 0.65, `LOAN_VS_INCOME_EXTREME`,
     or (high employment risk + credit < 650)
   - **Requires Manual Review** otherwise

Live tuning: edit `data/risk_rules.json` or the system prompt, restart the
one affected process, redo a submission.

## Sample applicants (in `data/applicants.json`)

| ID | Profile | Demo outcome |
| --- | --- | --- |
| A001 | Strong file (credit 780, low DTI, stable salaried) | Approved |
| A007 | Distressed (credit 540, contractor, 10× loan/income) | Rejected |
| A010 + tweaks | Gray zone (credit 700, DTI ~0.35) | Requires Manual Review |

## Why "Agentic"

- Each of 4 agents has **one responsibility** and **one MCP data source**
- Agents communicate via **typed Pydantic payloads** and **MCP tool calls**, no shared globals
- The orchestrator **routes context**, it doesn't decide
- The decision agent uses an **LLM with a cached rubric**, not hard-coded if/else
- Outputs include `key_decision_factors[]` + `explanation` for **explainability**
- Audit trail in `data/decisions.log` + `data/notifications.log`

## Conventions / gotchas

- Every service writes its PID to `.pids/<name>.pid` and logs to `logs/<name>.log`.
  Editing one service? Restart just it: `kill $(cat .pids/<name>.pid) && nohup .venv/bin/python <path> > logs/<name>.log 2>&1 &`
- `mcp_servers/` use **FastMCP streamable-http** transport — agents connect via
  `common.mcp_client.call_tool(port, name, args)`.
- The decision agent's LLM output is parsed with a brace-balanced JSON extractor
  (`common/llm.py:extract_json`) to survive trailing prose and code fences.
- Prompt caching is wired into `common/llm.py` — the system prompt is sent with
  `cache_control: ephemeral` so multiple applications within 5 min reuse it.
- Timestamps are timezone-aware (`datetime.now(timezone.utc)`); don't reintroduce `utcnow()`.

## Common changes

| Task | Where |
| --- | --- |
| Add a new applicant | `data/applicants.json` |
| Tune risk thresholds | `data/risk_rules.json` |
| Change decision rubric | `SYSTEM_PROMPT` in `agents/loan_decision_agent.py` |
| Add a new agent step | New node in `orchestrator/graph.py` + new FastAPI service in `agents/` + new launcher line in `start_all.sh` |
| Add a UI field | Edit form in `ui/streamlit_app.py` + add field to `LoanApplication` in `common/schemas.py` |
