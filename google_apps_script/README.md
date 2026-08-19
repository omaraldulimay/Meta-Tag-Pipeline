# AI-Act-Kennzeichnung als Google Apps Script

Setzt das IPTC/XMP-Feld "Digital Source Type" auf
`compositeWithTrainedAlgorithmicMedia`, komplett innerhalb von Google (Drive +
Apps Script) – ohne lokalen Rechner, ohne Cloud Run, ohne Webhook. Das ist die
Google-native Variante des lokalen `ai_act_labeler`/`examples/`-Workarounds in
diesem Repo.

## Was das Script tut

Ein Zeit-Trigger ruft periodisch `processFolder()` auf. Für jede JPEG-Datei im
konfigurierten Drive-Ordner, die das Ziel-Property noch nicht trägt, wird das
XMP-Paket im Bild direkt auf Byte-Ebene ergänzt/aktualisiert – die
Bilddaten selbst werden dabei nicht angefasst (verifiziert per
Pixel-Checksum-Vergleich vor/nach dem Schreiben).

## Wichtige fachliche Klarstellung: "IPTC" vs. "XMP"

"Digital Source Type" ist **ausschließlich** als XMP-Property definiert
(Schema `Iptc4xmpExt`, `http://iptc.org/std/Iptc4xmpExt/2008-02-29/`). Für das
alte binäre IPTC-IIM-Record (das Photoshop-"APP13"/"8BIM"-Segment) gibt es
dafür **kein** Gegenstück – dieses Feld existiert dort schlicht nicht (auch
nicht in aktuellen exiftool-Versionen: `-IPTC:DigitalSourceType` ist nicht
schreibbar, das habe ich lokal mit exiftool 13.55 geprüft).

Ein einziger XMP-Schreibvorgang deckt daher sowohl "IPTC" (der Standard, der
das Feld definiert – die International Press Telecommunications Council) als
auch "maschinenlesbar" ab, wie in der Aufgabenstellung vermutet. Es gibt hier
keine zweite, separate Baustelle.

**Wert-Format:** Es wird die volle Controlled-Vocabulary-URI geschrieben
(`http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia`),
nicht nur der Kurzname. Das entspricht dem URI-Wertetyp der IPTC-Spezifikation.
Zum Vergleich: Der lokale Python-Workaround (`ai_act_labeler/metadata_writer.py`,
`config.IPTC_DIGITAL_SOURCE_TYPE`) schreibt aktuell nur den Kurzname
`trainedAlgorithmicMedia` ohne URI-Präfix – das ist die gängige,
tolerant gelesene Kurzform, aber laut Spezifikation genaugenommen nicht
korrekt. Falls gewünscht, kann das dort angeglichen werden; das ist hier
bewusst nicht mit angefasst, da es ein anderes Pipeline-Teil betrifft.

## Setup

1. Neues Apps-Script-Projekt anlegen (z.B. über
   [script.google.com](https://script.google.com) oder direkt aus einem
   Drive-Ordner heraus über "Weitere Apps" -> "Google Apps Script").
2. `Code.gs`, `XmpJpeg.gs` und `appsscript.json` aus diesem Ordner in das
   Projekt übernehmen (Dateiinhalte 1:1 kopieren; `appsscript.json` ist über
   das Zahnrad-Icon "Projekteinstellungen" -> "`appsscript.json`-Manifestdatei
   anzeigen" erreichbar).
3. Im Editor links auf "Dienste" (Services) -> "+" -> **Drive API** (v3)
   hinzufügen. Das wird für das Ersetzen des Dateiinhalts bei gleicher
   Datei-ID benötigt (die einfache `DriveApp`-Basis-API kann keinen
   Binärinhalt schreiben).
4. In `Code.gs`: `CONFIG.SOURCE_FOLDER_ID` auf die Ordner-ID des zu
   überwachenden Drive-Ordners setzen (aus der Ordner-URL:
   `.../drive/folders/<DIESE_ID>`).
5. Funktion `runManually` auswählen und einmal manuell ausführen, um den
   OAuth-Berechtigungsdialog zu durchlaufen (Zugriff auf Drive).
6. Funktion `createTimeTrigger` einmal manuell ausführen, um den
   wiederkehrenden Trigger anzulegen (Standard: alle 5 Minuten,
   `CONFIG.POLL_INTERVAL_MINUTES`).

Danach läuft es automatisch: neue JPEGs im Ordner werden beim nächsten
Trigger-Durchlauf erkannt und getaggt.

## Idempotenz statt Ordner-Verschieben

Es gibt keinen separaten "erledigt"-Ordner. Stattdessen prüft
`XmpJpeg.isAlreadyTagged()` vor jedem Schreibvorgang, ob das Ziel-Property
bereits mit dem korrekten Wert vorhanden ist, und überspringt die Datei dann.
Dateien bleiben also im selben Ordner, werden aber nie doppelt bearbeitet.

## Grenzen / bewusst nicht implementiert

- **Nur JPEG.** PNG (XMP steckt dort in einem `iTXt`-Chunk) und WebP (XMP
  steckt in einem RIFF-`XMP `-Chunk, der bei "einfachen" WebP-Dateien zusätzlich
  eine Umwandlung in den Extended-Format-Container `VP8X` erfordert) verwenden
  jeweils ein komplett anderes Container-Format. Um keinen ungetesteten
  Binärformat-Code auszuliefern, ist das hier nicht mit abgedeckt. Falls
  benötigt, kann das gezielt ergänzt werden.
- **Kein C2PA-Manifest.** Der lokale Python-Workaround erzeugt zusätzlich ein
  signiertes C2PA-Manifest (`c2patool`). Das lässt sich in Apps Script nicht
  nachbilden (kein Zugriff auf ein Kommandozeilen-Tool, keine C2PA-Bibliothek
  für Apps Script). Falls C2PA auch über diesen Weg benötigt wird, bräuchte es
  einen externen Dienst (z.B. Cloud Run), an den Apps Script den Signiervorgang
  delegiert.
- **Extended XMP nicht implementiert.** Falls eine Datei bereits ein sehr
  großes XMP-Paket enthält (>~65 KB nach dem Hinzufügen des neuen Properties),
  bricht der Schreibvorgang mit einer Fehlermeldung ab (Datei wird
  übersprungen, im Log vermerkt) statt ein fehlerhaftes Segment zu erzeugen.
- **Kein echtzeitnaher Trigger.** Apps Script kennt kein natives
  "neue Datei in Drive-Ordner"-Ereignis. Die Erkennung erfolgt daher per
  Zeit-Trigger-Abfrage (Polling), minimal alle 1 Minute einstellbar.

## Dateien

```
google_apps_script/
├── Code.gs           # Orchestrierung: Ordner scannen, Trigger, Drive-Update
├── XmpJpeg.gs         # Byte-Ebene: XMP-Segment in JPEG lesen/schreiben
└── appsscript.json    # Manifest (aktiviert die Drive-API als Advanced Service)
```
