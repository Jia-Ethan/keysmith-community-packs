# Keysmith 社区包

> English: [README.en.md](README.en.md) · 格式：[docs/SPEC-community.md](docs/SPEC-community.md) · 投稿：[CONTRIBUTING.md](CONTRIBUTING.md)

社区做的**提示词包**和**输入替换规则包**，给 Keysmith 支持的编程 Agent 用：Codex、Claude、Grok、ZCode、pi、DSH。

和 [Keysmith Switch](https://github.com/Jia-Ethan/keysmith-switch) 官方拓展包**同一套格式**（schema 1），所以你在这里做的包将来 App 也能直接认。**包里只有数据，没有可执行代码。**

## 怎么用（现阶段）

社区包暂时还不在 App 里一键安装（那是后续阶段）。现在：

1. 在[画廊](https://keysmithswitch.com/)（上线后）或本仓库 `packs/` 里浏览。
2. 把提示词正文复制进 Keysmith Switch 的"我的提示词"，或下载这个包。

## 投稿一个包

照着示范包 `packs/example.hello/` 抄，本地跑 `python3 scripts/check.py` 全绿后开 PR。完整步骤见 [CONTRIBUTING.md](CONTRIBUTING.md)。

- 包 id 形如 `<你的handle>.<slug>`；`keysmith.` 开头是官方保留的。
- 每个包配一个边车 `packs/<id>.meta.json`（作者 + 画廊文案）。
- 维护者会**人工审核内容**后再合并；CI 只检查格式。

## 本仓库是什么

```
packs/<id>/            一个社区包（schema 1，纯内容）
packs/<id>.meta.json   该包的边车：作者、画廊文案、分类
scripts/packlib.py     官方校验器（vendored，勿改）
scripts/check.py       本地/CI 校验
scripts/build_index.py 生成 community-index.json 给画廊
community-index.json   构建产物，官网画廊读它
docs/                  格式说明、审核清单
```

## 相关项目

- [Keysmith Switch](https://github.com/Jia-Ethan/keysmith-switch) — 统一管理各 Agent 指令的桌面端
- [codex-keysmith](https://github.com/Jia-Ethan/codex-keysmith) · [claude-keysmith](https://github.com/Jia-Ethan/claude-keysmith) · [grok-keysmith](https://github.com/Jia-Ethan/grok-keysmith) · [zcode-keysmith](https://github.com/Jia-Ethan/zcode-keysmith) · [pi-keysmith](https://github.com/Jia-Ethan/pi-keysmith) · [dsh-keysmith](https://github.com/Jia-Ethan/dsh-keysmith)

喜欢这些项目的话，点个 star，也欢迎来投稿你的包。
