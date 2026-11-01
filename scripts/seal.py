#!/usr/bin/env python3
"""Fill in the sha256 of every file a pack lists, then validate the pack and its sidecar.

    python3 scripts/seal.py packs/<id>

Covers prompt files (``items``), a rule pack's ``rules.json`` and a harness pack's
component files. Leave the hashes empty while you write; run this before the PR.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import communitylib  # noqa: E402
import packlib  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    directory = Path(sys.argv[1])
    manifest_path = directory / "pack.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        listed = [item["file"] for item in manifest.get("items", [])]
        for component in manifest.get("components", []):
            listed += [entry["path"] for entry in component.get("files", [])]
        for path in listed:
            packlib.safe_relative_path(path)
        for item in manifest.get("items", []):
            item["sha256"] = packlib.sha256_hex((directory / item["file"]).read_bytes())
        for component in manifest.get("components", []):
            for entry in component.get("files", []):
                entry["sha256"] = packlib.sha256_hex((directory / entry["path"]).read_bytes())
        rules = manifest.get("rules")
        if isinstance(rules, dict) and isinstance(rules.get("file"), str):
            packlib.safe_relative_path(rules["file"])
            rules["sha256"] = packlib.sha256_hex((directory / rules["file"]).read_bytes())
    except (OSError, KeyError, TypeError, AttributeError, json.JSONDecodeError, packlib.PackError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    manifest_path.write_bytes(packlib.canonical_json(manifest))
    try:
        communitylib.load_community_pack(directory)
    except packlib.PackError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"sealed {directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
