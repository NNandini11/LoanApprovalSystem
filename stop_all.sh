#!/usr/bin/env bash
# Stop every process launched by start_all.sh.
set -uo pipefail

cd "$(dirname "$0")"

if [[ ! -d .pids ]]; then
  echo "No .pids directory — nothing to stop."
  exit 0
fi

stopped=0
for pidfile in .pids/*.pid; do
  [[ -e "$pidfile" ]] || continue
  name="$(basename "$pidfile" .pid)"
  pid="$(cat "$pidfile")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 0.2
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    echo "  [down] ${name} (pid ${pid})"
    stopped=$((stopped + 1))
  else
    echo "  [gone] ${name} (pid ${pid} not running)"
  fi
  rm -f "$pidfile"
done

echo "Stopped ${stopped} process(es)."
