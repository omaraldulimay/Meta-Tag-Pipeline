"""Liest vorhandene Metadaten aus Bild- und Videodateien.

Nutzt drei externe CLI-Tools (müssen im PATH installiert sein):
- exiftool: liest EXIF/IPTC/XMP aus Bildern UND Videos
- ffprobe:  liest Container-/Stream-Metadaten aus Videos (ergänzend zu exiftool)
- c2patool: prüft, ob ein gültiges C2PA-Manifest (Content Credentials) eingebettet ist

Warum exiftool statt pyexiv2/piexif? pyexiv2 benötigt eine native exiv2-Bibliothek,
deren Installation je nach Betriebssystem unzuverlässig ist. exiftool ist ein
einzelnes Kommandozeilen-Programm (brew/apt/choco), das EXIF, IPTC und XMP
einheitlich abdeckt – auch für Videos.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import config


class ToolNotFoundError(RuntimeError):
    """Wird geworfen, wenn ein benötigtes externes CLI-Tool nicht installiert ist."""


def _require_tool(name: str) -> None:
    """Bricht mit einer klaren Fehlermeldung ab, falls ein CLI-Tool fehlt.

    Ohne diese Prüfung würde subprocess erst beim Aufruf mit einem kryptischen
    'FileNotFoundError' scheitern – das ist für ein Nicht-Entwickler-Team schwer
    zu debuggen.
    """
    if shutil.which(name) is None:
        raise ToolNotFoundError(
            f"Das benötigte Kommandozeilen-Tool '{name}' wurde nicht gefunden. "
            f"Bitte installieren (siehe README.md) und sicherstellen, dass es im PATH liegt."
        )


@dataclass
class ScanResult:
    """Ergebnis des Metadaten-Scans einer einzelnen Datei."""

    exif_iptc_xmp: dict = field(default_factory=dict)
    c2pa_manifest_present: bool = False
    c2pa_raw_info: str = ""
    status: str = config.STATUS_NONE  # full / partial / none


def read_exif_iptc_xmp(file_path: Path) -> dict:
    """Liest alle EXIF/IPTC/XMP-Felder einer Datei als flaches dict aus.

    exiftool gibt mit '-j' ein JSON-Array mit genau einem Objekt zurück
    (eines pro Eingabedatei). Gruppenpräfixe (-G1) helfen später bei der
    Modell-Erkennung, weil z.B. 'XMP:CreatorTool' von 'EXIF:Software'
    unterschieden werden kann.
    """
    _require_tool("exiftool")
    result = subprocess.run(
        ["exiftool", "-G1", "-j", str(file_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        # exiftool liefert bei beschädigten/fremden Dateien evtl. leeren Output.
        return {}
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return parsed[0] if parsed else {}


def read_video_container_metadata(file_path: Path) -> dict:
    """Liest zusätzliche Container-/Stream-Metadaten eines Videos via ffprobe.

    Dient als Ergänzung zu exiftool: manche Encoder schreiben Custom-Tags
    (z.B. 'comment', 'encoder') nur in die Container-Metadaten, die exiftool
    nicht immer vollständig ausliest.
    """
    _require_tool("ffprobe")
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def check_c2pa_manifest(file_path: Path) -> tuple[bool, str]:
    """Prüft per c2patool, ob ein gültiges C2PA-Manifest eingebettet ist.

    c2patool gibt bei Dateien ohne Manifest einen Fehler/leere Ausgabe zurück.
    Das ist kein Programmfehler, sondern der Normalfall für unmarkierte Dateien
    -> wir werten das als "kein Manifest vorhanden", nicht als Abbruch.
    """
    _require_tool("c2patool")
    result = subprocess.run(
        ["c2patool", str(file_path), "-d"],  # -d: Manifest als JSON ausgeben ("detailed")
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode == 0 and result.stdout.strip():
        return True, result.stdout
    return False, output


def _flatten_values(d: dict) -> list[str]:
    """Extrahiert alle String-Werte eines (verschachtelten) dicts für Textsuche."""
    values: list[str] = []
    for v in d.values():
        if isinstance(v, dict):
            values.extend(_flatten_values(v))
        elif isinstance(v, list):
            values.extend(str(item) for item in v)
        elif v is not None:
            values.append(str(v))
    return values


def _bare_tag_name(exiftool_key: str) -> str:
    """Entfernt das Gruppenpräfix eines exiftool -G1-Keys, z.B. 'IFD0:Software' -> 'software'.

    exiftool nutzt je nach Dateityp/Version unterschiedliche Gruppen für denselben
    Tag (z.B. 'IFD0:Software' bei JPEG, 'EXIF:Software' bei anderen Formaten).
    Der Abgleich mit config.PARTIAL_MARKER_FIELDS erfolgt deshalb bewusst nur
    über den Tag-Namen selbst, nicht über die Gruppe.
    """
    return exiftool_key.rsplit(":", 1)[-1].lower()


def classify_status(exif_data: dict, c2pa_present: bool) -> str:
    """Ordnet eine Datei in 'vollständig' / 'teilweise' / 'nicht markiert' ein.

    Regel (siehe Aufgabenstellung):
    - vollständig: C2PA-Manifest vorhanden UND IPTC Digital Source Type korrekt gesetzt
    - teilweise:   nur ein EXIF/XMP-Hinweis vorhanden (z.B. CreatorTool), aber kein C2PA
    - nicht:       weder noch
    """
    bare_keys_with_values = {
        _bare_tag_name(k): v for k, v in exif_data.items() if v not in (None, "")
    }

    iptc_correct = (
        str(bare_keys_with_values.get("digitalsourcetype", "")).strip()
        == config.IPTC_DIGITAL_SOURCE_TYPE
    ) or any(
        config.IPTC_DIGITAL_SOURCE_TYPE.lower() in str(v).lower()
        for v in _flatten_values(exif_data)
    )

    if c2pa_present and iptc_correct:
        return config.STATUS_FULL

    has_partial_hint = any(
        marker in bare_keys_with_values for marker in config.PARTIAL_MARKER_FIELDS
    )
    if c2pa_present or has_partial_hint or iptc_correct:
        return config.STATUS_PARTIAL

    return config.STATUS_NONE


def scan_file(file_path: Path) -> ScanResult:
    """Führt den vollständigen Metadaten-Scan (Schritt 1 der Pipeline) durch."""
    exif_data = read_exif_iptc_xmp(file_path)

    if file_path.suffix.lower() in config.VIDEO_EXTENSIONS:
        # Container-Metadaten ergänzen exif_data, ohne bestehende Keys zu überschreiben.
        container_data = read_video_container_metadata(file_path)
        for key, value in _flatten_ffprobe_tags(container_data).items():
            exif_data.setdefault(key, value)

    c2pa_present, c2pa_raw = check_c2pa_manifest(file_path)
    status = classify_status(exif_data, c2pa_present)

    return ScanResult(
        exif_iptc_xmp=exif_data,
        c2pa_manifest_present=c2pa_present,
        c2pa_raw_info=c2pa_raw,
        status=status,
    )


def _flatten_ffprobe_tags(container_data: dict) -> dict:
    """Zieht die 'tags'-Objekte aus format/streams in ein flaches dict."""
    tags: dict = {}
    fmt_tags = container_data.get("format", {}).get("tags", {})
    tags.update({f"ffprobe:format:{k}": v for k, v in fmt_tags.items()})
    for i, stream in enumerate(container_data.get("streams", [])):
        for k, v in stream.get("tags", {}).items():
            tags[f"ffprobe:stream{i}:{k}"] = v
    return tags
