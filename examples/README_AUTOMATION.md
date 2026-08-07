Automation (Push Webhook)
=========================

Recommended: deploy the webhook to Cloud Run and create a Drive watch channel that posts to it.

1) Deploy webhook (Cloud Run)

 - Build container (example):

   docker build -t gcr.io/PROJECT/ai-act-webhook -f examples/Dockerfile .
   docker push gcr.io/PROJECT/ai-act-webhook

 - Deploy to Cloud Run:

   gcloud run deploy ai-act-webhook --image gcr.io/PROJECT/ai-act-webhook --platform managed --allow-unauthenticated --region europe-west1

2) Start watch channel (once)

 - Run locally or on a trusted host to register the webhook URL with Drive:

   python examples/start_drive_watch.py --service-account-file google-service-account.json --webhook-url https://YOUR-CLOUD-RUN-URL/drive-webhook

3) Webhook behavior

 - The webhook will call the local processing wrapper which downloads, processes, uploads and archives files.
 - In production you should replace the direct processing call with enqueueing to Pub/Sub and have a worker pool consume jobs.

Security

 - Set `DRIVE_WEBHOOK_SECRET` env var and the `X-Webhook-Token` header on the watch registration (or validate channel IDs).
