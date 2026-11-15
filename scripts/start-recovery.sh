#!/bin/sh
# Start a separate disposable HydraDB node without modifying the original store.
set -eu
cd "$(dirname "$0")/.."
if docker container inspect hydrawitness-hydradb-recovery >/dev/null 2>&1; then
  docker start hydrawitness-hydradb-recovery >/dev/null
else
  docker image inspect ghcr.io/hydra-db/hydradb:latest >/dev/null 2>&1 || { echo 'HydraDB image is not cached; see official setup instructions.' >&2; exit 1; }
  mkdir -p .hydradb/recovery/store .hydradb/recovery/cache
  if [ ! -f .hydradb/auth-token ]; then
    printf '%s\n' 'local-development-token-32-bytes' > .hydradb/auth-token
  fi
  docker run -d --name hydrawitness-hydradb-recovery \
    -p 127.0.0.1:18444:8443 -p 127.0.0.1:19091:9090 \
    -v "$PWD/.hydradb:/data" -e CLOUD_PROVIDER=local -e LOCAL_PATH=/data/recovery/store \
    -e GRAPH_NAMESPACE=default -e GRAPH_ID=default -e GRAPH_CELL_ID=cell-0 \
    -e GRAPH_CELLS=cell-0 -e GRAPH_NODE_ID=node-0 \
    -e GRAPH_BOLT_NODE_ADDRESSES=node-0=127.0.0.1:7687 -e GRAPH_ADVERTISED_BOLT_ADDR=127.0.0.1:7687 \
    -e GRAPH_DATA_CACHE_DIR=/data/recovery/cache -e GRAPH_AUTH_TOKEN_FILE=/data/auth-token \
    -e GRAPH_ALLOW_PLAINTEXT=true -e GRAPH_USAGE_REPORT_ENABLED=false -e RUST_MIN_STACK=33554432 \
    ghcr.io/hydra-db/hydradb:latest >/dev/null
fi
printf '%s\n' 'Set HYDRA_URL=http://127.0.0.1:18444 and allow time for the node to become ready.'
