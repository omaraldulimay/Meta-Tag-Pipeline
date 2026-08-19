exiftool -overwrite_original -r \
  -IPTC:DigitalSourceType="compositeWithTrainedAlgorithmicMedia" \
  -XMP-iptcExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia" \
  "/path/to/project Metatags""""Start a Drive changes watch channel that points to the webhook URL.

Usage:
  python examples/start_drive_watch.py --service-account-file google-service-account.json --webhook-url https://.../drive-webhook
"""
from pathlib import Path
import argparse
import json
import uuid
from google.oauth2 import service_account
from googleapiclient.discovery import build


def start_watch(service_account_file: Path, webhook_url: str):
    creds = service_account.Credentials.from_service_account_file(
        service_account_file, scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    # Get startPageToken
    start = service.changes().getStartPageToken().execute()
    page_token = start.get("startPageToken")

    channel_id = str(uuid.uuid4())
    body = {
        "id": channel_id,
        "type": "web_hook",
        "address": webhook_url,
    }

    # Create watch channel for changes
    resp = service.changes().watch(pageToken=page_token, body=body, supportsAllDrives=True).execute()

    out = {
        "channel": resp,
        "startPageToken": page_token,
    }

    Path(".drive_watch.json").write_text(json.dumps(out, indent=2))
    print("Watch channel started and saved to .drive_watch.json")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--service-account-file", required=True)
    p.add_argument("--webhook-url", required=True)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    start_watch(Path(args.service_account_file), args.webhook_url)
