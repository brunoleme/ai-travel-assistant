"""
CLI to replay DLQ events back into the active pipeline.

Usage:
    uv run python -m app.replay_dlq
"""

from __future__ import annotations

import sys

from app.dlq import replay_dlq_to_requeue


def main() -> None:
    """Replay all DLQ events back into the pipeline (requeue)."""
    n = replay_dlq_to_requeue()
    if n == 0:
        print("No events in DLQ.", file=sys.stderr)
        sys.exit(0)
    print(f"Replayed {n} event(s) from DLQ to active pipeline.")
    sys.exit(0)


if __name__ == "__main__":
    main()
