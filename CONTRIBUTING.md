# 贡献一个社区包

> English: [CONTRIBUTING.en.md](CONTRIBUTING.en.md)

> 不会写代码？可以[提需求](docs/requests.md)；想找点事做？去[需求池](https://github.com/Jia-Ethan/keysmith-community-packs/issues?q=is%3Aissue+is%3Aopen+label%3Aready)评论 `/claim` 领一个。

社区包是一组**内容**——提示词或输入替换规则——给 Keysmith 支持的编程 Agent 用（Codex、Claude、Grok、ZCode、pi、DSH）。它和 Keysmith Switch 官方拓展包**用同一套格式**（schema 1），所以你做的包将来 App 也能直接认。

**包里没有可执行代码，只有数据。** 校验器会拒绝任何对不上清单的文件。

## 一分钟上手

1. 复制示范包 `packs/example.hello/` 和它的边车 `packs/example.hello.meta.json`。
2. 改目录名为你的 `<handle>.<slug>`（例如 `alice.codex-review`），并把 `pack.json` 里的 `id` 改成同样的值。
3. 写你的提示词正文到 `prompts/*.md`，更新 `pack.json` 里的 `name` / `description` / `items`。
4. 更新每个提示词文件的 `sha256`（下面有命令）。
5. 填好边车 `packs/<id>.meta.json`（作者、画廊文案）。
6. 本地校验，然后开 PR。

```bash
# 填 sha256
python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" packs/<id>/prompts/你的文件.md
# 校验（必须全 ok）
python3 scripts/check.py
```

## 命名规则

- 包 id 形如 **`<handle>.<slug>`**，`handle` 是你的 GitHub 用户名风格标识（小写、数字、连字符）。
- 目录名必须**等于** `pack.json` 里的 `id`。
- `keysmith.` 开头是官方命名空间，**保留**，社区包不能用——CI 会直接拒。

## 边车 `packs/<id>.meta.json`

包格式本身没有"作者"字段，所以作者和画廊展示信息放在**同名边车**里（它在包目录**旁边**，不在里面——校验器不允许包目录里有清单外的文件）。

```jsonc
{
  "author": { "handle": "alice", "name": "Alice", "url": "https://github.com/alice" },
  "summary": { "zh-CN": "给 Codex 做代码审查的提示词", "en": "A code-review prompt for Codex" },
  "category": "code-review",
  "source_url": "https://...",
  "submitted_at": "2026-11-01"
}
```

- `author.handle` **必须**和包 id 的第一段一致。
- `summary` 至少填中文或英文，单条不超过 280 字符（这是画廊卡片文案，比 `description` 更口语）。
- `category` / `source_url` / `submitted_at` 可选。
- 如果这个包是在做某个[需求](docs/requests.md)，加上 `"request": { "issue": 12, "by": "提需求的人" }`，画廊会同时署名；PR 描述里写 `Closes #12`。

## license

每个包都要在 `pack.json` 里声明 `license`（`"license": { "spdx": "MIT" }`，推荐 MIT 或 CC-BY-4.0）。开 PR 即表示：**内容是你原创或你有权再分发，并授予在 Keysmith 画廊与 App 内展示、再分发的许可**；你保留版权。

## 格式细节

完整规则见官方 [SPEC（schema 1）](docs/SPEC-community.md)。要点：

- 提示词文件 UTF-8、非空，单个 ≤ 256 KiB，整个包 ≤ 4 MiB。
- 不允许符号链接，不允许清单外的文件，路径不能含 `..`。
- `version` 三段式；已合并的 `id`+`version` 内容不可改，要改就升版本号。

## 审核

维护者会**人工审核内容**后再合并——CI 的绿勾只代表格式没问题，不代表会被接受。审核看什么见 [docs/review-checklist.md](docs/review-checklist.md)。
