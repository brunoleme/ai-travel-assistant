#!/usr/bin/env python3
"""
Send one ingestion message per video in a YouTube playlist to the ingestion SQS queue.

Usage (from repo root, with configs/.env loaded for INGESTION_QUEUE_URL and AWS):
  set -a && . configs/.env && set +a
  python scripts/send_playlist_ingestion.py "https://www.youtube.com/playlist?list=PLt_pGH-ytqFM8z-BPOjUNa41DEQzaSlNC"
  # optional: --destination "Playa del Carmen" --playlist-name "Gabriel Lorenzi - Playa del Carmen"

Requires: yt-dlp on PATH, boto3, INGESTION_QUEUE_URL and AWS credentials in env.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid


def get_playlist_video_ids(playlist_url: str) -> list[tuple[str, str]]:
    """Return list of (video_id, video_url) for each video in the playlist."""
    # Use same Python as this script so yt-dlp from ingestion venv is used
    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "yt_dlp",
            "--flat-playlist",
            "-j",
            "--no-warnings",
            playlist_url,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if out.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {out.stderr or out.stdout}")
    pairs: list[tuple[str, str]] = []
    for line in out.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            vid = obj.get("id")
            if vid:
                pairs.append((vid, f"https://www.youtube.com/watch?v={vid}"))
        except json.JSONDecodeError:
            continue
    return pairs


def send_message(queue_url: str, body: dict) -> None:
    import boto3

    sqs = boto3.client("sqs")
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: send_playlist_ingestion.py <playlist_url> [--destination D] [--playlist-name N]", file=sys.stderr)
        return 1
    playlist_url = sys.argv[1].strip()
    destination = ""
    playlist_name = ""
    args = sys.argv[2:]
    for i, a in enumerate(args):
        if a == "--destination" and i + 1 < len(args):
            destination = args[i + 1]
        elif a == "--playlist-name" and i + 1 < len(args):
            playlist_name = args[i + 1]

    queue_url = os.environ.get("INGESTION_QUEUE_URL", "").strip()
    if not queue_url:
        print("INGESTION_QUEUE_URL must be set (e.g. from configs/.env).", file=sys.stderr)
        return 1

    try:
        pairs = get_playlist_video_ids(playlist_url)
    except Exception as e:
        print(f"Failed to get playlist: {e}", file=sys.stderr)
        return 1
    if not pairs:
        print("No videos found in playlist.", file=sys.stderr)
        return 1

    playlist_name = playlist_name or "YouTube playlist"
    for video_id, video_url in pairs:
        content_source_id = f"youtube:{video_id}"
        body = {
            "event_id": str(uuid.uuid4()),
            "content_source_id": content_source_id,
            "stage": "requested",
            "payload": {
                "source_type": "youtube",
                "video_url": video_url,
                "destination": destination,
                "playlist_url": playlist_url,
                "playlist_name": playlist_name,
            },
            "retry_count": 0,
            "max_retries": 3,
            "error": None,
        }
        try:
            send_message(queue_url, body)
            print(f"Sent {content_source_id} -> {video_url}")
        except Exception as e:
            print(f"Failed to send {content_source_id}: {e}", file=sys.stderr)
            return 1
    print(f"Enqueued {len(pairs)} video(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
