"""Simple webhook receiver for Drive change notifications.

Deploy this to Cloud Run or any HTTPS-capable host. On notification it
triggers the local processing wrapper `drive_processor_api.run_processing`.

This is intentionally minimal; in production prefer to enqueue to Pub/Sub
and process via worker instances.
"""
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
import os
import logging

from .drive_processor_api import run_processing

app = FastAPI()
logger = logging.getLogger("drive_webhook")


@app.post("/drive-webhook")
async def drive_webhook(request: Request, background: BackgroundTasks):
    # Basic verification: require a secret header (set as environment var)
    secret = os.environ.get("DRIVE_WEBHOOK_SECRET")
    if secret:
        hdr = request.headers.get("X-Webhook-Token")
        if hdr != secret:
            raise HTTPException(status_code=401, detail="Invalid secret")

    body = await request.body()
    logger.info("Received webhook: %s", body[:200])

    # Process in background to return 200 quickly
    background.add_task(_background_process)
    return {"status": "accepted"}


def _background_process():
    # Read configuration from environment variables set when deploying
    sa = os.environ.get("SERVICE_ACCOUNT_FILE", "google-service-account.json")
    drive_folder = os.environ.get("DRIVE_FOLDER_ID")
    out_folder = os.environ.get("OUTPUT_DRIVE_FOLDER_ID")
    archive_folder = os.environ.get("ARCHIVE_DRIVE_FOLDER_ID")
    incoming = os.environ.get("INCOMING_DIR", "incoming")
    processed = os.environ.get("PROCESSED_DIR", "processed")

    try:
        run_processing(sa, drive_folder, out_folder, archive_folder, incoming, processed)
        logger.info("Processing finished")
    except Exception:
        logger.exception("Processing failed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
