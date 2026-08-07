"""Kommandozeilen-Einstiegspunkt: orchestriert die gesamte Pipeline.

Ablauf pro Datei (siehe README.md für Details):
1. Metadaten scannen (metadata_reader)
2. KI-Modell erkennen (model_detection)
3. Fehlende Metadaten ergänzen (metadata_writer), falls nötig
4. Sichtbares Badge ergänzen (visible_label), falls nötig
5. Ergebnis in Report aufnehmen (report)
6. Datei nach compliant/ oder review/ verschieben (file_router)

Aufruf-Beispiel:
    python -m ai_act_labeler.cli --input ./incoming --output ./processed
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import config, file_router, metadata_reader, metadata_writer, model_detection, report, visible_label


def _iter_input_files(input_root: Path):
    """Durchläuft rekursiv alle Dateien im Eingabeordner (alle Unterordner)."""
    for path in sorted(input_root.rglob("*")):
        if path.is_file():
            yield path


def _process_single_file(
    file_path: Path,
    input_root: Path,
    badge_path: Path,
    badge_position: str,
    cert_path: Path | None,
    key_path: Path | None,
    alg: str,
    timestamp: str,
) -> report.FileReportEntry:
    """Verarbeitet genau eine Datei und gibt den fertigen Report-Eintrag zurück.

    Wirft keine Exceptions nach außen weiter (fängt sie selbst und trägt sie
    als 'fehler' im Report-Eintrag ein) – ein einzelner Fehler soll den
    gesamten Batch-Lauf nicht abbrechen.
    """
    relative_path = str(file_path.relative_to(input_root))
    is_image = file_path.suffix.lower() in config.IMAGE_EXTENSIONS
    is_video = file_path.suffix.lower() in config.VIDEO_EXTENSIONS

    if not (is_image or is_video):
        return report.FileReportEntry(
            dateiname=file_path.name,
            relativer_pfad=relative_path,
            erkanntes_modell=config.UNKNOWN_MODEL_LABEL,
            metadaten_status_vorher="-",
            metadaten_status_nachher="-",
            sichtbare_kennzeichnung_vorher=False,
            sichtbare_kennzeichnung_nachher=False,
            zielordner=config.REVIEW_DIRNAME,
            fehler="Nicht unterstützter Dateityp",
            zeitstempel=timestamp,
        )

    try:
        # --- 1. Scan (auf der unveränderten Originaldatei) --------------
        scan_before = metadata_reader.scan_file(file_path)
        detected_model = model_detection.detect_model(
            scan_before.exif_iptc_xmp, scan_before.c2pa_raw_info
        )
        visible_before = (
            visible_label.image_has_visible_label(file_path)
            if is_image
            else visible_label.video_has_visible_label(file_path)
        )
        visible_after = visible_before

        # Sicherungskopie der unveränderten Originaldatei: wird gebraucht, um
        # nach dem Badge-Overlay bestehende Metadaten zurückzukopieren (siehe
        # Schritt 2 unten) – Pillow/ffmpeg erzeugen beim Speichern technisch
        # neue Dateien und übernehmen nicht zuverlässig alle EXIF/IPTC/XMP-Felder.
        with tempfile.TemporaryDirectory() as backup_dir:
            original_backup = Path(backup_dir) / f"original_{file_path.name}"
            shutil.copy2(file_path, original_backup)

            # --- 2. Sichtbares Badge ergänzen (nur wenn kein Label erkannt) ---
            # WICHTIG: Das Badge muss VOR dem C2PA-Manifest eingefügt werden,
            # nicht danach – C2PA signiert einen Hash der finalen Bild-/Video-
            # daten. Würde man das Badge erst nach der Signatur einbrennen,
            # verursacht das eine Bild-/Videoänderung NACH der Signatur, wodurch
            # das Manifest bei jeder späteren Prüfung als ungültig auffiele.
            if not visible_before:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_badge_output = Path(tmp_dir) / f"badge_{file_path.name}"
                    if is_image:
                        visible_label.add_badge_to_image(
                            file_path, tmp_badge_output, badge_path, badge_position
                        )
                    else:
                        visible_label.add_badge_to_video(
                            file_path, tmp_badge_output, badge_path, badge_position
                        )
                    shutil.move(str(tmp_badge_output), str(file_path))
                metadata_writer.restore_original_metadata(original_backup, file_path)
                visible_after = True

        # --- 3. Metadaten ergänzen (IPTC + C2PA), zuletzt und auf Basis   ---
        # --- des tatsächlichen aktuellen Zustands (nicht des Zustands vor  ---
        # --- dem Badge-Schritt, der ein vorher gültiges C2PA invalidiert    ---
        # --- haben kann, falls ein Badge eingefügt wurde).                  ---
        status_after = metadata_reader.scan_file(file_path).status
        if status_after != config.STATUS_FULL:
            metadata_writer.set_iptc_digital_source_type(file_path)

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_c2pa_output = Path(tmp_dir) / f"c2pa_{file_path.name}"
                metadata_writer.embed_c2pa_manifest(
                    file_path, tmp_c2pa_output, detected_model, cert_path, key_path, alg
                )
                shutil.move(str(tmp_c2pa_output), str(file_path))

            # Nach dem Schreiben erneut scannen, um den tatsächlichen Status
            # zu dokumentieren (statt ihn nur anzunehmen).
            status_after = metadata_reader.scan_file(file_path).status

        return report.FileReportEntry(
            dateiname=file_path.name,
            relativer_pfad=relative_path,
            erkanntes_modell=detected_model,
            metadaten_status_vorher=scan_before.status,
            metadaten_status_nachher=status_after,
            sichtbare_kennzeichnung_vorher=visible_before,
            sichtbare_kennzeichnung_nachher=visible_after,
            zielordner=config.COMPLIANT_DIRNAME,
            fehler="",
            zeitstempel=timestamp,
        )

    except Exception as exc:  # noqa: BLE001 - bewusst breit, siehe Docstring
        return report.FileReportEntry(
            dateiname=file_path.name,
            relativer_pfad=relative_path,
            erkanntes_modell=config.UNKNOWN_MODEL_LABEL,
            metadaten_status_vorher="-",
            metadaten_status_nachher="-",
            sichtbare_kennzeichnung_vorher=False,
            sichtbare_kennzeichnung_nachher=False,
            zielordner=config.REVIEW_DIRNAME,
            fehler=str(exc),
            zeitstempel=timestamp,
        )


def run(
    input_dir: Path,
    output_dir: Path,
    badge_path: Path | None,
    badge_position: str,
    cert_path: Path | None,
    key_path: Path | None,
    alg: str = config.C2PA_DEFAULT_SIGNING_ALG,
) -> list[report.FileReportEntry]:
    """Führt den gesamten Batch-Lauf aus und gibt alle Report-Einträge zurück."""
    resolved_badge_path = badge_path or visible_label.ensure_default_badge_exists()
    timestamp = datetime.now(timezone.utc).isoformat()

    entries: list[report.FileReportEntry] = []
    for file_path in _iter_input_files(input_dir):
        entry = _process_single_file(
            file_path, input_dir, resolved_badge_path, badge_position, cert_path, key_path, alg, timestamp
        )
        entries.append(entry)

        # Datei entsprechend Ergebnis in compliant/ oder review/ verschieben.
        if entry.zielordner == config.COMPLIANT_DIRNAME:
            file_router.route_to_compliant(file_path, input_dir, output_dir)
        else:
            file_router.route_to_review(file_path, input_dir, output_dir)

    report.write_reports(entries, output_dir, config.REPORT_BASENAME)
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prüft und ergänzt AI-Act-konforme Kennzeichnung für KI-generierte Produktmedien."
    )
    parser.add_argument("--input", required=True, type=Path, help="Eingabeordner (wird rekursiv durchsucht)")
    parser.add_argument("--output", required=True, type=Path, help="Ausgabeordner (enthält compliant/, review/, report.*)")
    parser.add_argument("--badge", type=Path, default=None, help="Eigenes Badge-PNG (optional, sonst wird ein Standard-Badge generiert)")
    parser.add_argument(
        "--badge-position",
        default=config.DEFAULT_BADGE_POSITION,
        choices=["bottom-right", "bottom-left", "top-right", "top-left"],
        help="Position des Badges (Default: bottom-right)",
    )
    parser.add_argument("--cert", type=Path, default=None, help="Pfad zu einem eigenen C2PA-Signaturzertifikat (.pem)")
    parser.add_argument("--key", type=Path, default=None, help="Pfad zum passenden privaten Schlüssel (.pem)")
    parser.add_argument(
        "--alg",
        default=config.C2PA_DEFAULT_SIGNING_ALG,
        help="Signaturalgorithmus für c2patool, muss zum --key passen (Default: es256 für EC-Keys; RSA-Keys benötigen z.B. ps256)",
    )
    args = parser.parse_args()

    if not args.input.is_dir():
        parser.error(f"Eingabeordner '{args.input}' existiert nicht oder ist kein Ordner.")

    entries = run(args.input, args.output, args.badge, args.badge_position, args.cert, args.key, args.alg)

    n_compliant = sum(1 for e in entries if e.zielordner == config.COMPLIANT_DIRNAME)
    n_review = sum(1 for e in entries if e.zielordner == config.REVIEW_DIRNAME)
    print(f"Fertig: {len(entries)} Dateien verarbeitet -> {n_compliant} compliant, {n_review} zur Review.")
    print(f"Report: {args.output / config.REPORT_BASENAME}.csv / .json")


if __name__ == "__main__":
    main()
