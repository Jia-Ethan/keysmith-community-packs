"""Community-specific rules on top of the vendored schema-1 validator.

A community pack is an ordinary schema-1 pack (validated by ``packlib``) plus a
registry sidecar ``packs/<id>.meta.json`` that carries author and gallery
metadata the pack format itself has no field for. The pack directory stays
pure schema-1 so the App can consume it unchanged later; everything
registry-only lives in the sidecar, next to the pack rather than inside it
(``packlib.load_pack`` rejects any file a pack.json does not list).

Standard library only, same as ``packlib``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import packlib

# Author handle: GitHub-login shaped (lowercase, digits, single hyphens, <= 39).
HANDLE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_HANDLE_LEN = 39
# The official namespace. Community packs may not claim it, so no community pack
# can present itself as official.
RESERVED_FIRST_SEGMENTS = {"keysmith"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_CATEGORY_LEN = 32
CATEGORY = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_SUMMARY_CHARS = 280
MAX_URL_LEN = 300


class CommunityError(packlib.PackError):
    """A pack that is valid schema-1 but breaks a community-registry rule."""


def meta_path_for(pack_dir: Path) -> Path:
    return pack_dir.parent / f"{pack_dir.name}.meta.json"


def _first_segment(pack_id: str) -> str:
    return pack_id.split(".", 1)[0]


def validate_community_id(pack_id: str) -> str:
    """Community ids are ``<handle>.<slug>`` and never in the official namespace."""
    if "." not in pack_id:
        raise CommunityError(
            f"{pack_id}: community pack id must be '<author-handle>.<slug>' (needs a dot)"
        )
    handle = _first_segment(pack_id)
    if handle in RESERVED_FIRST_SEGMENTS:
        raise CommunityError(
            f"{pack_id}: '{handle}.' is the official namespace and is reserved"
        )
    if not HANDLE.match(handle) or len(handle) > MAX_HANDLE_LEN:
        raise CommunityError(
            f"{pack_id}: the first segment must be a valid author handle"
        )
    return handle


def _opt_url(value: Any, label: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise CommunityError(f"{label}: must be a non-empty string when present")
    if len(value) > MAX_URL_LEN:
        raise CommunityError(f"{label}: longer than {MAX_URL_LEN} characters")
    if not (value.startswith("https://") or value.startswith("http://")):
        raise CommunityError(f"{label}: must be an http(s) URL")


def validate_meta(meta: Any, pack_id: str, where: str) -> Dict[str, Any]:
    if not isinstance(meta, dict):
        raise CommunityError(f"{where}: must be a JSON object")
    allowed = {"author", "summary", "category", "source_url", "submitted_at", "request"}
    extra = set(meta) - allowed
    if extra:
        raise CommunityError(f"{where}: unknown keys {sorted(extra)}")

    author = meta.get("author")
    if not isinstance(author, dict):
        raise CommunityError(f"{where}: author must be an object")
    author_extra = set(author) - {"handle", "name", "url"}
    if author_extra:
        raise CommunityError(f"{where}: author has unknown keys {sorted(author_extra)}")
    handle = author.get("handle")
    if not isinstance(handle, str) or not HANDLE.match(handle) or len(handle) > MAX_HANDLE_LEN:
        raise CommunityError(f"{where}: author.handle must be a GitHub-style handle")
    expected = _first_segment(pack_id)
    if handle != expected:
        raise CommunityError(
            f"{where}: author.handle {handle!r} must match the pack id's first segment {expected!r}"
        )
    if "name" in author and (not isinstance(author["name"], str) or not author["name"].strip()):
        raise CommunityError(f"{where}: author.name must be a non-empty string when present")
    _opt_url(author.get("url"), f"{where}: author.url")

    summary = meta.get("summary")
    # Reuse the pack format's localized-string rule: an object keyed by known
    # locales, at least one non-empty.
    packlib._localized(summary, "summary", where)
    for key, text in summary.items():
        if len(text) > MAX_SUMMARY_CHARS:
            raise CommunityError(f"{where}: summary[{key}] longer than {MAX_SUMMARY_CHARS} characters")

    category = meta.get("category")
    if category is not None:
        if not isinstance(category, str) or not CATEGORY.match(category) or len(category) > MAX_CATEGORY_LEN:
            raise CommunityError(f"{where}: category must be a short lowercase slug")

    _opt_url(meta.get("source_url"), f"{where}: source_url")

    submitted = meta.get("submitted_at")
    if submitted is not None and (not isinstance(submitted, str) or not DATE.match(submitted)):
        raise CommunityError(f"{where}: submitted_at must be a YYYY-MM-DD date")

    # The request this pack answers: the issue number and who asked, so the gallery can
    # credit the idea and the build. Optional; the issue itself is the record.
    request = meta.get("request")
    if request is not None:
        if not isinstance(request, dict) or set(request) - {"issue", "by"} or "issue" not in request:
            raise CommunityError(f"{where}: request must be an object with issue (and optional by)")
        issue = request["issue"]
        if isinstance(issue, bool) or not isinstance(issue, int) or issue < 1:
            raise CommunityError(f"{where}: request.issue must be a positive issue number")
        by = request.get("by")
        if by is not None and (not isinstance(by, str) or not HANDLE.match(by.lower()) or len(by) > MAX_HANDLE_LEN):
            raise CommunityError(f"{where}: request.by must be a GitHub login")
    return meta


def load_community_pack(pack_dir: Path) -> Dict[str, Any]:
    """Validate the pack (schema-1) and its sidecar; return {'manifest', 'meta'}."""
    pack_dir = Path(pack_dir)
    manifest = packlib.load_pack(pack_dir)  # full schema-1 validation
    validate_community_id(manifest["id"])
    sidecar = meta_path_for(pack_dir)
    if sidecar.is_symlink() or not sidecar.is_file():
        raise CommunityError(
            f"{pack_dir.name}: missing sidecar {sidecar.name} (author/gallery metadata)"
        )
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CommunityError(f"{sidecar.name}: not valid JSON ({error})")
    validate_meta(meta, manifest["id"], sidecar.name)
    return {"manifest": manifest, "meta": meta}


def iter_pack_dirs(packs_dir: Path) -> List[Path]:
    return sorted(p for p in Path(packs_dir).iterdir() if p.is_dir())


def validate_all(packs_dir: Path) -> List[Dict[str, Any]]:
    """Validate every pack and sidecar. Raises on the first failure in a dir;
    the caller decides whether to keep going. Returns loaded packs."""
    return [load_community_pack(d) for d in iter_pack_dirs(packs_dir)]


def build_community_index(packs_dir: Path, base_url: str, generated_at: str) -> Dict[str, Any]:
    """A schema-1 index entry per pack, each with a registry ``meta`` block
    the gallery renders. Deterministic bytes via packlib.canonical_json."""
    entries: List[Dict[str, Any]] = []
    for pack_dir in iter_pack_dirs(packs_dir):
        loaded = load_community_pack(pack_dir)
        manifest, meta = loaded["manifest"], loaded["meta"]
        archive = packlib.build_zip(pack_dir)
        if len(archive) > packlib.MAX_ARCHIVE_BYTES:
            raise CommunityError(f"{manifest['id']}: archive is larger than {packlib.MAX_ARCHIVE_BYTES} bytes")
        filename = f"{manifest['id']}-{manifest['version']}.zip"
        entry = {
            "id": manifest["id"],
            "version": manifest["version"],
            "min_app_version": manifest["min_app_version"],
            "kind": manifest["kind"],
            "name": manifest["name"],
            "description": manifest["description"],
            "tools": manifest["tools"],
            "item_count": len(manifest.get("items", [])),
            "url": f"{base_url.rstrip('/')}/{filename}",
            "sha256": packlib.sha256_hex(archive),
            "size": len(archive),
            "meta": meta,
        }
        # Prompt-pack items the gallery detail page lists (id/tool/title/tags only;
        # never the prompt body or its sha). Rule packs carry no items.
        if manifest["kind"] == "prompts":
            entry["items"] = [
                {
                    "id": item["id"],
                    "tool": item["tool"],
                    "title": item["title"],
                    **({"tags": item["tags"]} if item.get("tags") else {}),
                }
                for item in manifest.get("items", [])
            ]
        # License badge on the detail page, when the pack declares one.
        if isinstance(manifest.get("license"), dict) and manifest["license"].get("spdx"):
            entry["license"] = {"spdx": manifest["license"]["spdx"]}
        if manifest.get("opaque") is True:
            entry["opaque"] = True
        entries.append(entry)
    ids = [e["id"] for e in entries]
    if len(set(ids)) != len(ids):
        raise CommunityError("two packs share an id")
    return {"schema": packlib.SCHEMA, "generated_at": generated_at, "packs": entries}
