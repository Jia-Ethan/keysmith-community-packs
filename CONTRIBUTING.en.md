# Contributing a community pack

> 中文：[CONTRIBUTING.md](CONTRIBUTING.md)

A community pack is a set of **content** — prompts, or input-replacement rules —
for the coding agents Keysmith supports (Codex, Claude, Grok, ZCode, pi, DSH).
It uses the **same format** (schema 1) as the official Keysmith Switch
extension packs, so a pack you make here is already in the shape the App can
consume later.

**Packs contain data only, no executable code.** The validator rejects any file
that the manifest does not list.

## One-minute start

1. Copy the example pack `packs/example.hello/` and its sidecar `packs/example.hello.meta.json`.
2. Rename the directory to your `<handle>.<slug>` (e.g. `alice.codex-review`) and set `id` in `pack.json` to the same value.
3. Write your prompt text under `prompts/*.md`; update `name` / `description` / `items` in `pack.json`.
4. Update each prompt file's `sha256` (command below).
5. Fill in the sidecar `packs/<id>.meta.json` (author, gallery copy).
6. Validate locally, then open a PR.

```bash
# compute a sha256
python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" packs/<id>/prompts/your-file.md
# validate (must be all ok)
python3 scripts/check.py
```

## Naming

- Pack id is **`<handle>.<slug>`**, where `handle` is your GitHub-style handle (lowercase, digits, hyphens).
- The directory name must **equal** `id` in `pack.json`.
- The `keysmith.` prefix is the official namespace and is **reserved** — CI rejects it for community packs.

## The sidecar `packs/<id>.meta.json`

The pack format has no "author" field, so author and gallery data live in a
sidecar named after the pack. It sits **next to** the pack directory, not inside
it (the validator forbids files a pack.json doesn't list).

```jsonc
{
  "author": { "handle": "alice", "name": "Alice", "url": "https://github.com/alice" },
  "summary": { "zh-CN": "给 Codex 做代码审查的提示词", "en": "A code-review prompt for Codex" },
  "category": "code-review",
  "source_url": "https://...",
  "submitted_at": "2026-11-01"
}
```

- `author.handle` **must** match the first segment of the pack id.
- `summary` needs at least one of zh-CN / en, each ≤ 280 chars (this is the gallery card blurb; more conversational than `description`).
- `category` / `source_url` / `submitted_at` are optional.

## License

Every pack must declare a `license` in `pack.json` (`"license": { "spdx": "MIT" }`;
MIT or CC-BY-4.0 recommended). Opening a PR means: **the content is yours or you
have the right to redistribute it, and you grant permission to display and
redistribute it in the Keysmith gallery and App**; you keep your copyright.

## Format details

Full rules in the [SPEC (schema 1)](docs/SPEC-community.md). Highlights:

- Prompt files are UTF-8, non-empty, ≤ 256 KiB each, ≤ 4 MiB per pack.
- No symlinks, no files outside the manifest, no `..` in paths.
- `version` is x.y.z; a merged `id`+`version` is immutable — bump the version to change content.

## Review

A maintainer **reviews content by hand** before merging — CI's green check means
the format is fine, not that the pack is accepted. See what review looks at in
[docs/review-checklist.md](docs/review-checklist.md).
