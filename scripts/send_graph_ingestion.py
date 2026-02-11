#!/usr/bin/env python3
"""
Send one graph ingestion message (youtube_kg) for a single YouTube video to the ingestion SQS queue.

Usage (from repo root, with configs/.env loaded for INGESTION_QUEUE_URL and AWS):
  set -a && . configs/.env && set +a
  python scripts/send_graph_ingestion.py "https://www.youtube.com/watch?v=VIDEO_ID" [--destination-hint "Playa del Carmen"]

Requires: INGESTION_QUEUE_URL and AWS credentials in env.
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid


def _extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: send_graph_ingestion.py <video_url> [--destination-hint D] [--language-hint L]", file=sys.stderr)
        return 1
    video_url = sys.argv[1].strip()
    video_id = _extract_video_id(video_url)
    if not video_id:
        print("Could not extract video ID from URL.", file=sys.stderr)
        return 1
    destination_hint = ""
    language_hint = ""  # leave unset so pipeline defaults to "auto" (same as YouTube playlist)
    args = sys.argv[2:]
    for i, a in enumerate(args):
        if a == "--destination-hint" and i + 1 < len(args):
            destination_hint = args[i + 1]
        elif a == "--language-hint" and i + 1 < len(args):
            language_hint = args[i + 1]

    payload: dict = {
        "source_type": "youtube_kg",
        "video_url": video_url,
        "destination_hint": destination_hint,
        "extract_model": "gpt-4.1",
    }
    if language_hint:
        payload["language_hint"] = language_hint

    queue_url = os.environ.get("INGESTION_QUEUE_URL", "").strip()
    if not queue_url:
        print("INGESTION_QUEUE_URL must be set (e.g. from configs/.env).", file=sys.stderr)
        return 1

    content_source_id = f"youtube_kg:{video_id}"
    body = {
        "event_id": str(uuid.uuid4()),
        "content_source_id": content_source_id,
        "stage": "requested",
        "payload": payload,
        "retry_count": 0,
        "max_retries": 3,
        "error": None,
    }
    try:
        import boto3
        sqs = boto3.client("sqs")
        sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
        print(f"Sent {content_source_id} -> {video_url}")
    except Exception as e:
        print(f"Failed to send: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
