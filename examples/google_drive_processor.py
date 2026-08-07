#!/usr/bin/env python3
"""Download images from Google Drive and process them with the AI Act tool.

This script supports separate Google Drive folders for input uploads and processed output.
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
import time
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov"}
DRIVE_SCOPE = ["https://www.googleapis.com/auth/drive"]


def get_drive_service(service_account_file: Path):
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file, scopes=DRIVE_SCOPE
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def list_files_in_folder(service, folder_id: str) -> list[dict[str, str]]:
    query = f"'{folder_id}' in parents and trashed=false"
    files: list[dict[str, str]] = []
    page_token = None

    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return files


def download_file(service, file_id: str, destination: Path) -> None:
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with io.FileIO(destination, mode="wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()


def is_supported_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def run_ai_act(input_dir: Path, output_dir: Path) -> int:
    command = [sys.executable, "-m", "ai_act_labeler.cli", "--input", str(input_dir), "--output", str(output_dir)]
    return subprocess.run(command).returncode


def move_file_to_folder(service, file_id: str, from_folder_id: str, to_folder_id: str) -> None:
    service.files().update(
        fileId=file_id,
        addParents=to_folder_id,
        removeParents=from_folder_id,
        fields="id, parents",
        supportsAllDrives=True,
    ).execute()


def upload_file_to_folder(service, source_path: Path, folder_id: str) -> None:
    file_metadata = {"name": source_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(source_path), resumable=True)
    service.files().create(body=file_metadata, media_body=media, fields="id", supportsAllDrives=True).execute()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download new Drive files and run AI Act labeling.")
    parser.add_argument("--service-account-file", type=Path, default=Path("google-service-account.json"), help="Path to the Google service account JSON file.")
    parser.add_argument("--drive-folder-id", required=True, help="Google Drive folder ID with uploaded images/videos.")
    parser.add_argument("--output-drive-folder-id", default=None, help="Optional Drive folder ID to upload processed compliant files into.")
    parser.add_argument("--archive-drive-folder-id", default=None, help="Optional Drive folder ID to move processed input files into after download.")
    parser.add_argument("--incoming", type=Path, default=Path("incoming"), help="Local incoming folder for downloaded files.")
    parser.add_argument("--processed", type=Path, default=Path("processed"), help="Local output folder for the AI Act tool.")
    parser.add_argument("--poll-interval", type=int, default=0, help="If >0, repeat the check every N seconds.")
    return parser.parse_args()


def process_once(args: argparse.Namespace, service) -> None:
    files = list_files_in_folder(service, args.drive_folder_id)
    supported_files = [f for f in files if is_supported_file(f["name"])]

    if not supported_files:
        print("Keine unterstützten Dateien im Drive-Ordner gefunden.")
        return

    for file_entry in supported_files:
        file_id = file_entry["id"]
        name = file_entry["name"]
        destination = args.incoming / name

        if destination.exists():
            print(f"Datei existiert bereits lokal, überspringe: {name}")
            continue

        print(f"Lade herunter: {name}")
        download_file(service, file_id, destination)

    print("Starte AI Act-Verarbeitung...")
    rc = run_ai_act(args.incoming, args.processed)
    if rc != 0:
        raise SystemExit(f"AI Act-Tool ist mit Exit-Code {rc} fehlgeschlagen.")

    if args.output_drive_folder_id:
        compliant_folder = args.processed / "compliant"
        if compliant_folder.exists():
            for local_file in compliant_folder.iterdir():
                if local_file.is_file() and is_supported_file(local_file.name):
                    print(f"Lade verarbeitete Datei in Drive-Output-Ordner hoch: {local_file.name}")
                    upload_file_to_folder(service, local_file, args.output_drive_folder_id)

    if args.archive_drive_folder_id:
        for file_entry in supported_files:
            print(f"Verschiebe Input-Datei in Drive-Archiv-Ordner: {file_entry['name']}")
            move_file_to_folder(service, file_entry["id"], args.drive_folder_id, args.archive_drive_folder_id)

    # Lokale Eingabedateien entfernen, um Wiederholungsverarbeitung zu verhindern
    for local_file in args.incoming.iterdir():
        if local_file.is_file() and is_supported_file(local_file.name):
            print(f"Lösche lokale Eingabedatei: {local_file.name}")
            local_file.unlink()


def main() -> None:
    args = parse_args()
    service = get_drive_service(args.service_account_file)

    if args.poll_interval > 0:
        while True:
            process_once(args, service)
            print(f"Warte {args.poll_interval} Sekunden bis zum nächsten Lauf...")
            time.sleep(args.poll_interval)
    else:
        process_once(args, service)


if __name__ == "__main__":
    main()
