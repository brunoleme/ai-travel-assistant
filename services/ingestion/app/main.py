from __future__ import annotations

import os
import sys


def main() -> None:
    """
    Ingestion worker: local (stub) or aws (SQS pipeline).
    Set INGESTION_MODE=aws and INGESTION_QUEUE_URL (and optionally INGESTION_DLQ_URL).
    """
    mode = os.getenv("INGESTION_MODE", "local")
    if mode == "local":
        print("ingestion: ok (local mode)")
        return
    if mode == "aws":
        from app.aws_worker import run_worker_loop

        run_worker_loop()
        return

    print(f"ingestion: unknown mode={mode}", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
