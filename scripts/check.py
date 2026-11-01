#!/usr/bin/env python3
"""Validate every community pack and its sidecar — what you run before a PR.

    python3 scripts/check.py            # validate packs/
    python3 scripts/check.py <dir>      # validate another packs dir

Exit code 0 when everything is well formed, 1 otherwise. Checks format only
(schema 1 + the community id/sidecar rules + no two harness packs sharing a
component name); whether the content belongs in the gallery is a human review
decision.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import communitylib  # noqa: E402
import packlib  # noqa: E402


def main() -> int:
    packs = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "packs"
    if not packs.is_dir():
        print(f"no packs directory at {packs}", file=sys.stderr)
        return 1
    dirs = communitylib.iter_pack_dirs(packs)
    if not dirs:
        print("no packs yet (packs/ is empty)")
        return 0
    failed = False
    manifests = []
    for directory in dirs:
        try:
            loaded = communitylib.load_community_pack(directory)
            manifest, meta = loaded["manifest"], loaded["meta"]
            manifests.append(manifest)
            if manifest["kind"] == "prompts":
                count = f"{len(manifest['items'])} items"
            elif manifest["kind"] == "harness":
                count = f"{len(manifest['components'])} components, tier {manifest['tier']}"
            else:
                rules = json.loads((directory / "rules.json").read_text(encoding="utf-8"))["rules"]
                count = f"{len(rules)} rules"
            print(f"ok    {manifest['id']} {manifest['version']} by @{meta['author']['handle']} ({count})")
        except packlib.PackError as error:
            failed = True
            print(f"FAIL  {error}", file=sys.stderr)
    # Rules across packs: two harness packs may not install the same component name.
    try:
        communitylib.check_component_names(manifests)
    except packlib.PackError as error:
        failed = True
        print(f"FAIL  {error}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
