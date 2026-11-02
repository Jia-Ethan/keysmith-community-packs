# Vendored verbatim from Jia-Ethan/keysmith-switch-extensions scripts/packlib.py
# (schema 1). DO NOT EDIT HERE. Re-vendor from the official repo when it changes.
# Community packs use the exact same format so the App can consume them later unchanged.

"""Validation and deterministic packaging for Keysmith Switch extension packs.

Standard library only, so CI and contributors need nothing installed. The rules
here are the ones SPEC.md states; the app enforces the same rules again when it
installs a pack, because where a pack came from says nothing about whether it is
well formed.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = 1
TOOLS = ("claude", "codex", "grok", "zcode", "pi", "dsh")
REWRITE_TOOLS = ("claude", "codex", "grok", "zcode")
KINDS = ("prompts", "rules", "harness")
RULES_FILE = "rules.json"
# The first app version that understands rule packs (for Codex only).
RULES_MIN_APP = (0, 4, 0)
# The first app version that rewrites for agents other than Codex. A rule pack whose tools
# are anything but exactly ["codex"] needs it; App 0.4.0 does not list such a pack.
RULES_ANY_AGENT_MIN_APP = (0, 5, 0)
# The first app version that keeps opaque rule text off the interface. Older apps list the pack
# as needing a newer app and do not install it.
RULES_OPAQUE_MIN_APP = (0, 6, 5)
# First app versions that list these agents. Older apps drop the unknown tool name.
PI_MIN_APP = (0, 7, 0)
DSH_MIN_APP = (0, 8, 1)
MAX_RULES = 1000
MAX_FROM_CHARS = 200
MAX_TO_CHARS = 2000
LOCALES = ("zh-CN", "zh-TW", "en")
MAX_ITEMS = 200
MAX_FILE_BYTES = 256 * 1024
MAX_PACK_BYTES = 4 * 1024 * 1024  # all files of a pack together, unpacked
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024  # the .zip itself
MAX_TAGS = 8
MAX_TAG_LEN = 24

# Harness packs (SPEC §2.2): agent components (skills, slash commands, subagents, rule files)
# that the app writes into each agent's own directories. Tier 1 only: nothing in them runs code.
HARNESS_MIN_APP = (0, 9, 0)
HARNESS_TOOLS = ("claude", "codex", "grok")
HARNESS_TIERS = (1,)
COMPONENT_TYPES = ("skill", "command", "agent", "rule")
# The agents each component type has a place on. A component cannot name an agent that has
# nowhere to put it (Codex has no slash commands or rule files).
COMPONENT_TOOLS = {
    "skill": ("claude", "codex", "grok"),
    "command": ("claude", "grok"),
    "agent": ("claude", "codex", "grok"),
    "rule": ("claude", "grok"),
}
# Skills and commands are both invoked as /name, so they share one namespace.
COMPONENT_NAMESPACE = {"skill": "invocable", "command": "invocable", "agent": "agent", "rule": "rule"}
# Frontmatter is an allowlist. Anything else (allowed-tools, hooks, model, mcpServers,
# permissionMode, ...) widens what the agent may do, so a tier-1 pack cannot carry it.
FRONTMATTER_KEYS = {
    "skill": ("name", "description"),
    "command": ("description", "argument-hint"),
    "agent": ("name", "description"),
    "rule": (),
}
FRONTMATTER_REQUIRED = {"skill": ("name", "description"), "command": (), "agent": ("name", "description"), "rule": ()}
MAX_COMPONENTS = 50
MAX_SKILL_FILES = 20
MAX_COMPONENT_NAME = 40
MAX_FRONTMATTER_VALUE = 1024
COMPONENT_KEYS = {"id", "type", "name", "tools", "title", "files"}
# Names beginning with these are kept for official packs (ids starting with "keysmith.").
RESERVED_NAME_PREFIXES = ("ks-", "keysmith")
OFFICIAL_ID_PREFIX = "keysmith."
# Names the supported agents already use. A skill or command by one of these names would be
# shadowed by, or shadow, the agent's own slash command; a subagent would collide with a
# built-in subagent. Fixed for schema 1: a name an agent adds later is the app's install-time
# conflict check, not a format change, so a published pack never turns invalid.
RESERVED_INVOCABLE_NAMES = frozenset({
    "add-dir", "agents", "approvals", "bug", "clear", "compact", "config", "context", "cost",
    "diff", "doctor", "exit", "export", "fast", "feedback", "fork", "help", "hooks", "ide", "init",
    "login", "logout", "mcp", "memory", "mention", "model", "new", "output-style", "permissions",
    "plan", "plugin", "plugins", "pr-comments", "prompts", "quit", "release-notes", "resume",
    "review", "rewind", "sandbox", "security-review", "settings", "skills", "status",
    "statusline", "theme", "todos", "undo", "upgrade", "usage", "vim",
    # Skills Claude Code ships with, invoked the same way.
    "batch", "claude-api", "code-review", "debug", "fewer-permission-prompts", "keybindings-help",
    "loop", "run", "simplify", "update-config",
})
RESERVED_AGENT_NAMES = frozenset({"default", "explore", "explorer", "general-purpose", "plan", "statusline-setup", "worker"})

PACK_ID = re.compile(r"^[a-z0-9]+([.-][a-z0-9]+)*$")
ITEM_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
COMPONENT_NAME = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
# One segment of a file path inside a harness pack. ASCII only: APFS and NTFS ignore case, and
# APFS also folds Unicode (`ſ` onto `s`, `K` onto `K`, NFD onto NFC), so two names that look
# different could be one file on disk and the second written would replace the first.
COMPONENT_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,63}$")
# Names Windows reserves for devices: `aux.md` there is the AUX device, not a file.
WINDOWS_DEVICE_NAMES = frozenset(
    ["con", "prn", "aux", "nul"] + [f"com{i}" for i in range(1, 10)] + [f"lpt{i}" for i in range(1, 10)]
)
FRONTMATTER_LINE = re.compile(r"^([a-z][a-z0-9-]*):(?: +(.*))?$")
# Plain scalars YAML reads as something other than a string (booleans, null, numbers, dates).
YAML_NOT_A_STRING = re.compile(
    r"^(?:true|false|yes|no|on|off|y|n|null|~|[-+]?0[xob][0-9a-f_]+|[-+]?\.?[0-9][0-9_.:e+-]*|[-+]?\.inf|\.nan)$",
    re.IGNORECASE,
)
# `!` followed by a backtick, or a fence whose info string starts with `!`: Claude Code runs
# these as shell commands when the skill or command is invoked. That is code, so not tier 1.
SHELL_INJECTION = re.compile(r"!`|^[ \t]*(?:`{3,}|~{3,})[ \t]*!", re.MULTILINE)
# `@~/...`, `@/...`, `@$HOME`, `@../`: pulls a file from outside the project into the context.
OUTSIDE_FILE_REFERENCE = re.compile(r"(?:^|[\s(\[])@(?:[~/$]|\.\.)", re.MULTILINE)
# Characters that hide or reorder text, so a reviewer would not see what the model sees:
# bidirectional controls, zero-width space and word joiner, byte order mark, Unicode tags.
HIDDEN_CHARACTERS = re.compile("[\u061c\u200b\u200e\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\U000e0000-\U000e007f]")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")

ZIP_TIME = (1980, 1, 1, 0, 0, 0)


class PackError(ValueError):
    """A pack that breaks the format. The message names the pack and the rule."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    """Stable bytes: sorted keys, two-space indent, trailing newline."""
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def semver_tuple(version: str) -> tuple:
    match = SEMVER.match(version)
    if not match:
        raise PackError(f"not a plain x.y.z version: {version!r}")
    return tuple(int(part) for part in match.groups())


def safe_relative_path(path: str) -> str:
    """A forward-slash path inside the pack: no absolute paths, no `..`, no odd segments."""
    if not isinstance(path, str) or not path or "\\" in path or "\x00" in path:
        raise PackError(f"unsafe path: {path!r}")
    posix = PurePosixPath(path)
    if posix.is_absolute() or any(part in ("", ".", "..") for part in posix.parts) or str(posix) != path:
        raise PackError(f"unsafe path: {path!r}")
    return path


def _localized(value: Any, label: str, where: str) -> Dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise PackError(f"{where}: {label} must be an object with at least one language")
    for key, text in value.items():
        if key not in LOCALES:
            raise PackError(f"{where}: {label} has an unknown language {key!r}")
        if not isinstance(text, str) or not text.strip():
            raise PackError(f"{where}: {label}[{key}] must be a non-empty string")
    return value


def validate_manifest(manifest: Any, where: str = "pack.json") -> Dict[str, Any]:
    if not isinstance(manifest, dict):
        raise PackError(f"{where}: must be a JSON object")
    if manifest.get("schema") != SCHEMA:
        raise PackError(f"{where}: schema must be {SCHEMA}")
    pack_id = manifest.get("id")
    if not isinstance(pack_id, str) or not PACK_ID.match(pack_id) or len(pack_id) > 64:
        raise PackError(f"{where}: id must be lowercase letters, digits, dots and hyphens (max 64)")
    semver_tuple(str(manifest.get("version")))
    semver_tuple(str(manifest.get("min_app_version")))
    if manifest.get("kind") not in KINDS:
        raise PackError(f"{where}: kind must be one of {list(KINDS)}")
    if "opaque" in manifest and manifest["kind"] != "rules":
        raise PackError(f"{where}: opaque is only for rule packs")
    _localized(manifest.get("name"), "name", where)
    _localized(manifest.get("description"), "description", where)
    tools = manifest.get("tools")
    if not isinstance(tools, list) or not tools or len(set(tools)) != len(tools) or any(t not in TOOLS for t in tools):
        raise PackError(f"{where}: tools must be a non-empty list of unique names from {list(TOOLS)}")
    have = semver_tuple(str(manifest.get("min_app_version")))
    if "pi" in tools and have < PI_MIN_APP:
        raise PackError(f"{where}: a pack whose tools include 'pi' needs min_app_version 0.7.0")
    if "dsh" in tools and have < DSH_MIN_APP:
        raise PackError(f"{where}: a pack whose tools include 'dsh' needs min_app_version 0.8.1")
    if manifest["kind"] == "rules":
        return _validate_rules_manifest(manifest, tools, where)
    if manifest["kind"] == "harness":
        return _validate_harness_manifest(manifest, tools, where)
    if "tier" in manifest or "components" in manifest:
        raise PackError(f"{where}: tier and components are only for harness packs")
    items = manifest.get("items")
    if not isinstance(items, list) or not items or len(items) > MAX_ITEMS:
        raise PackError(f"{where}: items must be a list of 1 to {MAX_ITEMS} entries")
    seen = set()
    files = set()
    for index, item in enumerate(items):
        label = f"{where}: items[{index}]"
        if not isinstance(item, dict):
            raise PackError(f"{label} must be an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not ITEM_ID.match(item_id) or len(item_id) > 64:
            raise PackError(f"{label}: id must be lowercase letters, digits and hyphens (max 64)")
        if item_id in seen:
            raise PackError(f"{label}: duplicate id {item_id!r}")
        seen.add(item_id)
        if item.get("tool") not in tools:
            raise PackError(f"{label}: tool must be one of this pack's tools")
        _localized(item.get("title"), "title", label)
        tags = item.get("tags", [])
        if (
            not isinstance(tags, list)
            or len(tags) > MAX_TAGS
            or any(not isinstance(tag, str) or not tag.strip() or len(tag) > MAX_TAG_LEN for tag in tags)
        ):
            raise PackError(f"{label}: tags must be at most {MAX_TAGS} short non-empty strings")
        path = safe_relative_path(item.get("file"))
        if not path.startswith("prompts/") or not path.endswith(".md"):
            raise PackError(f"{label}: file must be a .md file under prompts/")
        if path in files:
            raise PackError(f"{label}: file {path!r} is used twice")
        files.add(path)
        if not isinstance(item.get("sha256"), str) or not SHA256.match(item["sha256"]):
            raise PackError(f"{label}: sha256 must be 64 lowercase hex characters")
    return manifest


def _validate_rules_manifest(manifest: Dict[str, Any], tools: List[str], where: str) -> Dict[str, Any]:
    if any(tool not in REWRITE_TOOLS for tool in tools):
        raise PackError(
            f"{where}: rule pack tools must be rewrite agents {list(REWRITE_TOOLS)}"
        )
    needs = RULES_MIN_APP if tools == ["codex"] else RULES_ANY_AGENT_MIN_APP
    opaque = manifest.get("opaque", False)
    if not isinstance(opaque, bool):
        raise PackError(f"{where}: opaque must be a boolean")
    if opaque:
        needs = max(needs, RULES_OPAQUE_MIN_APP)
    if semver_tuple(manifest["min_app_version"]) < needs:
        if opaque:
            what = "an opaque rule pack"
        elif tools == ["codex"]:
            what = "a rule pack"
        else:
            what = "a rule pack for agents other than codex"
        raise PackError(f"{where}: {what} needs min_app_version {'.'.join(map(str, needs))} or later")
    if "items" in manifest:
        raise PackError(f"{where}: a rule pack has no items")
    if "tier" in manifest or "components" in manifest:
        raise PackError(f"{where}: tier and components are only for harness packs")
    rules = manifest.get("rules")
    if not isinstance(rules, dict) or set(rules) != {"file", "sha256"}:
        raise PackError(f"{where}: rules must be an object with file and sha256")
    if rules["file"] != RULES_FILE:
        raise PackError(f"{where}: rules.file must be {RULES_FILE!r}")
    if not isinstance(rules["sha256"], str) or not SHA256.match(rules["sha256"]):
        raise PackError(f"{where}: rules.sha256 must be 64 lowercase hex characters")
    return manifest


def _validate_harness_manifest(manifest: Dict[str, Any], tools: List[str], where: str) -> Dict[str, Any]:
    if any(tool not in HARNESS_TOOLS for tool in tools):
        raise PackError(f"{where}: harness pack tools must be from {list(HARNESS_TOOLS)}")
    if semver_tuple(manifest["min_app_version"]) < HARNESS_MIN_APP:
        raise PackError(f"{where}: a harness pack needs min_app_version {'.'.join(map(str, HARNESS_MIN_APP))} or later")
    for key in ("items", "rules"):
        if key in manifest:
            raise PackError(f"{where}: a harness pack has no {key}")
    tier = manifest.get("tier")
    if isinstance(tier, bool) or tier not in HARNESS_TIERS:
        raise PackError(f"{where}: tier must be 1 (tier 2, components that run code, is not in the format yet)")
    components = manifest.get("components")
    if not isinstance(components, list) or not components or len(components) > MAX_COMPONENTS:
        raise PackError(f"{where}: components must be a list of 1 to {MAX_COMPONENTS} entries")
    official = manifest["id"].startswith(OFFICIAL_ID_PREFIX)
    ids = set()
    names = set()
    paths = set()
    folded = set()
    covered = set()
    for index, component in enumerate(components):
        label = f"{where}: components[{index}]"
        if not isinstance(component, dict):
            raise PackError(f"{label} must be an object")
        extra = set(component) - COMPONENT_KEYS
        if extra:
            raise PackError(f"{label}: unknown keys {sorted(extra)}")
        component_id = component.get("id")
        if not isinstance(component_id, str) or not ITEM_ID.match(component_id) or len(component_id) > 64:
            raise PackError(f"{label}: id must be lowercase letters, digits and hyphens (max 64)")
        if component_id in ids:
            raise PackError(f"{label}: duplicate id {component_id!r}")
        ids.add(component_id)
        kind = component.get("type")
        if kind not in COMPONENT_TYPES:
            raise PackError(f"{label}: type must be one of {list(COMPONENT_TYPES)}")
        name = component.get("name")
        if (
            not isinstance(name, str)
            or not COMPONENT_NAME.match(name)
            or len(name) > MAX_COMPONENT_NAME
            or name in WINDOWS_DEVICE_NAMES
        ):
            raise PackError(
                f"{label}: name must start with a letter and be lowercase letters, digits and hyphens (max {MAX_COMPONENT_NAME})"
            )
        if not official and name.startswith(RESERVED_NAME_PREFIXES):
            raise PackError(f"{label}: names starting with 'ks-' or 'keysmith' are kept for official packs")
        namespace = COMPONENT_NAMESPACE[kind]
        if namespace == "invocable" and name in RESERVED_INVOCABLE_NAMES:
            raise PackError(f"{label}: /{name} is a built-in command of a supported agent")
        if namespace == "agent" and name in RESERVED_AGENT_NAMES:
            raise PackError(f"{label}: {name!r} is a built-in subagent of a supported agent")
        if (namespace, name) in names:
            raise PackError(f"{label}: another component already uses the name {name!r}")
        names.add((namespace, name))
        component_tools = component.get("tools")
        if (
            not isinstance(component_tools, list)
            or not component_tools
            or len(set(component_tools)) != len(component_tools)
            or any(tool not in tools for tool in component_tools)
        ):
            raise PackError(f"{label}: tools must be a non-empty list of unique names from this pack's tools")
        unsupported = [tool for tool in component_tools if tool not in COMPONENT_TOOLS[kind]]
        if unsupported:
            raise PackError(f"{label}: a {kind} has nowhere to go on {unsupported}")
        covered.update(component_tools)
        _localized(component.get("title"), "title", label)
        files = component.get("files")
        if not isinstance(files, list) or not files:
            raise PackError(f"{label}: files must be a non-empty list")
        for position, entry in enumerate(files):
            at = f"{label}.files[{position}]"
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
                raise PackError(f"{at}: must be an object with only path and sha256")
            path = safe_relative_path(entry["path"])
            if not path.endswith(".md"):
                raise PackError(f"{at}: only .md files are allowed")
            for segment in path.split("/"):
                if (
                    not COMPONENT_PATH_SEGMENT.match(segment)
                    or segment.endswith(".")
                    or segment.split(".")[0].lower() in WINDOWS_DEVICE_NAMES
                ):
                    raise PackError(
                        f"{at}: file names use ASCII letters, digits, '.', '_' and '-' only ({segment!r})"
                    )
            if path in paths or path.lower() in folded:
                raise PackError(f"{at}: file {path!r} is used twice")
            paths.add(path)
            folded.add(path.lower())
            if not isinstance(entry["sha256"], str) or not SHA256.match(entry["sha256"]):
                raise PackError(f"{at}: sha256 must be 64 lowercase hex characters")
        listed = [entry["path"] for entry in files]
        if kind == "skill":
            root = f"components/{component_id}/"
            if len(files) > MAX_SKILL_FILES:
                raise PackError(f"{label}: a skill has at most {MAX_SKILL_FILES} files")
            if any(not path.startswith(root) for path in listed):
                raise PackError(f"{label}: a skill's files must be under {root}")
            if root + "SKILL.md" not in listed:
                raise PackError(f"{label}: a skill needs {root}SKILL.md")
            nested = [p for p in listed if p != root + "SKILL.md" and PurePosixPath(p).name.casefold() == "skill.md"]
            if nested:
                raise PackError(f"{label}: only the skill's top-level SKILL.md may be named SKILL.md ({nested[0]})")
        else:
            expected = f"components/{component_id}.md"
            if listed != [expected]:
                raise PackError(f"{label}: a {kind} is exactly one file, {expected}")
    if covered != set(tools):
        missing = sorted(set(tools) - covered)
        raise PackError(f"{where}: no component is for {missing}; drop them from tools or add a component")
    if len(paths) > MAX_ITEMS:
        raise PackError(f"{where}: a harness pack has at most {MAX_ITEMS} files")
    return manifest


def manifest_files(manifest: Dict[str, Any]) -> List[str]:
    """The files a pack's manifest lists, besides pack.json."""
    if manifest["kind"] == "rules":
        return [manifest["rules"]["file"]]
    if manifest["kind"] == "harness":
        return sorted(entry["path"] for component in manifest["components"] for entry in component["files"])
    return sorted(item["file"] for item in manifest["items"])


def harness_files(manifest: Dict[str, Any]) -> List[Tuple[Dict[str, Any], Dict[str, str]]]:
    """Every (component, file entry) of a harness pack, in manifest order."""
    return [(component, entry) for component in manifest["components"] for entry in component["files"]]


def component_summary(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """What an index entry lists about a harness pack's components (never file contents)."""
    return [
        {
            "id": component["id"],
            "type": component["type"],
            "name": component["name"],
            "tools": component["tools"],
            "title": component["title"],
        }
        for component in manifest["components"]
    ]


def _is_control(char: str) -> bool:
    # Mirrors Rust's char::is_control: the Cc category.
    code = ord(char)
    return code < 0x20 or 0x7F <= code <= 0x9F


def check_rules_bytes(data: bytes, label: str) -> List[Dict[str, str]]:
    """The rules file: {"rules": [{"from", "to"}]}, checked the way the app checks rules people type."""
    if len(data) > MAX_FILE_BYTES:
        raise PackError(f"{label}: file is larger than {MAX_FILE_BYTES} bytes")
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackError(f"{label}: not valid UTF-8 JSON ({error})")
    if not isinstance(value, dict) or set(value) != {"rules"}:
        raise PackError(f"{label}: must be an object with only a rules list")
    rules = value["rules"]
    if not isinstance(rules, list) or not rules or len(rules) > MAX_RULES:
        raise PackError(f"{label}: rules must be a list of 1 to {MAX_RULES} entries")
    seen = set()
    for index, rule in enumerate(rules):
        where = f"{label}: rules[{index}]"
        if not isinstance(rule, dict) or set(rule) != {"from", "to"}:
            raise PackError(f"{where}: must be an object with only from and to")
        source, target = rule["from"], rule["to"]
        if not isinstance(source, str) or not isinstance(target, str):
            raise PackError(f"{where}: from and to must be strings")
        if not source:
            raise PackError(f"{where}: from must not be empty")
        if len(source) > MAX_FROM_CHARS:
            raise PackError(f"{where}: from is longer than {MAX_FROM_CHARS} characters")
        if len(target) > MAX_TO_CHARS:
            raise PackError(f"{where}: to is longer than {MAX_TO_CHARS} characters")
        if any(_is_control(char) for char in source):
            raise PackError(f"{where}: from contains a control character")
        if source in seen:
            raise PackError(f"{where}: duplicate from {source!r}")
        seen.add(source)
    return rules


def _check_prompt_bytes(data: bytes, label: str) -> None:
    if not data.strip():
        raise PackError(f"{label}: file is empty")
    if len(data) > MAX_FILE_BYTES:
        raise PackError(f"{label}: file is larger than {MAX_FILE_BYTES} bytes")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise PackError(f"{label}: file is not UTF-8")


def _harness_text(data: bytes, label: str) -> str:
    if not data.strip():
        raise PackError(f"{label}: file is empty")
    if len(data) > MAX_FILE_BYTES:
        raise PackError(f"{label}: file is larger than {MAX_FILE_BYTES} bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise PackError(f"{label}: file is not UTF-8")
    if "\r" in text:
        raise PackError(f"{label}: use LF line endings (found a carriage return)")
    bad = next((char for char in text if char != "\t" and char != "\n" and _is_control(char)), None)
    if bad is not None:
        raise PackError(f"{label}: contains the control character U+{ord(bad):04X}")
    hidden = HIDDEN_CHARACTERS.search(text)
    if hidden:
        raise PackError(f"{label}: contains the invisible character U+{ord(hidden.group()):04X}")
    if SHELL_INJECTION.search(text):
        raise PackError(f"{label}: !`command` and ```! blocks run shell commands; not allowed in a tier-1 pack")
    if OUTSIDE_FILE_REFERENCE.search(text):
        raise PackError(f"{label}: @ file references outside the project (@~/, @/, @$, @..) are not allowed")
    return text


def split_frontmatter(text: str, label: str) -> Tuple[Optional[Dict[str, str]], str]:
    """A strict frontmatter subset: `---`, then one `key: value` per line, then `---`.

    Values are single-line plain or quoted scalars. Anything YAML would read differently
    from how it looks (lists, maps, block scalars, tags, anchors, comments) is rejected,
    so what a reviewer sees is what the agent parses.
    """
    lines = text.split("\n")
    if lines[0].rstrip(" \t") != "---":
        return None, text
    if lines[0] != "---":
        raise PackError(f"{label}: the opening --- must be alone on its line")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i] == "---")
    except StopIteration:
        raise PackError(f"{label}: frontmatter is not closed with ---")
    fields: Dict[str, str] = {}
    for number, line in enumerate(lines[1:end], start=2):
        at = f"{label}: frontmatter line {number}"
        if not line.strip():
            continue
        match = FRONTMATTER_LINE.match(line)
        if not match:
            raise PackError(f"{at}: must be `key: value` on one line")
        key, raw = match.group(1), (match.group(2) or "").strip()
        if key in fields:
            raise PackError(f"{at}: duplicate key {key!r}")
        if not raw:
            raise PackError(f"{at}: {key} needs a value on the same line")
        if raw[0] in "\"'":
            quote = raw[0]
            if len(raw) < 2 or raw[-1] != quote or quote in raw[1:-1] or (quote == '"' and "\\" in raw):
                raise PackError(f"{at}: a quoted value must be one plain {quote}...{quote} string")
            value = raw[1:-1]
        else:
            if (
                raw[0] in "[]{}|>&*!%@`#,?:-\"'"
                or ": " in raw
                or " #" in raw
                or raw.endswith(":")
                or YAML_NOT_A_STRING.match(raw)
            ):
                raise PackError(f"{at}: put the value of {key} in double quotes")
            value = raw
        if not value.strip():
            raise PackError(f"{at}: {key} must not be empty")
        if len(value) > MAX_FRONTMATTER_VALUE:
            raise PackError(f"{at}: {key} is longer than {MAX_FRONTMATTER_VALUE} characters")
        fields[key] = value
    return fields, "\n".join(lines[end + 1:])


def check_component_bytes(data: bytes, component: Dict[str, Any], path: str, label: str) -> None:
    """One harness file, checked the way the app checks it before writing it anywhere."""
    text = _harness_text(data, label)
    kind = component["type"]
    primary = path == f"components/{component['id']}/SKILL.md" if kind == "skill" else True
    if not primary:
        # A skill's supporting file: read on demand, never parsed for metadata.
        return
    fields, body = split_frontmatter(text, label)
    if not body.strip():
        raise PackError(f"{label}: has no instructions after the frontmatter")
    allowed = FRONTMATTER_KEYS[kind]
    if fields is None:
        if FRONTMATTER_REQUIRED[kind]:
            raise PackError(f"{label}: a {kind} needs frontmatter with {list(FRONTMATTER_REQUIRED[kind])}")
        return
    if not allowed:
        raise PackError(f"{label}: a {kind} file has no frontmatter")
    extra = sorted(set(fields) - set(allowed))
    if extra:
        raise PackError(f"{label}: frontmatter key(s) {extra} are not allowed for a {kind} (allowed: {list(allowed)})")
    missing = [key for key in FRONTMATTER_REQUIRED[kind] if key not in fields]
    if missing:
        raise PackError(f"{label}: frontmatter is missing {missing}")
    if "name" in fields and fields["name"] != component["name"]:
        raise PackError(f"{label}: frontmatter name {fields['name']!r} must equal the component name {component['name']!r}")
    if kind == "agent" and "codex" in component["tools"] and "\'\'\'" in body:
        raise PackError(f"{label}: a Codex subagent's instructions cannot contain three single quotes in a row")


def load_pack(directory: Path) -> Dict[str, Any]:
    """Validate a pack directory and return its manifest. Every file must be accounted for."""
    directory = Path(directory)
    manifest_path = directory / "pack.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PackError(f"{directory.name}: pack.json is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackError(f"{directory.name}/pack.json: not valid JSON ({error})")
    validate_manifest(manifest, f"{directory.name}/pack.json")
    if manifest["id"] != directory.name:
        raise PackError(f"{directory.name}: directory name must equal the pack id {manifest['id']!r}")
    listed = set()
    total = 0
    if manifest["kind"] == "rules":
        name = manifest["rules"]["file"]
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise PackError(f"{directory.name}: {name} is missing or not a regular file")
        data = path.read_bytes()
        check_rules_bytes(data, f"{directory.name}/{name}")
        if sha256_hex(data) != manifest["rules"]["sha256"]:
            raise PackError(f"{directory.name}/{name}: sha256 does not match pack.json")
        listed.add(name)
    for item in manifest.get("items", []):
        path = directory / item["file"]
        if path.is_symlink() or not path.is_file():
            raise PackError(f"{directory.name}: {item['file']} is missing or not a regular file")
        data = path.read_bytes()
        _check_prompt_bytes(data, f"{directory.name}/{item['file']}")
        if sha256_hex(data) != item["sha256"]:
            raise PackError(f"{directory.name}/{item['file']}: sha256 does not match pack.json")
        listed.add(item["file"])
        total += len(data)
    if manifest["kind"] == "harness":
        for component, entry in harness_files(manifest):
            path = directory / entry["path"]
            if path.is_symlink() or not path.is_file():
                raise PackError(f"{directory.name}: {entry['path']} is missing or not a regular file")
            data = path.read_bytes()
            check_component_bytes(data, component, entry["path"], f"{directory.name}/{entry['path']}")
            if sha256_hex(data) != entry["sha256"]:
                raise PackError(f"{directory.name}/{entry['path']}: sha256 does not match pack.json")
            listed.add(entry["path"])
            total += len(data)
    if total > MAX_PACK_BYTES:
        raise PackError(f"{directory.name}: files add up to more than {MAX_PACK_BYTES} bytes")
    for found in sorted(directory.rglob("*")):
        relative = found.relative_to(directory).as_posix()
        if found.is_symlink():
            raise PackError(f"{directory.name}: symlinks are not allowed ({relative})")
        if found.is_dir() or relative == "pack.json":
            continue
        if relative not in listed:
            raise PackError(f"{directory.name}: {relative} is not listed in pack.json")
    return manifest


def build_zip(directory: Path) -> bytes:
    """A deterministic archive: same pack, same bytes, so hashes are reproducible."""
    directory = Path(directory)
    manifest = load_pack(directory)
    names = ["pack.json"] + manifest_files(manifest)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, (directory / name).read_bytes())
    return buffer.getvalue()


def check_zip(data: bytes, expected: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """What the app does on install: open the archive, distrust every name, re-check every rule."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise PackError(f"archive is not a zip file ({error})")
    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(set(names)) != len(names):
            raise PackError("archive has duplicate entries")
        for info in infos:
            safe_relative_path(info.filename)
            if info.is_dir() or (info.external_attr >> 28) == 0xA:
                raise PackError(f"archive entry {info.filename!r} is a directory or a link")
            if info.file_size > MAX_FILE_BYTES:
                raise PackError(f"archive entry {info.filename!r} is too large")
        if "pack.json" not in names:
            raise PackError("archive has no pack.json")
        try:
            manifest = json.loads(archive.read("pack.json").decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PackError(f"pack.json is not valid JSON ({error})")
        validate_manifest(manifest, "pack.json")
        listed = set(manifest_files(manifest))
        if set(names) != listed | {"pack.json"}:
            raise PackError("archive entries do not match pack.json")
        if manifest["kind"] == "rules":
            data_rules = archive.read(RULES_FILE)
            check_rules_bytes(data_rules, RULES_FILE)
            if sha256_hex(data_rules) != manifest["rules"]["sha256"]:
                raise PackError(f"{RULES_FILE}: sha256 does not match pack.json")
        for item in manifest.get("items", []):
            data_item = archive.read(item["file"])
            _check_prompt_bytes(data_item, item["file"])
            if sha256_hex(data_item) != item["sha256"]:
                raise PackError(f"{item['file']}: sha256 does not match pack.json")
        if manifest["kind"] == "harness":
            total = 0
            for component, entry in harness_files(manifest):
                data_file = archive.read(entry["path"])
                check_component_bytes(data_file, component, entry["path"], entry["path"])
                if sha256_hex(data_file) != entry["sha256"]:
                    raise PackError(f"{entry['path']}: sha256 does not match pack.json")
                total += len(data_file)
            if total > MAX_PACK_BYTES:
                raise PackError(f"files add up to more than {MAX_PACK_BYTES} bytes")
    if expected is not None:
        for key in ("id", "version", "kind"):
            if manifest[key] != expected.get(key):
                raise PackError(f"archive {key} {manifest[key]!r} differs from the index ({expected.get(key)!r})")
    return manifest


def build_index(packs_dir: Path, out_dir: Path, base_url: str, generated_at: str) -> Dict[str, Any]:
    """Write every pack archive and index.json into out_dir; return the index."""
    packs_dir, out_dir = Path(packs_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: List[Dict[str, Any]] = []
    for directory in sorted(p for p in packs_dir.iterdir() if p.is_dir()):
        manifest = load_pack(directory)
        archive = build_zip(directory)
        if len(archive) > MAX_ARCHIVE_BYTES:
            raise PackError(f"{manifest['id']}: archive is larger than {MAX_ARCHIVE_BYTES} bytes")
        filename = f"{manifest['id']}-{manifest['version']}.zip"
        (out_dir / filename).write_bytes(archive)
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
            "sha256": sha256_hex(archive),
            "size": len(archive),
        }
        if manifest["kind"] == "harness":
            entry["tier"] = manifest["tier"]
            entry["components"] = component_summary(manifest)
        if manifest.get("opaque") is True:
            entry["opaque"] = True
        entries.append(entry)
    ids = [entry["id"] for entry in entries]
    if len(set(ids)) != len(ids):
        raise PackError("two packs share an id")
    index = {"schema": SCHEMA, "generated_at": generated_at, "packs": entries}
    (out_dir / "index.json").write_bytes(canonical_json(index))
    return index


def verify_release(out_dir: Path) -> Dict[str, Any]:
    """Check a built directory the way a downloading app would."""
    out_dir = Path(out_dir)
    try:
        index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackError(f"index.json is unreadable ({error})")
    if index.get("schema") != SCHEMA or not isinstance(index.get("packs"), list):
        raise PackError("index.json has the wrong shape")
    for entry in index["packs"]:
        filename = entry["url"].rsplit("/", 1)[-1]
        safe_relative_path(filename)
        path = out_dir / filename
        if not path.is_file():
            raise PackError(f"{filename} is listed in the index but missing")
        data = path.read_bytes()
        if len(data) != entry["size"] or sha256_hex(data) != entry["sha256"]:
            raise PackError(f"{filename} does not match the size and sha256 in the index")
        check_zip(data, entry)
    return index
