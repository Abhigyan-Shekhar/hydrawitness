FROM ghcr.io/hydra-db/hydradb:0.4.0
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
COPY hydrawitness ./hydrawitness
COPY datasets ./datasets
COPY frontend ./frontend
COPY evals/results/iterations.csv ./evals/results/iterations.csv
COPY scripts/render-start.sh ./scripts/render-start.sh
USER 10001:10001
ENTRYPOINT ["/bin/sh", "/app/scripts/render-start.sh"]
