"""Best-Effort-Erkennung, mit welchem KI-Generator eine Datei erstellt wurde.

Die Erkennung basiert ausschließlich auf Textmustern in den bereits gelesenen
Metadaten (siehe metadata_reader.py) – es gibt keine 'offizielle' Kennzeichnung
des Modells, daher ist dies eine Heuristik. Neue Tools/Modelle können einfach
in config.MODEL_SIGNATURES ergänzt werden, ohne diese Datei zu ändern.
"""

from __future__ import annotations

from . import config


def _flatten_values(d: dict) -> list[str]:
    """Extrahiert alle (verschachtelten) Werte eines dicts als Strings."""
    values: list[str] = []
    for v in d.values():
        if isinstance(v, dict):
            values.extend(_flatten_values(v))
        elif isinstance(v, list):
            values.extend(str(item) for item in v)
        elif v is not None:
            values.append(str(v))
    return values


def detect_model(exif_data: dict, c2pa_raw_info: str = "") -> str:
    """Gibt den Namen des erkannten KI-Generators zurück, oder 'unbekannt'.

    Durchsucht alle Metadaten-Werte (case-insensitiv) nach den in
    config.MODEL_SIGNATURES definierten Teilstrings. Das C2PA-Manifest
    (falls vorhanden) wird zusätzlich durchsucht, da dort z.B. der
    'claim_generator' oft den Tool-Namen enthält.
    """
    haystack = " ".join(_flatten_values(exif_data)) + " " + c2pa_raw_info
    haystack_lower = haystack.lower()

    for model_name, patterns in config.MODEL_SIGNATURES:
        for pattern in patterns:
            if pattern.lower() in haystack_lower:
                return model_name

    return config.UNKNOWN_MODEL_LABEL
