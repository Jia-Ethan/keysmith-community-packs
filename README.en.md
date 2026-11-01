# Keysmith Community Packs

> 中文：[README.md](README.md) · Format: [docs/SPEC-community.md](docs/SPEC-community.md) · Contribute: [CONTRIBUTING.en.md](CONTRIBUTING.en.md)

Community-made **prompt packs** and **input-replacement rule packs** for the
coding agents Keysmith supports: Codex, Claude, Grok, ZCode, pi, DSH.

Same format (schema 1) as the official [Keysmith Switch](https://github.com/Jia-Ethan/keysmith-switch)
extension packs, so a pack you make here is already in the shape the App can
consume later. **Packs contain data only, no executable code.**

## Using a pack (for now)

Community packs aren't one-click installable in the App yet (that's a later
stage). For now:

1. Browse the [gallery](https://keysmithswitch.com/) (once live) or `packs/` here.
2. Copy the prompt text into Keysmith Switch's "my prompts", or download the pack.

## Contributing

Copy the example pack `packs/example.hello/`, run `python3 scripts/check.py`
until it's all green, and open a PR. Full steps in [CONTRIBUTING.en.md](CONTRIBUTING.en.md).

- Pack id is `<your-handle>.<slug>`; the `keysmith.` prefix is reserved for official packs.
- Each pack has a sidecar `packs/<id>.meta.json` (author + gallery copy).
- A maintainer **reviews content by hand** before merging; CI only checks format.

## What's in here

```
packs/<id>/            a community pack (schema 1, content only)
packs/<id>.meta.json   its sidecar: author, gallery copy, category
scripts/packlib.py     the official validator (vendored, do not edit)
scripts/check.py       local/CI validation
scripts/build_index.py builds community-index.json for the gallery
community-index.json   build artifact the website gallery reads
docs/                  format spec, review checklist
```

## Related projects

- [Keysmith Switch](https://github.com/Jia-Ethan/keysmith-switch) — desktop manager for agent instructions
- [codex-keysmith](https://github.com/Jia-Ethan/codex-keysmith) · [claude-keysmith](https://github.com/Jia-Ethan/claude-keysmith) · [grok-keysmith](https://github.com/Jia-Ethan/grok-keysmith) · [zcode-keysmith](https://github.com/Jia-Ethan/zcode-keysmith) · [pi-keysmith](https://github.com/Jia-Ethan/pi-keysmith) · [dsh-keysmith](https://github.com/Jia-Ethan/dsh-keysmith)

If these projects help you, star them — and come share a pack.
