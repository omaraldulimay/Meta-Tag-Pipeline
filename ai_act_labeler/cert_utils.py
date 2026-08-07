"""Erzeugt bei Bedarf eine lokale Test-Zertifikatskette für C2PA-Signaturen.

WARUM EINE KETTE (Mini-CA + Leaf-Zertifikat) UND NICHT NUR EIN EINZELNES
SELBSTSIGNIERTES ZERTIFIKAT?
c2patool lehnt ein rein selbstsigniertes Zertifikat als Signatur-Zertifikat
kategorisch ab (Fehler: "the certificate was self-signed") – das ist eine
bewusste C2PA-Vorgabe, damit niemand versehentlich mit einem trivial
selbstsignierten Zertifikat "vertrauenswürdig" wirkende Signaturen erzeugt.
Deshalb wird hier zweistufig vorgegangen:
  1. Eine lokale Test-CA (selbstsigniert, nur zum Ausstellen des Leaf-Zertifikats)
  2. Ein Leaf-("End-Entity"-)Zertifikat, das VON dieser Test-CA signiert wird
     und die für C2PA nötigen Extensions trägt (u.a. extendedKeyUsage=emailProtection,
     wie von c2patool/der C2PA-Spezifikation für Signatur-Zertifikate erwartet).

WICHTIG für die Produktion:
Diese Kette ist rein lokal und nirgends als vertrauenswürdig hinterlegt (kein
Eintrag in einer anerkannten Trust-List / Certificate Authority). c2patool
zeigt das im Manifest korrekt als "signingCredential.untrusted" an – der
technische Workflow (Manifest erzeugen, signieren, einbetten, auslesen)
funktioniert damit vollständig, aber für eine rechtssicher vertrauenswürdige
Signatur muss ein echtes Zertifikat einer anerkannten Stelle (z.B. über das
Content Authenticity Initiative Trust-List-Programm) per --cert/--key
hinterlegt werden (siehe README.md).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import config


class OpensslNotFoundError(RuntimeError):
    pass


def ensure_test_certificate(
    cert_path: Path = config.DEFAULT_CERT_PATH,
    key_path: Path = config.DEFAULT_KEY_PATH,
) -> tuple[Path, Path]:
    """Stellt sicher, dass eine lokale Test-Zertifikatskette existiert.

    Wird nur einmal erzeugt und danach für alle Folgeläufe wiederverwendet,
    damit nicht bei jedem Lauf eine neue Kette entsteht.

    Rückgabe: (cert_path, key_path), wobei cert_path auf die vollständige
    Kette (Leaf-Zertifikat + Test-CA, in dieser Reihenfolge) zeigt und
    key_path auf den privaten Schlüssel des Leaf-Zertifikats – exakt die
    beiden Dateien, die metadata_writer.embed_c2pa_manifest benötigt.
    """
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    if shutil.which("openssl") is None:
        raise OpensslNotFoundError(
            "openssl wurde nicht gefunden. Bitte installieren oder --cert/--key "
            "mit einem vorhandenen Zertifikat angeben (siehe README.md)."
        )

    cert_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ca_key = tmp / "ca_key.pem"
        ca_cert = tmp / "ca_cert.pem"
        leaf_csr = tmp / "leaf_csr.pem"

        # 1. Test-CA: selbstsigniert, darf ausschließlich zum Ausstellen von
        #    Leaf-Zertifikaten dienen (keyCertSign), nicht zum Signieren von Inhalten.
        subprocess.run(
            [
                "openssl", "req", "-x509", "-nodes",
                "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
                "-keyout", str(ca_key), "-out", str(ca_cert),
                "-days", "1825",
                "-subj", "/CN=AI-Act-Labeler Test CA/O=Internal Test/C=DE",
                "-addext", "basicConstraints=critical,CA:TRUE",
                "-addext", "keyUsage=critical,keyCertSign,cRLSign",
            ],
            check=True,
            capture_output=True,
        )

        # 2. Leaf-Schlüssel + Zertifikatsanfrage (CSR).
        subprocess.run(
            [
                "openssl", "req", "-nodes",
                "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
                "-keyout", str(key_path), "-out", str(leaf_csr),
                "-subj", "/CN=AI-Act-Labeler Signer/O=Internal Test/C=DE",
            ],
            check=True,
            capture_output=True,
        )

        # 3. Leaf-Zertifikat von der Test-CA signieren lassen, mit den von
        #    c2patool/C2PA erwarteten Extensions (kein CA-Zertifikat,
        #    digitalSignature + die EKU "emailProtection", die c2patool als
        #    gültige Signatur-EKU akzeptiert).
        ext_file = tmp / "leaf_ext.cnf"
        ext_file.write_text(
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,nonRepudiation\n"
            "extendedKeyUsage=critical,emailProtection\n"
        )
        leaf_cert = tmp / "leaf_cert.pem"
        subprocess.run(
            [
                "openssl", "x509", "-req",
                "-in", str(leaf_csr),
                "-CA", str(ca_cert), "-CAkey", str(ca_key), "-CAcreateserial",
                "-out", str(leaf_cert),
                "-days", "825",
                "-extfile", str(ext_file),
            ],
            check=True,
            capture_output=True,
        )

        # Kette = Leaf-Zertifikat + CA-Zertifikat, wie von c2patool für
        # 'sign_cert' erwartet (End-Entity-Zertifikat zuerst).
        cert_path.write_text(leaf_cert.read_text() + ca_cert.read_text())

    return cert_path, key_path
