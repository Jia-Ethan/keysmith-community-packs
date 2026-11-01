# Contributing a community pack

> 中文：[CONTRIBUTING.md](CONTRIBUTING.md)

> Don't code? [File a request](docs/requests.en.md). Looking for something to build? Comment `/claim` on one in the [request pool](https://github.com/Jia-Ethan/keysmith-community-packs/issues?q=is%3Aissue+is%3Aopen+label%3Aready).

A community pack is a set of **content** — prompts, input-replacement rules, or
agent components (skills, slash commands, subagents) — for the coding agents Keysmith supports (Codex, Claude, Grok, ZCode, pi, DSH).
It uses the **same format** (schema 1) as the official Keysmith Switch
extension packs, so a pack you make here is already in the shape the App can
consume later.

**Packs contain data only, no executable code.** The validator rejects any file
that the manifest does not list.

> Tier 2 (things that run code: hooks, MCP, plugins…) is not accepted yet. If you want one, [file a request](docs/requests.en.md) first.

## One-minute start

1. Copy the example pack `packs/example.hello/` and its sidecar `packs/example.hello.meta.json`.
2. Rename the directory to your `<handle>.<slug>` (e.g. `alice.codex-review`) and set `id` in `pack.json` to the same value.
3. Write your prompt text under `prompts/*.md`; update `name` / `description` / `items` in `pack.json`.
4. Fill in the `sha256`s: run `python3 scripts/seal.py packs/<id>`; it computes them and writes them back into `pack.json`.
5. Fill in the sidecar `packs/<id>.meta.json` (author, gallery copy).
6. Validate locally, then open a PR.

```bash
# fill in the sha256s and validate this pack
python3 scripts/seal.py packs/<id>
# validate everything (must be all ok)
python3 scripts/check.py
```

## Harness packs (skills, commands, subagents)

Besides prompts, you can make a **harness pack** (`kind: "harness"`): skills, slash commands, subagents or extra rule files that go straight into Claude Code, Codex or Grok Build. The demo is [`packs/jia.review-kit/`](packs/jia.review-kit/).

```
packs/<id>/
  pack.json                       kind: "harness", tier: 1, min_app_version: "0.9.0"
  components/<id>/SKILL.md        a skill (plus a few more .md files if you like)
  components/<id>.md              a command, subagent or rule: one file per component
```

Highlights (full rules in the official SPEC §2.2):

- **Tier 1 only: nothing runs when it is installed.** `.md` files only.
- **Frontmatter is an allowlist.** Skills: `name`, `description`. Commands: `description`, `argument-hint`. Subagents: `name`, `description`. Rules: no frontmatter. `allowed-tools`, `hooks`, `model`, `tools`, `mcpServers`, `permissionMode` and the rest are rejected.
- No `` !`command` `` or ```` ```! ```` blocks in the text (Claude Code runs them as shell), and no `@~/` or `@/` references to files outside the project.
- **Names must not clash with another pack.** Skills and commands are both called as `/name`, so they share one namespace. CI checks every merged pack; if yours clashes, pick another name. Names starting with `ks-` or `keysmith`, and the agents' built-in command names, are taken.
- Codex has no slash commands or rule files, so leave `codex` out of those components' `tools`.

Apps before 0.9.0 cannot install harness packs; the gallery shows the manual install steps.

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
- If the pack answers a [request](docs/requests.en.md), add `"request": { "issue": 12, "by": "the-requester" }` so the gallery credits both of you, and put `Closes #12` in the PR description.

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
