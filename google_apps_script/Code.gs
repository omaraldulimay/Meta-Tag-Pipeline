/**
 * Google Apps Script Variante der AI-Act-Metadaten-Kennzeichnung.
 *
 * Läuft komplett innerhalb von Google (kein lokaler Rechner, kein Cloud Run,
 * kein Webhook nötig): ein Zeit-Trigger ruft periodisch processFolder() auf,
 * das den konfigurierten Drive-Ordner nach JPEGs durchsucht, die noch nicht
 * das Ziel-Property tragen, und setzt es per XmpJpeg.gs (siehe dort für die
 * Details zum Metadaten-Schreibvorgang).
 *
 * Setup:
 * 1. In diesem Apps-Script-Projekt: Dienste (Services) -> "Drive API" (v3)
 *    hinzufügen (Advanced Service) - wird für das In-Place-Update der
 *    Dateiinhalte benötigt (DriveApp allein kann keinen Binärinhalt ersetzen).
 * 2. CONFIG.SOURCE_FOLDER_ID unten eintragen (Ordner-ID aus der Drive-URL,
 *    https://drive.google.com/drive/folders/<HIER_STEHT_DIE_ID>).
 * 3. Einmalig runManually() oder processFolder() manuell ausführen, um die
 *    Berechtigungs-Freigabe (OAuth-Consent) zu durchlaufen.
 * 4. createTimeTrigger() einmalig ausführen, um den wiederkehrenden Trigger
 *    anzulegen. deleteTimeTriggers() entfernt ihn wieder.
 */

var CONFIG = {
  SOURCE_FOLDER_ID: 'HIER_DRIVE_ORDNER_ID_EINTRAGEN',
  POLL_INTERVAL_MINUTES: 5 // erlaubt: 1, 5, 10, 15, 30
};

function processFolder() {
  var folder = DriveApp.getFolderById(CONFIG.SOURCE_FOLDER_ID);
  var files = folder.getFiles();
  var taggedCount = 0;
  var skippedCount = 0;
  var errorCount = 0;

  while (files.hasNext()) {
    var file = files.next();
    try {
      if (processFile(file)) {
        taggedCount++;
      } else {
        skippedCount++;
      }
    } catch (err) {
      errorCount++;
      Logger.log('Fehler bei "%s": %s', file.getName(), err);
    }
  }

  Logger.log(
    'Lauf abgeschlossen: %s getaggt, %s übersprungen, %s Fehler.',
    taggedCount, skippedCount, errorCount
  );
}

/**
 * Verarbeitet eine einzelne Datei. Gibt true zurück, wenn sie neu getaggt
 * wurde, false wenn sie übersprungen wurde (falscher Typ oder schon getaggt).
 */
function processFile(file) {
  if (file.getMimeType() !== MimeType.JPEG) {
    Logger.log('Überspringe "%s" (nicht unterstützter Typ: %s). Nur JPEG wird unterstützt.',
      file.getName(), file.getMimeType());
    return false;
  }

  var originalBytes = file.getBlob().getBytes();

  if (XmpJpeg.isAlreadyTagged(originalBytes)) {
    return false;
  }

  var taggedBytes = XmpJpeg.tagWithDigitalSourceType(originalBytes);
  var newBlob = Utilities.newBlob(taggedBytes, MimeType.JPEG, file.getName());

  // Advanced Drive Service: ersetzt den Dateiinhalt bei gleicher File-ID
  // (Kommentare, Freigaben, Ordner-Zuordnung bleiben erhalten).
  Drive.Files.update({}, file.getId(), newBlob);

  Logger.log('Getaggt: "%s" (%s Bytes -> %s Bytes)',
    file.getName(), originalBytes.length, taggedBytes.length);
  return true;
}

function createTimeTrigger() {
  deleteTimeTriggers();
  ScriptApp.newTrigger('processFolder')
    .timeBased()
    .everyMinutes(CONFIG.POLL_INTERVAL_MINUTES)
    .create();
  Logger.log('Trigger angelegt: alle %s Minuten.', CONFIG.POLL_INTERVAL_MINUTES);
}

function deleteTimeTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'processFolder') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
}

/** Für den ersten manuellen Testlauf inkl. OAuth-Consent-Dialog. */
function runManually() {
  processFolder();
}
