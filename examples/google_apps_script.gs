/**
 * Google Apps Script: Drive Image Tagging
 *
 * Dieses Script markiert Bilder in einem Google Drive Ordner als KI-generiert
 * und schreibt maschinenlesbare Metadaten in die Datei-Eigenschaften.
 *
 * Schritte:
 * 1) Öffne https://script.google.com und erstelle ein neues Projekt.
 * 2) Kopiere diesen Code in das Script.
 * 3) Ersetze FOLDER_ID_HERE durch die ID des Zielordners.
 * 4) Aktiviere in Apps Script die Drive API unter "Erweiterte Google-Dienste".
 * 5) Erstelle einen Zeittrigger, z. B. alle 5-15 Minuten.
 */

const TARGET_FOLDER_ID = 'FOLDER_ID_HERE';
const IPTC_VALUE = 'compositeWithTrainedAlgorithmicMedia';
const XMP_VALUE = 'http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia';

function tagDriveFolderImages() {
  const folder = DriveApp.getFolderById(TARGET_FOLDER_ID);
  const files = folder.getFiles();

  while (files.hasNext()) {
    const file = files.next();
    const mimeType = file.getMimeType();

    if (!mimeType.startsWith('image/')) {
      continue;
    }

    const fileId = file.getId();
    const resource = {
      appProperties: {
        digitalSourceType: IPTC_VALUE,
        xmpDigitalSourceType: XMP_VALUE,
      },
    };

    Drive.Files.update(resource, fileId);
  }
}
