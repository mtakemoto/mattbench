FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 agent \
    && mkdir /workspace \
    && chown agent:agent /workspace

USER agent
WORKDIR /workspace
