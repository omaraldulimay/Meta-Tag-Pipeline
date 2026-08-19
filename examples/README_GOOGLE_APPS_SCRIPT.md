# Google Apps Script für Drive-Bild-Tagging

Dieses Beispiel benutzt Google Apps Script direkt in Google Drive.
Es markiert Bilder in einem Ordner mit maschinenlesbaren Metadaten:
- `digitalSourceType = compositeWithTrainedAlgorithmicMedia`
- `xmpDigitalSourceType = http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia`

## Setup
1. Öffne https://script.google.com und erstelle ein neues Projekt.
2. Kopiere den Inhalt von `examples/google_apps_script.gs` in dein Script.
3. Ersetze `FOLDER_ID_HERE` durch die ID des Zielordners.
4. Aktiviere in Apps Script unter `Erweiterte Google-Dienste` die `Drive API`.
5. Erstelle einen Trigger:
   - `Edit` → `Current project's triggers`
   - `Add Trigger`
   - Funktion: `tagDriveFolderImages`
   - Trigger: `Time-driven`
   - Intervall: z.B. `Every 5 minutes`

## Hinweis
- Das Script schreibt Metadaten in `appProperties` der Datei.
- Es ist keine lokale `exiftool`-Lösung mehr.
- Wenn später echte IPTC/XMP-Embed-Daten erforderlich sind, brauchen wir einen externen Workflow.
