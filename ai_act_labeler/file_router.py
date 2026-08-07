"""Verschiebt verarbeitete Dateien in die Ziel-Ordnerstruktur.

Erfolgreich verarbeitete Dateien -> <output>/compliant/<relativer Unterpfad>/
Fehlerhafte/nicht unterstützte Dateien -> <output>/review/<relativer Unterpfad>/

Die relative Unterordnerstruktur des Eingabeordners bleibt erhalten, damit bei
sehr großen Batches (z.B. nach Produktkategorie sortiert) der Kontext nicht
verloren geht.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import config


def _destination_path(
    file_path: Path, input_root: Path, output_root: Path, subdir_name: str
) -> Path:
    relative = file_path.relative_to(input_root)
    return output_root / subdir_name / relative


def route_to_compliant(file_path: Path, input_root: Path, output_root: Path) -> Path:
    """Verschiebt eine erfolgreich verarbeitete Datei nach compliant/."""
    destination = _destination_path(file_path, input_root, output_root, config.COMPLIANT_DIRNAME)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(file_path), str(destination))
    return destination


def route_to_review(file_path: Path, input_root: Path, output_root: Path) -> Path:
    """Verschiebt eine fehlerhafte/nicht verarbeitbare Datei nach review/.

    Wichtig: Diese Funktion darf selbst nicht fehlschlagen, wenn file_path
    z.B. schon verschoben wurde (defensive Prüfung), da sie oft im
    Fehlerbehandlungspfad aufgerufen wird.
    """
    if not file_path.exists():
        return file_path
    destination = _destination_path(file_path, input_root, output_root, config.REVIEW_DIRNAME)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(file_path), str(destination))
    return destination
