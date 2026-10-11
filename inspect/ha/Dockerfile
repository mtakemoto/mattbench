FROM ghcr.io/home-assistant/home-assistant@sha256:130241f28d01fa80dfa3b44f7d89781c188d8642ecab9024f079f19f9f82baa0

# Matches the requirement declared by the pinned Synthetic Home integration.
# Preinstall while building so sample containers can run on an internal network.
RUN python -m pip install --no-cache-dir synthetic-home==5.0.3
