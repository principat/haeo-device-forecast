#!/usr/bin/env bash
# Wird einmalig nach dem Erstellen des Devcontainers ausgeführt (postCreateCommand).
set -euo pipefail
cd "$(dirname "$0")/.."

pip install --upgrade pip
pip install -r requirements_test.txt
# Optional für die Browser-E2E-Tests (tests_e2e/):
#   pip install -r requirements_e2e.txt && python -m playwright install --with-deps chromium

# Claude Code CLI (nutzt die gemounteten Settings/Credentials aus ~/.claude)
npm install -g @anthropic-ai/claude-code

# Lokale Home-Assistant-Testinstanz vorbereiten: custom_components per Symlink einbinden
mkdir -p config/custom_components
ln -sfn "$(pwd)/custom_components/haeo_device_forecast" config/custom_components/haeo_device_forecast

echo "Setup abgeschlossen. Home Assistant starten mit: scripts/develop"
