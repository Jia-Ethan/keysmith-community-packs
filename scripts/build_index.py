#!/usr/bin/env python3
"""Generate community-index.json for the gallery (Stage 1 reads it).

    python3 scripts/build_index.py

Validates every pack, then writes community-index.json at the repo root:
one schema-1 entry per pack plus a `meta` block (author, summary, category).
Deterministic: same packs in, same bytes out.

Stage 0 does not run a release, so --base-url defaults to a placeholder. Point
it at the real download base once a release exists.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import communitylib  # noqa: E402
import packlib  # noqa: E402

PLACEHOLDER_BASE = "https://example.invalid/community-packs"


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--packs", default=str(repo / "packs"))
    parser.add_argument("--out", default=str(repo / "community-index.json"))
    parser.add_argument("--base-url", default=PLACEHOLDER_BASE)
    parser.add_argument(
        "--generated-at",
        default=None,
        help="RFC 3339 timestamp; defaults to now (use a fixed value for reproducible output)",
    )
    args = parser.parse_args()

    generated_at = args.generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        index = communitylib.build_community_index(Path(args.packs), args.base_url, generated_at)
    except packlib.PackError as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1
    Path(args.out).write_bytes(packlib.canonical_json(index))
    print(f"wrote {args.out} ({len(index['packs'])} packs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
