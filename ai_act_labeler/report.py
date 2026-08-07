"""Erzeugt den CSV- und JSON-Report über alle verarbeiteten Dateien.

Der Report ist die zentrale Nachweis-Grundlage für Compliance-Prüfungen:
für jede Datei wird dokumentiert, was vorher/nachher der Fall war und wann
geprüft wurde.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class FileReportEntry:
    """Eine Zeile im Report – entspricht genau einer verarbeiteten Datei."""

    dateiname: str
    relativer_pfad: str
    erkanntes_modell: str
    metadaten_status_vorher: str
    metadaten_status_nachher: str
    sichtbare_kennzeichnung_vorher: bool
    sichtbare_kennzeichnung_nachher: bool
    zielordner: str  # "compliant" oder "review"
    fehler: str  # leer, falls kein Fehler aufgetreten ist
    zeitstempel: str  # ISO-8601, wird vom Aufrufer übergeben (siehe cli.py)


def write_reports(entries: list[FileReportEntry], output_dir: Path, base_name: str) -> None:
    """Schreibt den Report als <base_name>.csv UND <base_name>.json.

    Beide Formate werden erzeugt, da CSV sich für Excel/manuelle Sichtprüfung
    eignet, JSON hingegen leicht von anderen Systemen (z.B. CMS/PIM) weiter-
    verarbeitet werden kann.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{base_name}.csv"
    json_path = output_dir / f"{base_name}.json"

    rows = [asdict(entry) for entry in entries]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        else:
            f.write("")

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
