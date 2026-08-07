#!/usr/bin/env bash
# Einfacher Ordner-Watcher für den AI Act Workflow.
# Dateien, die in ./incoming/ gelegt werden, werden automatisch verarbeitet.
#
# Nutzung:
#   chmod +x examples/watch_incoming.sh
#   ./examples/watch_incoming.sh
#
# Das Skript läuft im Hintergrund weiter und prüft den Ordner alle 60 Sekunden.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$PROJECT_ROOT/processed/watch_incoming.log"
INTERVAL_SECONDS=60

cd "$PROJECT_ROOT"

echo "[$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).astimezone().isoformat())
PY
)] Watcher gestartet" >> "$LOG_FILE"

if [[ -d "$PROJECT_ROOT/venv" ]]; then
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/venv/bin/activate"
else
  echo "[$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).astimezone().isoformat())
PY
)] WARNUNG: virtuelle Umgebung nicht gefunden, verwende System-Python" >> "$LOG_FILE"
fi

while true; do
  shopt -s nullglob
  files=(incoming/*)
  shopt -u nullglob

  if (( ${#files[@]} > 0 )); then
    echo "[$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).astimezone().isoformat())
PY
)] Neue Dateien gefunden: ${#files[@]} -> Verarbeite Batch" >> "$LOG_FILE"
    if python -m ai_act_labeler.cli --input "./incoming" --output "./processed" >> "$LOG_FILE" 2>&1; then
      echo "[$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).astimezone().isoformat())
PY
)] Batch-Verarbeitung erfolgreich" >> "$LOG_FILE"
    else
      echo "[$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).astimezone().isoformat())
PY
)] FEHLER bei der Batch-Verarbeitung" >> "$LOG_FILE"
    fi
  fi

  sleep "$INTERVAL_SECONDS"
done
