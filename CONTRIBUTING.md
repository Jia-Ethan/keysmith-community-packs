# 贡献一个社区包

> English: [CONTRIBUTING.en.md](CONTRIBUTING.en.md)

> 不会写代码？可以[提需求](docs/requests.md)；想找点事做？去[需求池](https://keysmithswitch.com/requests/)评论 `/claim` 领一个。

社区包是一组**内容**——提示词、输入替换规则，或者 Agent 的组件（技能、斜杠命令、子 Agent）——给 Keysmith 支持的编程 Agent 用（Codex、Claude、Grok、ZCode、pi、DSH）。它和 Keysmith Switch 官方拓展包**用同一套格式**（schema 1），所以你做的包将来 App 也能直接认。

**包里没有可执行代码，只有数据。** 校验器会拒绝任何对不上清单的文件。

> 第 2 层（会运行代码的 hook、MCP、插件等）现在还不收，想要的话先[提需求](docs/requests.md)。

## 一分钟上手

1. 复制示范包 `packs/example.hello/` 和它的边车 `packs/example.hello.meta.json`。
2. 改目录名为你的 `<handle>.<slug>`（例如 `alice.codex-review`），并把 `pack.json` 里的 `id` 改成同样的值。
3. 写你的提示词正文到 `prompts/*.md`，更新 `pack.json` 里的 `name` / `description` / `items`。
4. 填 `sha256`：运行 `python3 scripts/seal.py packs/<id>`，它会算好并写回 `pack.json`。
5. 填好边车 `packs/<id>.meta.json`（作者、画廊文案）。
6. 本地校验，然后开 PR。

```bash
# 填 sha256 并校验这个包
python3 scripts/seal.py packs/<id>
# 校验全部（必须全 ok）
python3 scripts/check.py
```

## 组件包（技能、命令、子 Agent）

除了提示词，还可以做**组件包**（`kind: "harness"`）：直接给 Agent 加技能、斜杠命令、子 Agent 或附加规则，适用 Claude Code、Codex、Grok Build。示范包是 [`packs/jia.review-kit/`](packs/jia.review-kit/)。

```
packs/<id>/
  pack.json                       kind: "harness", tier: 1, min_app_version: "0.9.0"
  components/<id>/SKILL.md        技能（可以再放几个 .md）
  components/<id>.md              斜杠命令、子 Agent 或规则，一个组件一个文件
```

要点（完整规则见官方 SPEC §2.2）：

- **只收第 1 层：装上不运行任何代码。** 只能是 `.md` 文件。
- **frontmatter 是白名单。** 技能只能写 `name`、`description`；命令只能写 `description`、`argument-hint`；子 Agent 只能写 `name`、`description`；规则不写 frontmatter。`allowed-tools`、`hooks`、`model`、`tools`、`mcpServers`、`permissionMode` 等一律拒绝。
- 正文里不能有 `` !`命令` `` 或 ```` ```! ```` 代码块（Claude Code 会当 shell 执行），也不能用 `@~/`、`@/` 这类引用项目外的文件。
- **名字不能和别的包撞。** 技能和命令都用 `/名字` 调用，所以两者共用一个名字空间。CI 会检查所有已合并的包，撞了就换一个名字。`ks-`、`keysmith` 开头的名字和各家内置命令名不能用。
- Codex 没有斜杠命令和规则文件，这两种组件的 `tools` 不要写 `codex`。

App 0.9.0 之前装不了组件包，画廊会给出手动安装的步骤。

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
