FROM node:22.22.2-bookworm-slim@sha256:9f6d5975c7dca860947d3915877f85607946403fc55349f39b4bc3688448bb6e

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 bash ca-certificates git ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent@1.1.0

RUN useradd --create-home --uid 10001 agent \
    && mkdir -p /workspace /home/agent/.pi/agent \
    && chown -R agent:agent /workspace /home/agent

USER agent
WORKDIR /workspace
