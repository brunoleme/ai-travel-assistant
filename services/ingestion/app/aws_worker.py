"""
AWS SQS worker for the ingestion pipeline.

When INGESTION_MODE=aws and INGESTION_QUEUE_URL is set, polls SQS, runs one
pipeline stage per message, and sends the next event to the main queue or DLQ.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from app.events import event_from_dict
from app.pipeline import (
    handle_chunk,
    handle_embed,
    handle_enrich,
    handle_fetch,
    handle_transcript,
    handle_write,
)


def _run_stage(body: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    """
    Run the pipeline stage for this event.
    Returns (next_event_dict, done). done=True only when write_complete finished.
    """
    event = event_from_dict(body)
    stage = event.stage

    if stage == "requested":
        out = handle_fetch(event)
    elif stage == "transcript":
        out = handle_transcript(event)
    elif stage == "chunks":
        out = handle_chunk(event)
    elif stage == "enrichment":
        out = handle_enrich(event)
    elif stage == "embeddings":
        out = handle_embed(event)
    elif stage == "write_complete":
        handle_write(event)
        return (None, True)  # Pipeline done
    else:
        return (None, False)

    if out is None:
        return (None, False)
    return (out.model_dump(), False)


def process_one_message(
    queue_url: str,
    dlq_url: str | None,
    receipt_handle: str,
    body: dict[str, Any],
) -> None:
    """
    Process one SQS message: run stage, send next event to queue or DLQ, delete message.
    Uses boto3; call only when AWS mode is enabled.
    """
    import boto3

    client = boto3.client("sqs")
    next_body, done = _run_stage(body)

    if done:
        # Write complete; just delete.
        pass
    elif next_body is not None:
        client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(next_body))
    else:
        # Stage failed: retry or DLQ.
        doc = {**body, "retry_count": body.get("retry_count", 0) + 1, "error": body.get("error") or "stage failed"}
        if doc["retry_count"] < doc.get("max_retries", 3):
            client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(doc))
        elif dlq_url:
            client.send_message(QueueUrl=dlq_url, MessageBody=json.dumps(doc))

    client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)


def receive_and_process_once(queue_url: str, dlq_url: str | None, wait_seconds: int = 5) -> bool:
    """
    Receive one message from SQS, process it, then return.
    Returns True if a message was processed, False if no message.
    """
    import boto3

    client = boto3.client("sqs")
    resp = client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=wait_seconds,
    )
    messages = resp.get("Messages") or []
    if not messages:
        return False
    msg = messages[0]
    body = json.loads(msg["Body"])
    content_source_id = body.get("content_source_id", "?")
    stage = body.get("stage", "?")
    print(f"ingestion: processing content_source_id={content_source_id} stage={stage}", file=sys.stderr)
    process_one_message(queue_url, dlq_url, msg["ReceiptHandle"], body)
    if stage == "write_complete":
        print(f"ingestion: pipeline complete for {content_source_id}", file=sys.stderr)
    return True


def run_worker_loop() -> None:
    """
    Run the AWS ingestion worker loop: poll SQS, process messages, until interrupted.
    """
    queue_url = os.environ.get("INGESTION_QUEUE_URL", "").strip()
    dlq_url = os.environ.get("INGESTION_DLQ_URL", "").strip() or None
    if not queue_url:
        print("INGESTION_QUEUE_URL is required for AWS mode.", file=sys.stderr)
        raise SystemExit(2)

    print("ingestion: aws mode, polling", queue_url[:60] + "...", file=sys.stderr)
    while True:
        try:
            receive_and_process_once(queue_url, dlq_url)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"ingestion worker error: {e}", file=sys.stderr)
