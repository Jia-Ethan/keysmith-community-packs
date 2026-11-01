# 社区包格式（schema 1 + 社区约束）

社区包**就是** Keysmith Switch 的 schema 1 拓展包，外加一层社区注册约束。包的格式规则以官方 SPEC 为准，本文件只写社区仓库**额外**的部分。

- 包格式权威来源：官方仓库 `Jia-Ethan/keysmith-switch-extensions` 的 `SPEC.md`。
- 校验器：本仓库 `scripts/packlib.py`，从官方仓库**原样 vendored**。不要在这里改它；官方更新了就重新 vendored 一份。

## 与官方包的三点不同

### 1. 命名空间

- 包 id 形如 `<handle>.<slug>`，至少含一个 `.`。
- id 第一段（`handle`）是 GitHub 用户名风格标识：小写字母、数字、单连字符，最长 39。
- `keysmith.` 开头保留给官方，社区包不能用。

### 2. 边车 `packs/<id>.meta.json`

每个包在包目录**旁边**有一个同名边车，装包格式没有的注册信息。放在目录外是因为 `packlib.load_pack` 不允许包目录里有清单外的文件——包目录保持纯 schema 1，App 将来能原样消费；注册信息只活在本仓库。

| 字段 | 规则 |
| --- | --- |
| `author.handle` | 必填，GitHub 风格 handle，且**必须等于**包 id 第一段 |
| `author.name` | 可选，非空字符串 |
| `author.url` | 可选，http(s) URL |
| `summary` | 必填，对象，键为 `zh-CN`/`zh-TW`/`en`，至少一种，单条 ≤ 280 字符 |
| `category` | 可选，短小写 slug（≤ 32） |
| `source_url` | 可选，http(s) URL |
| `submitted_at` | 可选，`YYYY-MM-DD` |
| `request` | 可选，`{ "issue": <正整数>, "by": "<GitHub 用户名>" }`：这个包回应的需求编号和提需求的人，画廊用来同时署名；`by` 可省略 |

除以上字段外的键一律拒绝。

### 3. 画廊索引 `community-index.json`

`scripts/build_index.py` 为每个包生成一条 schema 1 索引条目，并挂上该包的 `meta` 块给画廊用。写出是确定性的（键排序、两空格缩进、末尾换行），同样的包产出同样的字节。阶段 0 还没有发布，所以 `url` 用 `--base-url` 的占位前缀；有了正式发布地址再指过去。

## 不变的部分（强调）

- **只含数据，无可执行代码。** 校验器拒绝清单外的任何文件、符号链接、`..` 路径。
- 提示词文件 UTF-8、非空、≤ 256 KiB；整包 ≤ 4 MiB；zip ≤ 2 MiB。
- 已存在的 `id`+`version` 内容不可变；要改就升 `version`。
- 规则包（`kind: "rules"`）规则同官方 SPEC §2.1；本仓库同样支持，但同样要带边车。
