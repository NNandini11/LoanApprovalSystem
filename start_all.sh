#!/usr/bin/env bash
# Launch every process in the loan-approval system.
# PIDs are written to .pids/<name>.pid; logs go to logs/<name>.log.
set -euo pipefail

cd "$(dirname "$0")"

VENV_PY="${PWD}/.venv/bin/python"
VENV_ST="${PWD}/.venv/bin/streamlit"

if [[ ! -x "$VENV_PY" ]]; then
  echo "venv not found at .venv — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

mkdir -p logs .pids

start() {
  local name="$1"; shift
  local logfile="logs/${name}.log"
  local pidfile=".pids/${name}.pid"

  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "  [skip] ${name} already running (pid $(cat "$pidfile"))"
    return
  fi

  nohup "$@" >"$logfile" 2>&1 &
  echo $! > "$pidfile"
  echo "  [up]  ${name} (pid $!) -> $logfile"
}

echo "==> Starting MCP servers"
start applicant_db_mcp        "$VENV_PY" mcp_servers/applicant_db_server.py
start risk_rules_db_mcp       "$VENV_PY" mcp_servers/risk_rules_db_server.py
start decision_synthesis_mcp  "$VENV_PY" mcp_servers/decision_synthesis_server.py
start notification_system_mcp "$VENV_PY" mcp_servers/notification_system_server.py

sleep 2  # let MCP servers bind their ports before agents try to talk to them

echo "==> Starting agents"
start applicant_profile_agent "$VENV_PY" agents/applicant_profile_agent.py
start financial_risk_agent    "$VENV_PY" agents/financial_risk_agent.py
start loan_decision_agent     "$VENV_PY" agents/loan_decision_agent.py
start compliance_action_agent "$VENV_PY" agents/compliance_action_agent.py

sleep 1

echo "==> Starting gateway"
start gateway "$VENV_PY" microservice/main.py

sleep 1

echo "==> Starting Streamlit UI"
start streamlit_ui "$VENV_ST" run ui/streamlit_app.py --server.port 8501 --server.headless true

echo
echo "All services launched."
echo "  UI:       http://localhost:8501"
echo "  Gateway:  http://localhost:8000/docs"
echo "  Logs:     tail -f logs/*.log"
echo "  Stop:     bash stop_all.sh"
