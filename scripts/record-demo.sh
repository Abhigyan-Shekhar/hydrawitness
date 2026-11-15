#!/bin/sh
# Records a new synthetic dashboard investigation and saved Codex CLI replays.
set -eu
cd "$(dirname "$0")/.."
: "${HYDRA_URL:=http://127.0.0.1:18444}"
export HYDRA_URL
record_log=$(mktemp -t hydrawitness-recording)
HYDRAWITNESS_PORT=8766 .venv/bin/python -m hydrawitness.launch > "$record_log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT INT TERM
attempt=0
until curl -fsS http://127.0.0.1:8766/api/state >/dev/null; do
  attempt=$((attempt+1)); [ "$attempt" -lt 30 ] || { cat "$record_log" >&2; exit 1; }
  kill -0 "$server_pid" 2>/dev/null || { cat "$record_log" >&2; exit 1; }
  sleep 1
done
HYDRAWITNESS_DEMO_URL=http://127.0.0.1:8766/ .venv/bin/python demo/record_submission.py
