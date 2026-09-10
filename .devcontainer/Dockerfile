FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

# Das Basis-Image bringt ein vorkonfiguriertes yarnpkg-APT-Repo mit, dessen
# GPG-Key nicht mehr auflösbar ist (NO_PUBKEY 62D54FD4003F6525). Das lässt
# `apt-get update` in den devcontainer-Features (z. B. common-utils) fehlschlagen.
# Wird hier nicht benötigt (npm reicht für die Claude-Code-CLI) -> entfernen.
RUN rm -f /etc/apt/sources.list.d/yarn.list /etc/apt/sources.list.d/yarn.list.save
