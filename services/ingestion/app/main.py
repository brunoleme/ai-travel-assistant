from __future__ import annotations

import os
import sys


def main() -> None:
    """
    Phase 1 stub worker.
    Later this becomes the EDA entrypoint (SQS/SNS/EventBridge/Kinesis/etc).
    For now: just prove we can run it via Makefile.
    """
    mode = os.getenv("INGESTION_MODE", "local")
    if mode == "local":
        print("ingestion: ok (local mode)")
        return

    print(f"ingestion: unknown mode={mode}", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
