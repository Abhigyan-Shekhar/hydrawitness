#!/bin/sh
set -eu
# A fresh disposable graph per process start; no user or experiment data is durable.
workdir="$(mktemp -d /tmp/hydrawitness.XXXXXX)"
mkdir -p "$workdir/store" "$workdir/cache"
printf '%s\n' 'local-development-token-32-bytes' > "$workdir/token"
export CLOUD_PROVIDER=local LOCAL_PATH="$workdir/store"
export GRAPH_NAMESPACE=default GRAPH_ID=default GRAPH_CELL_ID=cell-0
export GRAPH_CELLS=cell-0 GRAPH_NODE_ID=node-0
export GRAPH_BOLT_NODE_ADDRESSES=node-0=127.0.0.1:7687 GRAPH_ADVERTISED_BOLT_ADDR=127.0.0.1:7687
export GRAPH_DATA_CACHE_DIR="$workdir/cache" GRAPH_AUTH_TOKEN_FILE="$workdir/token"
export GRAPH_ALLOW_PLAINTEXT=true GRAPH_USAGE_REPORT_ENABLED=false RUST_MIN_STACK=33554432
export HYDRA_URL=http://127.0.0.1:8443
/usr/local/bin/graph-node &
graph_pid=$!
trap 'kill "$graph_pid" 2>/dev/null || true' EXIT INT TERM
attempt=0
until /opt/venv/bin/python -c 'from hydrawitness.proof import query; query("MATCH (n:Claim) RETURN n.id LIMIT 1", {})' >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 90 ] || ! kill -0 "$graph_pid" 2>/dev/null; then
    echo 'HydraDB did not become ready' >&2
    exit 1
  fi
  sleep 1
done
/opt/venv/bin/python -m hydrawitness.launch
