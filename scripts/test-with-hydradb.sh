#!/bin/sh
# Run integration tests against a fresh graph that is removed on exit.
set -eu
cd "$(dirname "$0")/.."

python=${PYTHON:-python3}
container_id=
cleanup() {
  status=$?
  trap - 0 INT TERM HUP
  if [ -n "$container_id" ]; then
    if [ "$status" -ne 0 ]; then
      printf '%s\n' 'HydraDB container logs:' >&2
      docker logs "$container_id" >&2 2>&1 || true
    fi
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

HYDRA_TOKEN=hydrawitness-integration-token-32-bytes
export HYDRA_TOKEN
container_id=$(docker run --rm -d -p 127.0.0.1::8443 \
  -e HYDRA_TOKEN --entrypoint /bin/sh ghcr.io/hydra-db/hydradb:0.4.0 -c '
    set -eu
    workdir=$(mktemp -d /tmp/hydrawitness.XXXXXX)
    mkdir -p "$workdir/store" "$workdir/cache"
    printf "%s\n" "$HYDRA_TOKEN" > "$workdir/token"
    export CLOUD_PROVIDER=local LOCAL_PATH="$workdir/store"
    export GRAPH_NAMESPACE=default GRAPH_ID=default GRAPH_CELL_ID=cell-0
    export GRAPH_CELLS=cell-0 GRAPH_NODE_ID=node-0
    export GRAPH_BOLT_NODE_ADDRESSES=node-0=127.0.0.1:7687 GRAPH_ADVERTISED_BOLT_ADDR=127.0.0.1:7687
    export GRAPH_DATA_CACHE_DIR="$workdir/cache" GRAPH_AUTH_TOKEN_FILE="$workdir/token"
    export GRAPH_ALLOW_PLAINTEXT=true GRAPH_USAGE_REPORT_ENABLED=false RUST_MIN_STACK=33554432
    exec /usr/local/bin/graph-node
  ')
binding=$(docker port "$container_id" 8443/tcp)
case "$binding" in
  127.0.0.1:*) port=${binding#127.0.0.1:} ;;
  *) printf '%s\n' 'Unexpected Docker port binding' >&2; exit 1 ;;
esac
case "$port" in
  ''|*[!0-9]*) printf '%s\n' 'Invalid Docker port' >&2; exit 1 ;;
esac
HYDRA_URL="http://127.0.0.1:$port"
export HYDRA_URL

attempt=0
until "$python" -c 'from hydrawitness.proof import query; query("MATCH (n:Claim) RETURN n.id LIMIT 1", {})' >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ] || [ "$(docker inspect -f '{{.State.Running}}' "$container_id" 2>/dev/null || true)" != true ]; then
    printf '%s\n' 'Disposable HydraDB did not become ready' >&2
    exit 1
  fi
  sleep 1
done
"$python" -m tests.suites integration
