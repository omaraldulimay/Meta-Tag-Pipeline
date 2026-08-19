/**
 * Reine Byte-Manipulation eines JPEG, um das IPTC-Feld "Digital Source Type"
 * (Namespace Iptc4xmpExt, serialisiert in einem XMP-Paket im APP1-Segment)
 * zu setzen oder zu aktualisieren.
 *
 * WICHTIG zum Hintergrund: "Digital Source Type" ist ausschließlich als
 * XMP-Property definiert (Schema http://iptc.org/std/Iptc4xmpExt/2008-02-29/,
 * Property "DigitalSourceType"). Es gibt dafür KEIN Gegenstück im alten
 * binären IPTC-IIM-Record (Photoshop APP13/"8BIM") – das IIM-Schema kennt
 * dieses Feld schlicht nicht. Ein einziger XMP-Schreibvorgang deckt daher
 * sowohl "IPTC" (der Standard, der das Feld definiert) als auch
 * "maschinenlesbar" (XMP) ab.
 *
 * Nur JPEG wird unterstützt. PNG (iTXt-Chunk) und WebP (RIFF "XMP "-Chunk)
 * verwenden andere Container-Formate für XMP und sind hier bewusst NICHT
 * implementiert, um keinen ungetesteten Binärformat-Code auszuliefern.
 */

var XmpJpeg = (function () {
  var XMP_SIGNATURE = 'http://ns.adobe.com/xap/1.0/\u0000';
  var IPTC_EXT_NAMESPACE = 'http://iptc.org/std/Iptc4xmpExt/2008-02-29/';

  // Ziel-Wert lt. IPTC-Controlled-Vocabulary (volle URI, nicht nur der
  // Kurzname – siehe cv.iptc.org/newscodes/digitalsourcetype).
  var DIGITAL_SOURCE_TYPE_VALUE =
    'http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia';

  function toUnsignedBytes(signedBytes) {
    var out = new Array(signedBytes.length);
    for (var i = 0; i < signedBytes.length; i++) {
      var v = signedBytes[i];
      out[i] = v < 0 ? v + 256 : v;
    }
    return out;
  }

  function toSignedBytes(unsignedBytes) {
    var out = new Array(unsignedBytes.length);
    for (var i = 0; i < unsignedBytes.length; i++) {
      var v = unsignedBytes[i];
      out[i] = v > 127 ? v - 256 : v;
    }
    return out;
  }

  function stringToUtf8Bytes(str) {
    // Utilities.newBlob() encodiert JS-Strings als UTF-8, kein BOM.
    return toUnsignedBytes(Utilities.newBlob(str).getBytes());
  }

  function bytesToLatin1String(unsignedBytes, start, end) {
    // Für die XMP-Signatur (reines ASCII) genügt eine 1:1-Zeichenzuordnung.
    var s = '';
    for (var i = start; i < end; i++) {
      s += String.fromCharCode(unsignedBytes[i]);
    }
    return s;
  }

  function bytesToUtf8String(unsignedBytes, start, end) {
    var slice = unsignedBytes.slice(start, end);
    return Utilities.newBlob(toSignedBytes(slice)).getDataAsString('UTF-8');
  }

  /**
   * Zerlegt ein JPEG (als unsigned byte array) in seine Marker-Segmente.
   * Ab dem SOS-Marker (0xFFDA) werden die entropiekodierten Bilddaten NICHT
   * mehr interpretiert, sondern als ein einziger, unangetasteter Block bis
   * Dateiende behandelt (inkl. eingebetteter RSTn-Marker und EOI).
   */
  function readSegments(bytes) {
    if (bytes[0] !== 0xff || bytes[1] !== 0xd8) {
      throw new Error('Keine gültige JPEG-Datei (SOI-Marker fehlt).');
    }
    var segments = [];
    var i = 2;
    while (i < bytes.length) {
      if (bytes[i] !== 0xff) {
        throw new Error('Marker an Offset ' + i + ' erwartet, JPEG-Struktur unerwartet.');
      }
      var j = i + 1;
      while (bytes[j] === 0xff) j++; // Fill-Bytes überspringen
      var marker = bytes[j];

      if (marker === 0xd9) { // EOI ohne vorheriges SOS (untypisch, aber safe handhaben)
        segments.push({ marker: marker, start: i, end: j + 1, isSos: false });
        i = j + 1;
        break;
      }

      if (marker === 0xda) { // SOS: Header hat eigene Länge, danach folgen Scan-Daten
        var sosLen = (bytes[j + 1] << 8) | bytes[j + 2];
        var headerEnd = j + 1 + sosLen;
        segments.push({ marker: marker, start: i, end: headerEnd, isSos: true });
        segments.push({ marker: null, start: headerEnd, end: bytes.length, isTail: true });
        i = bytes.length;
        break;
      }

      if (marker >= 0xd0 && marker <= 0xd7) { // RST-Marker: kein Payload
        segments.push({ marker: marker, start: i, end: j + 1, isSos: false });
        i = j + 1;
        continue;
      }

      var len = (bytes[j + 1] << 8) | bytes[j + 2];
      var end = j + 1 + len;
      segments.push({ marker: marker, start: i, end: end, isSos: false });
      i = end;
    }
    return segments;
  }

  function findExistingXmpSegment(bytes, segments) {
    for (var s = 0; s < segments.length; s++) {
      var seg = segments[s];
      if (seg.marker === 0xe1) {
        var payloadStart = seg.start + 4; // FF E1 + 2 Länge-Bytes
        var sigLen = XMP_SIGNATURE.length;
        var sig = bytesToLatin1String(bytes, payloadStart, payloadStart + sigLen);
        if (sig === XMP_SIGNATURE) {
          var xml = bytesToUtf8String(bytes, payloadStart + sigLen, seg.end);
          return { seg: seg, xml: xml };
        }
      }
    }
    return null;
  }

  function upsertDigitalSourceType(xml) {
    var propRegex = /<Iptc4xmpExt:DigitalSourceType>[\s\S]*?<\/Iptc4xmpExt:DigitalSourceType>/;
    var newProp =
      '<Iptc4xmpExt:DigitalSourceType>' + DIGITAL_SOURCE_TYPE_VALUE + '</Iptc4xmpExt:DigitalSourceType>';

    if (propRegex.test(xml)) {
      return xml.replace(propRegex, newProp);
    }

    // Kein vorhandenes Property: neue rdf:Description mit lokal deklariertem
    // Namespace einfügen, damit bestehende Namespaces/Descriptions unangetastet bleiben.
    var newDescription =
      '<rdf:Description rdf:about="" xmlns:Iptc4xmpExt="' + IPTC_EXT_NAMESPACE + '">' +
      newProp +
      '</rdf:Description>';

    var rdfCloseRegex = /<\/rdf:RDF>/;
    if (rdfCloseRegex.test(xml)) {
      return xml.replace(rdfCloseRegex, newDescription + '</rdf:RDF>');
    }

    throw new Error('Vorhandenes XMP-Paket enthält kein <rdf:RDF> - kann nicht gepatcht werden.');
  }

  function buildFreshXmpPacket() {
    return (
      '<?xpacket begin="\uFEFF" id="W5M0MpCehiHzreSzNTczkc9d"?>\n' +
      '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n' +
      ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n' +
      '  <rdf:Description rdf:about="" xmlns:Iptc4xmpExt="' + IPTC_EXT_NAMESPACE + '">\n' +
      '   <Iptc4xmpExt:DigitalSourceType>' + DIGITAL_SOURCE_TYPE_VALUE + '</Iptc4xmpExt:DigitalSourceType>\n' +
      '  </rdf:Description>\n' +
      ' </rdf:RDF>\n' +
      '</x:xmpmeta>\n' +
      '<?xpacket end="w"?>'
    );
  }

  function buildApp1Segment(xml) {
    var sigBytes = stringToUtf8Bytes(XMP_SIGNATURE);
    var xmlBytes = stringToUtf8Bytes(xml);
    var payloadLen = sigBytes.length + xmlBytes.length;
    var segLen = payloadLen + 2; // Länge-Feld zählt sich selbst mit
    if (segLen > 0xffff) {
      throw new Error(
        'XMP-Paket zu groß für ein einzelnes APP1-Segment (' + segLen +
        ' Bytes). Extended XMP (mehrere Segmente) ist nicht implementiert.'
      );
    }
    var header = [0xff, 0xe1, (segLen >> 8) & 0xff, segLen & 0xff];
    return header.concat(sigBytes, xmlBytes);
  }

  /**
   * Prüft, ob die Datei das Ziel-Property bereits mit dem korrekten Wert trägt.
   * Dient als Idempotenz-Check, damit ein wiederholter Lauf (z.B. per
   * Zeit-Trigger) bereits getaggte Dateien nicht erneut anfasst.
   */
  function isAlreadyTagged(signedBytes) {
    var bytes = toUnsignedBytes(signedBytes);
    var segments = readSegments(bytes);
    var existing = findExistingXmpSegment(bytes, segments);
    if (!existing) return false;
    var escaped = DIGITAL_SOURCE_TYPE_VALUE.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    var valueRegex = new RegExp(
      '<Iptc4xmpExt:DigitalSourceType>\\s*' + escaped + '\\s*</Iptc4xmpExt:DigitalSourceType>'
    );
    return valueRegex.test(existing.xml);
  }

  /**
   * Hauptfunktion: nimmt die rohen (signed) Bytes einer JPEG-Datei entgegen
   * und gibt die rohen (signed) Bytes der getaggten Datei zurück.
   */
  function tagWithDigitalSourceType(signedBytes) {
    var bytes = toUnsignedBytes(signedBytes);
    var segments = readSegments(bytes);
    var existing = findExistingXmpSegment(bytes, segments);

    var xml = existing ? upsertDigitalSourceType(existing.xml) : buildFreshXmpPacket();
    var newApp1 = buildApp1Segment(xml);

    var out = [];
    out = out.concat(bytes.slice(0, 2)); // SOI

    var insertionDone = false;
    var cursor = 2;
    for (var s = 0; s < segments.length; s++) {
      var seg = segments[s];
      if (existing && seg === existing.seg) {
        out = out.concat(bytes.slice(cursor, seg.start));
        out = out.concat(newApp1);
        insertionDone = true;
        cursor = seg.end;
        continue;
      }
      if (!existing && !insertionDone && (seg.marker === 0xda || seg.isTail)) {
        out = out.concat(bytes.slice(cursor, seg.start));
        out = out.concat(newApp1);
        insertionDone = true;
        cursor = seg.start;
      }
    }
    out = out.concat(bytes.slice(cursor));

    if (!insertionDone) {
      throw new Error('Kein Einfügepunkt für das XMP-Segment gefunden.');
    }
    return toSignedBytes(out);
  }

  return {
    tagWithDigitalSourceType: tagWithDigitalSourceType,
    isAlreadyTagged: isAlreadyTagged,
    DIGITAL_SOURCE_TYPE_VALUE: DIGITAL_SOURCE_TYPE_VALUE
  };
})();
