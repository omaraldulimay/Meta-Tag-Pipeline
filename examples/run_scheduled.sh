#!/usr/bin/env bash
# Automatisches Batch-Processing für den AI Act Workflow.
# Dieses Skript verarbeitet alle Dateien aus ./incoming und schreibt die
# Ergebnisse nach ./processed.
#
# Nutzung:
#   chmod +x examples/run_scheduled.sh
#   ./examples/run_scheduled.sh
#
# Für automatische Ausführung z.B. mit cron oder launchd verwenden.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$PROJECT_ROOT/processed/scheduled_run.log"

cd "$PROJECT_ROOT"

echo "[$(date --iso-8601=seconds)] Starte AI Act Batch-Verarbeitung" >> "$LOG_FILE"

if [[ -d "$PROJECT_ROOT/venv" ]]; then
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/venv/bin/activate"
else
  echo "[$(date --iso-8601=seconds)] WARNUNG: virtuelle Umgebung nicht gefunden, verwende System-Python" >> "$LOG_FILE"
fi

python -m ai_act_labeler.cli --input "./incoming" --output "./processed" >> "$LOG_FILE" 2>&1

RESULT=$?
if [[ $RESULT -eq 0 ]]; then
  echo "[$(date --iso-8601=seconds)] Verarbeitung abgeschlossen: OK" >> "$LOG_FILE"
else
  echo "[$(date --iso-8601=seconds)] Verarbeitung fehlgeschlagen: Exit $RESULT" >> "$LOG_FILE"
fi

exit $RESULT
