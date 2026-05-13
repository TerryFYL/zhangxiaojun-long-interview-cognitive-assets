# Optimization Inbox

这里记录后续想到的优化点。每个优化点必须能落到流程、脚本、HTML、数据结构或系统连接，不保存纯感想。

## 模板

```markdown
## OPT-YYYYMMDD-001 标题

- Status: proposed
- Stage: transcript | structure | synthesis | html | integration | release
- Problem:
- Expected change:
- Acceptance check:
- Notes:
```

## OPT-20260513-001 泛化 transcript 抽取器

- Status: proposed
- Stage: transcript
- Problem: 当前 `zhangxiaojun_bilibili_transcripts.py` 绑定了张小珺视频列表，不适合下一批素材直接复用。
- Expected change: 新增素材无关的 `extract_transcripts.py`，支持 `--source bilibili`、`--input-list`、`--output`。
- Acceptance check: 给一份 BV 列表即可生成 `_index.json`、`json/`、`srt/`，不需要改源码。
- Notes: 保留 B站 cookie / official subtitle / whisper fallback 逻辑。

## OPT-20260513-002 统一素材 manifest

- Status: proposed
- Stage: structure
- Problem: 每批素材的角色、来源、处理边界、公开边界目前分散在文档和命令参数中。
- Expected change: 每批素材新增 `_material.json`。
- Acceptance check: pipeline 能从 `_material.json` 读取 material name、host name、role、comparison notes、source policy。
- Notes: 这会让飞书队列、GitHub release 和本地处理状态都更好接。

## OPT-20260513-003 HTML 工作台支持标记和导出

- Status: proposed
- Stage: html
- Problem: 当前 HTML 只能浏览和筛选，不能记录哪些卡真正击中 Terry，也不能导出精选卡。
- Expected change: 增加 `hit`、`actioned`、`needs_review` 标记，支持导出 selected cards 为 Markdown/JSON。
- Acceptance check: 在浏览器里标记后，可以下载一个 `selected_cards.md` 或 `selected_cards.json`。
- Notes: 静态 HTML 可先用 localStorage；后续再考虑文件回写。

## OPT-20260513-004 Wiki / Obsidian 导出器

- Status: proposed
- Stage: integration
- Problem: 认知卡生成后如果不进入长期知识系统，价值会停留在一次性浏览。
- Expected change: 新增导出器，把精选卡按母题、领域、缺口类型输出到 Wiki/Obsidian 可读 Markdown。
- Acceptance check: 输入 selected cards，输出包含 source、timestamp、知识增量、认识变化、行动修正的 Markdown 文件。
- Notes: 不要全量导入，只导入人工选中的卡。

## OPT-20260513-005 飞书队列和完成通知

- Status: proposed
- Stage: integration
- Problem: 长素材处理是长任务，后续批量跑时需要状态、失败、完成通知。
- Expected change: 接入飞书，维护素材队列和处理状态；完成后发通知。
- Acceptance check: 一批素材完成后，飞书里能看到素材名、状态、输出路径、失败数、HTML 链接。
- Notes: 先做通知，再考虑多维表格管理。

## OPT-20260513-006 Public release sanitizer 常规化

- Status: proposed
- Stage: release
- Problem: 公开发布需要稳定排除逐字稿、SRT、ASR segment、chunk 缓存和本地路径。
- Expected change: 把 `export_public_release.py` 泛化，适用于任意 material slug。
- Acceptance check: 任意素材都能生成 public-safe package，并通过敏感字段扫描。
- Notes: 继续保留 `NOTICE.md` 和 `DATA_LICENSE.md` 边界。
