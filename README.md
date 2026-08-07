# AI-Act-Kennzeichnungs-Tool für Produktmedien

Prüft KI-generierte Produktbilder und -videos auf AI-Act-konforme Kennzeichnung
(Art. 50 EU AI Act) und ergänzt fehlende Kennzeichnung automatisch — sowohl in
Metadaten (IPTC "Digital Source Type" + C2PA Content Credentials) als auch
sichtbar (Badge/Wasserzeichen).

## 1. Installation

### 1.1 Externe Kommandozeilen-Tools

Diese müssen auf dem System installiert und im `PATH` verfügbar sein:

| Tool | Zweck | macOS (Homebrew) | Ubuntu/Debian |
|---|---|---|---|
| `exiftool` | EXIF/IPTC/XMP lesen & schreiben | `brew install exiftool` | `apt install libimage-exiftool-perl` |
| `ffmpeg` / `ffprobe` | Video-Metadaten, Frame-Extraktion, Badge-Overlay | `brew install ffmpeg` | `apt install ffmpeg` |
| `c2patool` | C2PA-Manifest (Content Credentials) lesen/schreiben | siehe [c2patool Releases](https://github.com/contentauth/c2patool/releases) | siehe Releases |
| `tesseract` | OCR für die Sichtbarkeits-Heuristik | `brew install tesseract` | `apt install tesseract-ocr` |
| `openssl` | Selbstsigniertes Test-Zertifikat erzeugen | i.d.R. vorinstalliert | i.d.R. vorinstalliert |

Prüfen, ob alles installiert ist:

```bash
exiftool -ver && ffmpeg -version && c2patool --version && tesseract --version && openssl version
```

### 1.2 Python-Abhängigkeiten

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Nutzung

```bash
python -m ai_act_labeler.cli --input ./incoming --output ./processed
```

Optionale Parameter:

```bash
python -m ai_act_labeler.cli \
    --input ./incoming \
    --output ./processed \
    --badge ./eigenes_badge.png \
    --badge-position bottom-right \
    --cert ./mein_cert.pem \
    --key ./mein_key.pem
```

| Parameter | Beschreibung | Default |
|---|---|---|
| `--input` | Eingabeordner, wird **rekursiv** durchsucht | (Pflicht) |
| `--output` | Ausgabeordner, enthält `compliant/`, `review/`, `report.csv`, `report.json` | (Pflicht) |
| `--badge` | Eigenes Badge-PNG (mit Transparenz) | Standard-Badge wird automatisch erzeugt |
| `--badge-position` | `bottom-right`, `bottom-left`, `top-right`, `top-left` | `bottom-right` |
| `--cert` / `--key` | Eigenes C2PA-Signaturzertifikat (Dateipfade zu PEM-Zertifikat/-Key) | Lokal generierte Test-Zertifikatskette (siehe unten) |
| `--alg` | Signaturalgorithmus, muss zum `--key` passen (`es256` für EC-, `ps256` für RSA-Keys) | `es256` |

Nach dem Lauf:
- **`processed/compliant/`** — Dateien, die erfolgreich geprüft/ergänzt wurden
- **`processed/review/`** — Dateien mit Fehlern oder nicht unterstütztem Dateityp
  (Grund steht im Report)
- **`processed/report.csv`** / **`processed/report.json`** — vollständiger Bericht

## 3. Wichtiger Hinweis: Selbstsigniertes Test-Zertifikat

Ohne `--cert`/`--key` erzeugt das Tool beim ersten Lauf automatisch ein
selbstsigniertes Zertifikat unter `~/.ai_act_labeler/test_cert/` und verwendet
es für alle weiteren Läufe wieder.

**Das reicht aus, um den technischen Workflow zu testen — aber ein
selbstsigniertes Zertifikat wird von keinem Content-Credentials-Viewer als
vertrauenswürdig angezeigt.** Für den Produktivbetrieb muss ein Zertifikat
einer anerkannten Stelle (z.B. über das Content Authenticity Initiative
Trust-List-Programm) beschafft und per `--cert`/`--key` eingebunden werden.

## 4. Grenzen der Sichtbarkeits-Prüfung (Schritt 4)

Der Check, ob ein Bild/Video bereits ein sichtbares "KI-generiert"-Label trägt,
läuft über eine **OCR-Heuristik** (Tesseract), die die vier Bildecken bzw. den
ersten Video-Frame nach Schlüsselwörtern durchsucht ("KI", "AI", "generiert",
"generated"). Das erkennt zuverlässig **Text-Badges**, aber keine rein
grafischen Symbole ohne Text. Im Zweifel wird lieber ein zusätzliches Badge
eingefügt, als eine fehlende Kennzeichnung zu übersehen.

Ist `tesseract` nicht installiert, wird automatisch davon ausgegangen, dass
kein Label vorhanden ist (Badge wird dann immer ergänzt).

## 5. Fehlerbehebung

| Problem | Lösung |
|---|---|
| `ToolNotFoundError: ... 'exiftool' ...` | Tool laut Tabelle in Abschnitt 1.1 installieren, Terminal neu starten |
| Datei landet in `review/` mit Fehler `c2patool konnte Manifest nicht einbetten` | Meist Zertifikatsproblem — `--cert`/`--key` prüfen oder Test-Zertifikat unter `~/.ai_act_labeler/test_cert/` löschen, damit es neu erzeugt wird |
| Datei landet in `review/` mit `Nicht unterstützter Dateityp` | Nur `.jpg/.jpeg/.png/.webp` (Bild) und `.mp4/.mov` (Video) werden verarbeitet |
| Video-Badge fehlt/falsch positioniert | `ffmpeg`-Version prüfen (`ffmpeg -version`), `overlay`-Filter erfordert ein aktuelles ffmpeg-Build |
| OCR erkennt vorhandenes Label nicht (Badge wird doppelt eingefügt) | Unkritisch — führt nur zu einem zusätzlichen Badge, keine falsche Kennzeichnung. Ggf. `OCR_CORNER_FRACTION` in `ai_act_labeler/config.py` vergrößern |

## 6. Projektstruktur

```
ai_act_labeler/
├── cli.py               # Einstiegspunkt, Orchestrierung
├── config.py            # Alle Konstanten/Defaults an einer Stelle
├── metadata_reader.py   # Schritt 1: Scan (exiftool/ffprobe/c2patool)
├── model_detection.py   # Schritt 2: Modell-Erkennung
├── cert_utils.py        # Selbstsigniertes Test-Zertifikat
├── metadata_writer.py   # Schritt 3: IPTC + C2PA-Manifest schreiben
├── visible_label.py     # Schritt 4: OCR-Check + Badge-Overlay
├── report.py            # Schritt 5: CSV/JSON-Report
├── file_router.py       # Schritt 6: compliant/ vs. review/
└── badge_assets/        # Standard-Badge (wird automatisch erzeugt)
```

Integration in eine bestehende Upload-Pipeline: `cli.py` vor dem CMS/PIM-Import
aufrufen und nur die Dateien aus `processed/compliant/` weiterverarbeiten;
`processed/review/` sollte von einem Menschen gesichtet werden.
