"""Ergänzt fehlende Kennzeichnung in Metadaten (Schritt 3 der Pipeline).

Zwei unabhängige Schreib-Operationen:
1. IPTC-Feld 'Digital Source Type' per exiftool setzen (bestehende Felder
   bleiben erhalten, da exiftool immer nur die explizit angegebenen Tags ändert).
2. C2PA-Manifest per c2patool erzeugen, signieren und einbetten.

Beide Schritte werden nur für Dateien ausgeführt, die im Scan (metadata_reader.py)
als 'teilweise' oder 'nicht markiert' eingestuft wurden.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import cert_utils, config


class MetadataWriteError(RuntimeError):
    """Wird geworfen, wenn exiftool oder c2patool beim Schreiben fehlschlagen."""


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise MetadataWriteError(
            f"Das benötigte Kommandozeilen-Tool '{name}' wurde nicht gefunden. "
            f"Bitte installieren (siehe README.md)."
        )


def restore_original_metadata(original_path: Path, target_path: Path) -> None:
    """Kopiert alle Metadaten von original_path nach target_path zurück.

    Wird nach dem Badge-Overlay aufgerufen: Pillow (Bild) bzw. ein ffmpeg-
    Filtergraph (Video) erzeugen beim Speichern eine technisch neue Datei und
    übernehmen dabei nicht zuverlässig alle ursprünglichen EXIF/IPTC/XMP-Felder.
    Damit "bestehende Metadaten nicht unnötig überschrieben" werden (Vorgabe
    aus der Aufgabenstellung), werden sie hier explizit vom Original zurück-
    kopiert, bevor im nächsten Schritt IPTC/C2PA ergänzt werden.

    Bewusst als 'best effort' ohne Exception: Ein Fehler hier (z.B. weil ein
    Tag im Zielformat nicht existiert) darf die eigentliche Compliance-relevante
    Kennzeichnung (IPTC + C2PA, siehe unten) nicht verhindern.
    """
    if shutil.which("exiftool") is None:
        return
    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            "-TagsFromFile", str(original_path),
            "-all:all",
            "-icc_profile",
            str(target_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def set_iptc_digital_source_type(file_path: Path) -> None:
    """Setzt IPTC 'Digital Source Type' auf 'trainedAlgorithmicMedia'.

    '-overwrite_original' verhindert, dass exiftool eine '<datei>_original'-
    Sicherungskopie im selben Ordner anlegt (die sonst versehentlich mit in
    den Import wandern könnte). Da wir ohnehin vorher/nachher-Kopien über den
    file_router steuern, ist eine eigene Backup-Datei hier nicht nötig.
    Alle anderen Felder bleiben unverändert – exiftool schreibt ausschließlich
    das explizit genannte Tag.
    """
    _require_tool("exiftool")
    result = subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            f"-IPTC:DigitalSourceType={config.IPTC_DIGITAL_SOURCE_TYPE}",
            f"-XMP-iptcExt:DigitalSourceType={config.IPTC_DIGITAL_SOURCE_TYPE}",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise MetadataWriteError(
            f"exiftool konnte IPTC-Feld nicht setzen bei {file_path.name}: {result.stderr.strip()}"
        )


def _build_manifest_dict(detected_model: str) -> dict:
    """Baut das C2PA-Manifest-JSON, das c2patool zum Signieren/Einbetten braucht.

    'claim_generator' identifiziert unser Tool als Ersteller des Manifests.
    Die Assertion 'c2pa.actions' mit action 'c2pa.created'/'trainedAlgorithmicMedia'
    ist der Standard-Weg, KI-Erzeugung in C2PA abzubilden.
    """
    return {
        "claim_generator": config.C2PA_CLAIM_GENERATOR,
        "assertions": [
            {
                "label": "c2pa.actions",
                "data": {
                    "actions": [
                        {
                            "action": "c2pa.created",
                            "digitalSourceType": config.C2PA_ASSERTION_DIGITAL_SOURCE_TYPE,
                            "softwareAgent": (
                                detected_model
                                if detected_model != config.UNKNOWN_MODEL_LABEL
                                else config.C2PA_CLAIM_GENERATOR
                            ),
                        }
                    ]
                },
            }
        ],
    }


def _build_signer_settings_toml(cert_path: Path, key_path: Path, alg: str) -> str:
    """Baut den Inhalt einer c2patool-'--settings'-TOML-Datei.

    WICHTIG: c2patool (ab Version 0.27) erwartet 'sign_cert' und 'private_key'
    unter [signer.local] als INLINE-PEM-Text, nicht als Dateipfade – ein Pfad
    an dieser Stelle führt zu einem kryptischen OpenSSL-Decoder-Fehler. Deshalb
    wird der Datei-Inhalt hier eingelesen und direkt eingebettet.
    Als TOML-Mehrzeilen-String (\"\"\"...\"\"\") lässt sich PEM-Text 1:1 übernehmen.
    """
    cert_pem = cert_path.read_text().strip()
    key_pem = key_path.read_text().strip()
    return (
        "[signer.local]\n"
        f'alg = "{alg}"\n'
        f'sign_cert = """{cert_pem}\n"""\n'
        f'private_key = """{key_pem}\n"""\n'
    )


def embed_c2pa_manifest(
    file_path: Path,
    output_path: Path,
    detected_model: str,
    cert_path: Path | None = None,
    key_path: Path | None = None,
    alg: str = config.C2PA_DEFAULT_SIGNING_ALG,
) -> None:
    """Erzeugt ein signiertes C2PA-Manifest und bettet es in output_path ein.

    Nutzt entweder das per Parameter übergebene Zertifikat/Key, oder – falls
    keines angegeben ist – die automatisch generierte lokale Test-Zertifikatskette
    (siehe cert_utils.py). Die Signatur-Konfiguration wird c2patool über eine
    temporäre '--settings'-TOML-Datei übergeben (siehe _build_signer_settings_toml).
    """
    _require_tool("c2patool")

    if cert_path is None or key_path is None:
        cert_path, key_path = cert_utils.ensure_test_certificate()

    manifest = _build_manifest_dict(detected_model)
    settings_content = _build_signer_settings_toml(cert_path, key_path, alg)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        manifest_path = tmp / "manifest.json"
        settings_path = tmp / "settings.toml"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        settings_path.write_text(settings_content)

        result = subprocess.run(
            [
                "c2patool",
                str(file_path),
                "-m", str(manifest_path),
                "--settings", str(settings_path),
                "-o", str(output_path),
                "-f",  # überschreibt output_path, falls bereits vorhanden (z.B. bei Retry)
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise MetadataWriteError(
                f"c2patool konnte Manifest nicht einbetten bei {file_path.name}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
