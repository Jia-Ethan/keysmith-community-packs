<!-- 中文在上，English below. 保留你那部分即可。 -->

## 提交一个社区包 / Submitting a pack

**包 id / Pack id:** `<handle>.<slug>`

**回应的需求 / Request:** Closes #<!-- 编号，没有就删掉这行。写了才会挂到需求上，期限也会停 / number, or delete this line. This links the PR to the request and stops its deadline -->

### 自检清单 / Checklist

- [ ] 本地跑过 `python3 scripts/check.py`，全部 `ok` / Ran `python3 scripts/check.py` locally, all `ok`
- [ ] 目录名 = `pack.json` 的 `id`，且形如 `<我的handle>.<slug>` / Dir name equals `id`, shaped `<my-handle>.<slug>`
- [ ] 有同名边车 `packs/<id>.meta.json`，`author.handle` 与 id 第一段一致 / Sidecar present, handle matches
- [ ] `name` / `description` 至少填了中文或英文 / `name`/`description` has zh-CN and/or en
- [ ] 声明了 license（`pack.json` 的 `license.spdx`，推荐 MIT 或 CC-BY-4.0） / Declared a license
- [ ] 内容是我原创或我有权再分发 / Content is mine or I have the right to redistribute it
- [ ] 内容适合公开展示，不含越界/攻击性/违法内容 / Content is appropriate for a public gallery

### 这个包是做什么的 / What does it do

<!-- 一两句话 / One or two sentences -->

### 面向哪个工具 / Which tool(s)

<!-- codex / claude / grok / zcode / pi / dsh -->

---

维护者会人工审核内容后再合并。CI 只检查格式，绿勾不代表会被接受。
A maintainer reviews content by hand before merging. CI only checks format; a green check does not mean acceptance.
