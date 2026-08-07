#!/usr/bin/env bash
# Beispiel-Aufruf des AI-Act-Kennzeichnungs-Tools.
# Vor der Nutzung: requirements.txt installieren und externe Tools
# (exiftool, ffmpeg, c2patool, tesseract, openssl) bereitstellen — siehe README.md.

set -euo pipefail

# Ins Projekt-Wurzelverzeichnis wechseln (eine Ebene über examples/),
# damit der Modulaufruf unabhängig vom Ausführungsort funktioniert.
cd "$(dirname "$0")/.."

python3 -m ai_act_labeler.cli \
    --input "./incoming" \
    --output "./processed" \
    --badge-position "bottom-right"
