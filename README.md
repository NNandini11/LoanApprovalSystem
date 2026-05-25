# Agentic AI Intelligent Loan Approval System

Multi-agent loan approval pipeline built per the case study specification.

## Architecture

```
Streamlit UI (:8501)
    └── FastAPI gateway (:8000)
            └── LangGraph orchestrator
                    ├── Applicant Profile Agent  (:8001) ─► ApplicantDB MCP        (:9001)
                    ├── Financial Risk Agent     (:8002) ─► RiskRulesDB MCP        (:9002)
                    ├── Loan Decision Agent      (:8003) ─► DecisionSynthesis MCP  (:9003)
                    └── Compliance Action Agent  (:8004) ─► NotificationSystem MCP (:9004)

Loan Decision + Financial Risk agents call Anthropic Claude Sonnet 4.6
(with prompt-cached system prompts).
```

## Quick start

```bash
# 1. install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. configure
cp .env.example .env   # API key already set via env; .env optional

# 3. run
bash start_all.sh

# 4. open
xdg-open http://localhost:8501
```

`start_all.sh` launches 10 processes (4 MCP servers, 4 agents, gateway, UI),
each logging to `logs/<name>.log` with PIDs in `.pids/`.

```bash
bash stop_all.sh   # clean shutdown
tail -f logs/*.log # follow all logs during a demo
```

## Sample applicants (seeded in `data/applicants.json`)

| ID    | Profile                  | Expected outcome           |
| ----- | ------------------------ | -------------------------- |
| A001  | 780 score, low DTI       | Approved                   |
| A004  | 680 score, borderline DTI| Requires Manual Review     |
| A007  | 540 score, high DTI      | Rejected                   |

## Folder layout

```
common/         Pydantic schemas, Anthropic client w/ caching, shared logging
mcp_servers/    4 FastMCP servers (separate processes, streamable-http)
agents/         4 FastAPI agents (each owns one MCP server)
orchestrator/   LangGraph state machine
microservice/   FastAPI gateway
ui/             Streamlit chatbot
data/           seeded JSON DBs + decision/notification logs
```

## Demo walkthrough

1. Submit applicant `A001` in the UI → instant **Approved** with explanation.
2. Submit `A007` → **Rejected** with risk-factor list.
3. Submit `A004` → **Requires Manual Review** with confidence < 0.7.
4. Run `tail -f logs/loan_decision_agent.log` mid-demo to show the actual
   Claude call and the MCP `log_decision` tool invocation.
5. `cat data/decisions.log` / `data/notifications.log` to show audit trail.

## How explainability is achieved

* Every agent produces a typed, structured payload (Pydantic) which is merged
  into LangGraph state and surfaced in the UI.
* The decision agent's Claude call returns `key_decision_factors[]` and a
  prose `explanation`, both shown to the user.
* DecisionSynthesis MCP server appends every decision (with full state) to
  `data/decisions.log` for audit.
