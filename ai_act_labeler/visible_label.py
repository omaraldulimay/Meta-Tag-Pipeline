"""Prüft und ergänzt die für Menschen sichtbare 'KI-generiert'-Kennzeichnung.

Zwei Aufgaben:
1. Heuristischer Check per OCR (Tesseract), ob bereits ein Text-Label in einer
   Bildecke sichtbar ist (Bild) bzw. im ersten Video-Frame.
   ACHTUNG: Dies ist eine Heuristik, keine Garantie. Sie erkennt zuverlässig
   Text-Badges (z.B. "KI-generiert", "AI generated"), aber keine rein
   grafischen Symbole ohne Text. Bei Unsicherheit lieber ein Badge zusätzlich
   einfügen als ein fehlendes Label zu übersehen (Compliance-Risiko wiegt
   schwerer als ein doppeltes Badge).
2. Falls kein Label erkannt wurde: Badge-Overlay einfügen
   - Bild: Pillow, halbtransparentes PNG an konfigurierter Position
   - Video: ffmpeg-Filter, Badge in den ersten 2 Sekunden einblenden
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False


def _corner_crops(image: Image.Image) -> list[Image.Image]:
    """Schneidet die vier Ecken eines Bildes aus (dort sitzen Badges typischerweise)."""
    w, h = image.size
    cw = int(w * config.OCR_CORNER_FRACTION)
    ch = int(h * config.OCR_CORNER_FRACTION)
    return [
        image.crop((0, 0, cw, ch)),                 # oben links
        image.crop((w - cw, 0, w, ch)),              # oben rechts
        image.crop((0, h - ch, cw, h)),               # unten links
        image.crop((w - cw, h - ch, w, h)),           # unten rechts
    ]


def _text_contains_keyword(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in config.VISIBLE_LABEL_KEYWORDS)


def image_has_visible_label(image_path: Path) -> bool:
    """OCR-Heuristik: prüft die vier Bildecken auf Kennzeichnungs-Schlüsselwörter.

    Gibt False zurück (= 'kein Label erkannt', Badge wird ergänzt), wenn
    Tesseract nicht installiert ist – lieber ein zusätzliches Badge als eine
    ungeprüfte Datei, die still ohne Kennzeichnung durchläuft.
    """
    if not _TESSERACT_AVAILABLE:
        return False

    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            for crop in _corner_crops(img):
                text = pytesseract.image_to_string(crop)
                if _text_contains_keyword(text):
                    return True
    except Exception:
        # Beschädigte/nicht lesbare Bilddatei -> kein Label erkennbar.
        return False

    return False


def video_has_visible_label(video_path: Path) -> bool:
    """OCR-Heuristik für Videos: extrahiert den ersten Frame und prüft ihn wie ein Bild."""
    if not _TESSERACT_AVAILABLE:
        return False

    with tempfile.TemporaryDirectory() as tmp_dir:
        frame_path = Path(tmp_dir) / "frame0.jpg"
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "quiet",
                "-i", str(video_path),
                "-frames:v", "1",
                str(frame_path),
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0 or not frame_path.exists():
            return False
        return image_has_visible_label(frame_path)


def ensure_default_badge_exists() -> Path:
    """Generiert das Standard-Badge-PNG, falls noch keines unter badge_assets/ liegt.

    Einfaches Design: abgerundete halbtransparente schwarze Box mit weißem Text
    'KI-generiert'. Bewusst schlicht gehalten – Teams mit eigenem Corporate
    Design sollten stattdessen --badge mit ihrem eigenen PNG nutzen.
    """
    # If an EU-provided badge PNG exists, prefer it (org/legal requirement).
    eu_badge = Path(__file__).parent / "badge_assets" / "eu_badge.png"
    if eu_badge.exists():
        return eu_badge

    if config.DEFAULT_BADGE_PATH.exists():
        return config.DEFAULT_BADGE_PATH

    config.DEFAULT_BADGE_PATH.parent.mkdir(parents=True, exist_ok=True)

    font = ImageFont.load_default(size=28)
    padding = 16

    # Erst mit Dummy-Bild die Textgröße berechnen, dann das echte Badge in
    # passender Größe erzeugen (vermeidet Ecken/Überstand um den Text).
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), config.DEFAULT_BADGE_TEXT, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    badge = Image.new(
        "RGBA", (text_w + 2 * padding, text_h + 2 * padding), (0, 0, 0, 0)
    )
    draw = ImageDraw.Draw(badge)
    draw.rounded_rectangle(
        (0, 0, badge.width, badge.height), radius=8, fill=(20, 20, 20, 190)
    )
    draw.text((padding, padding - bbox[1]), config.DEFAULT_BADGE_TEXT, font=font, fill=(255, 255, 255, 255))

    badge.save(config.DEFAULT_BADGE_PATH)
    return config.DEFAULT_BADGE_PATH


def _badge_position_to_xy(
    canvas_size: tuple[int, int], badge_size: tuple[int, int], position: str
) -> tuple[int, int]:
    """Berechnet die Pixel-Koordinate der oberen linken Ecke des Badges."""
    cw, ch = canvas_size
    bw, bh = badge_size
    m = config.BADGE_MARGIN_PX
    positions = {
        "bottom-right": (cw - bw - m, ch - bh - m),
        "bottom-left": (m, ch - bh - m),
        "top-right": (cw - bw - m, m),
        "top-left": (m, m),
    }
    if position not in positions:
        raise ValueError(
            f"Unbekannte Badge-Position '{position}'. "
            f"Erlaubt: {', '.join(positions)}."
        )
    return positions[position]


def add_badge_to_image(
    image_path: Path,
    output_path: Path,
    badge_path: Path,
    position: str = config.DEFAULT_BADGE_POSITION,
) -> None:
    """Fügt das Badge-PNG an der konfigurierten Position ins Bild ein.

    Arbeitet mit alpha_composite, damit Transparenz im Badge korrekt
    durchscheint. Das Ergebnis wird als neue Datei gespeichert (output_path),
    das Original bleibt unverändert, bis der file_router es final verschiebt.
    """
    with Image.open(image_path) as base, Image.open(badge_path) as badge:
        base = base.convert("RGBA")
        badge = badge.convert("RGBA")

        # Badge relativ zur Bildbreite skalieren (max. 20% der Breite), damit
        # es bei sehr großen/kleinen Produktbildern proportional bleibt.
        max_badge_w = int(base.width * 0.20)
        if badge.width > max_badge_w:
            scale = max_badge_w / badge.width
            badge = badge.resize(
                (max_badge_w, int(badge.height * scale)), Image.LANCZOS
            )

        xy = _badge_position_to_xy(base.size, badge.size, position)
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        layer.paste(badge, xy, badge)
        composited = Image.alpha_composite(base, layer)

        # Ursprungsformat beibehalten (z.B. JPEG kennt keine Transparenz).
        if image_path.suffix.lower() in (".jpg", ".jpeg"):
            composited = composited.convert("RGB")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        composited.save(output_path)


def add_badge_to_video(
    video_path: Path,
    output_path: Path,
    badge_path: Path,
    position: str = config.DEFAULT_BADGE_POSITION,
) -> None:
    """Blendet das Badge in den ersten config.VIDEO_BADGE_DURATION_SECONDS Sekunden ein.

    Nutzt den ffmpeg-'overlay'-Filter mit 'enable=between(t,0,X)', sodass das
    Badge nur am Anfang sichtbar ist (wie in der Aufgabenstellung gefordert)
    statt das gesamte Video zu überdecken.
    """
    position_expr = {
        "bottom-right": f"main_w-overlay_w-{config.BADGE_MARGIN_PX}:main_h-overlay_h-{config.BADGE_MARGIN_PX}",
        "bottom-left": f"{config.BADGE_MARGIN_PX}:main_h-overlay_h-{config.BADGE_MARGIN_PX}",
        "top-right": f"main_w-overlay_w-{config.BADGE_MARGIN_PX}:{config.BADGE_MARGIN_PX}",
        "top-left": f"{config.BADGE_MARGIN_PX}:{config.BADGE_MARGIN_PX}",
    }
    if position not in position_expr:
        raise ValueError(
            f"Unbekannte Badge-Position '{position}'. Erlaubt: {', '.join(position_expr)}."
        )

    overlay_filter = (
        f"[1][0]scale2ref=w=main_w*0.20:h=ow/mdar[badge][base];"
        f"[base][badge]overlay={position_expr[position]}:"
        f"enable='between(t,0,{config.VIDEO_BADGE_DURATION_SECONDS})'"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(video_path),
            "-i", str(badge_path),
            "-filter_complex", overlay_filter,
            "-codec:a", "copy",
            "-map_metadata", "0",  # Container-Metadaten vom Original übernehmen
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg konnte Badge nicht in Video einfügen bei {video_path.name}: "
            f"{result.stderr.strip()}"
        )
