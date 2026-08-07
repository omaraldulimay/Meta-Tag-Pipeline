"""Zentrale Konfiguration und Konstanten.

Alle "Stellschrauben" des Tools sind hier gesammelt, damit das wartende
Team nicht in der Programmlogik nach Werten suchen muss.
"""

from pathlib import Path

# --- Unterstützte Dateitypen -------------------------------------------------

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# --- IPTC / C2PA Zielwerte ---------------------------------------------------

# Wert, den der AI Act / IPTC-Standard für KI-generierte Inhalte vorsieht.
IPTC_DIGITAL_SOURCE_TYPE = "trainedAlgorithmicMedia"

# "Nackte" Tag-Namen (ohne Gruppenpräfix), die als Hinweis auf KI-Erzeugung
# gelten, auch wenn kein C2PA-Manifest vorhanden ist ("teilweise markiert").
# Bewusst OHNE Gruppenpräfix (z.B. nicht "EXIF:Software"), da exiftool je nach
# Datei-Typ und Version unterschiedliche Gruppen verwendet (z.B. "IFD0:Software"
# bei JPEG statt "EXIF:Software") – der Vergleich erfolgt in metadata_reader.py
# über den Tag-Namen nach dem letzten ":", case-insensitiv.
PARTIAL_MARKER_FIELDS = [
    "digitalsourcetype",
    "aigenerated",
    "ai_generated",
    "creatortool",
    "software",
]

# --- Modell-Erkennung --------------------------------------------------------
# Reihenfolge ist relevant: erster Treffer gewinnt. Muster werden case-insensitiv
# als Teilstring in allen Metadaten-Werten gesucht.
# Ergänzt werden können hier jederzeit neue Tools, ohne Code an anderer Stelle
# anfassen zu müssen.
MODEL_SIGNATURES = [
    ("Midjourney", ["midjourney"]),
    ("DALL-E", ["dall-e", "dall·e", "openai"]),
    ("Adobe Firefly", ["firefly"]),
    ("Stable Diffusion", ["stable diffusion", "stability ai", "parameters:"]),
    ("Runway", ["runway", "gen-2", "gen-3", "gen-4"]),
    ("Sora", ["sora"]),
    ("Google Veo", ["veo"]),
    ("Kling", ["kling"]),
]

UNKNOWN_MODEL_LABEL = "unbekannt"

# --- Metadaten-Status --------------------------------------------------------

STATUS_FULL = "vollständig markiert"
STATUS_PARTIAL = "teilweise markiert"
STATUS_NONE = "nicht markiert"

# --- Sichtbare Kennzeichnung (OCR-Heuristik) --------------------------------

# Schlüsselwörter, nach denen die OCR-Heuristik in den Bildecken sucht.
# Bewusst kurz und sprachunabhängig gehalten – ein Treffer reicht.
VISIBLE_LABEL_KEYWORDS = ["ki", "ai", "generiert", "generated", "ki-generiert"]

# Anteil der Bildbreite/-höhe, der pro Ecke für die OCR ausgeschnitten wird.
# 0.25 bedeutet: die äußeren 25% jeder Kante werden untersucht.
OCR_CORNER_FRACTION = 0.25

# --- Badge (sichtbare Kennzeichnung, die ergänzt wird) ----------------------

DEFAULT_BADGE_PATH = Path(__file__).parent / "badge_assets" / "default_badge.png"
DEFAULT_BADGE_TEXT = "KI-generiert"
DEFAULT_BADGE_POSITION = "bottom-right"  # Optionen: bottom-right, bottom-left, top-right, top-left
BADGE_MARGIN_PX = 20
VIDEO_BADGE_DURATION_SECONDS = 2.0

# --- C2PA / Zertifikate ------------------------------------------------------

# Ablageort für das automatisch generierte Self-signed-Test-Zertifikat.
# Wird nur einmal erzeugt und danach wiederverwendet (siehe cert_utils.py).
DEFAULT_CERT_DIR = Path.home() / ".ai_act_labeler" / "test_cert"
DEFAULT_CERT_PATH = DEFAULT_CERT_DIR / "cert.pem"
DEFAULT_KEY_PATH = DEFAULT_CERT_DIR / "key.pem"

# c2patool erwartet eine kleine JSON-Manifest-Vorlage. "claim_generator" taucht
# im Content-Credentials-Viewer als Herkunftshinweis auf.
C2PA_CLAIM_GENERATOR = "ai-act-labeler/1.0"
C2PA_ASSERTION_DIGITAL_SOURCE_TYPE = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
)

# Signaturalgorithmus, den c2patool für den Signer erwartet. "es256" passt zu
# den EC-P-256-Schlüsseln, die cert_utils.py erzeugt. Wer ein eigenes
# RSA-Zertifikat per --cert/--key einsetzt, muss --alg ps256 angeben.
C2PA_DEFAULT_SIGNING_ALG = "es256"

# --- Ausgabe-Ordnernamen ------------------------------------------------------

COMPLIANT_DIRNAME = "compliant"
REVIEW_DIRNAME = "review"
REPORT_BASENAME = "report"  # es entstehen report.csv und report.json
