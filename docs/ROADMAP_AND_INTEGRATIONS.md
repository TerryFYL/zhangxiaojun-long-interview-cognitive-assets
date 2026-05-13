# Roadmap And Integrations

这份路线图服务两个目标：

1. 下一批视频、播客、访谈能复用同一套认知卡片流程。
2. 后续想到的优化点和系统连接方式，有固定入口可以进入处理队列。

## 优先级

### P0: 让下一批素材能稳定复用

| 项目 | 价值 | 验收标准 |
| --- | --- | --- |
| 泛化 transcript 抽取器 | 不再把脚本绑定到张小珺 | 支持 `--source`、`--input-list`、`--output` |
| 泛化结构化抽取命令 | 新素材不需要改源码 | 支持任意 `data/<material-slug>/json` |
| 统一素材 manifest | 后续素材队列可管理 | 每批素材有 `_material.json` |
| 失败恢复机制 | 长任务不中断 | 单集失败可重跑，不影响全量 |

### P1: 让卡片进入真实使用闭环

| 项目 | 价值 | 验收标准 |
| --- | --- | --- |
| HTML 卡片标记 | 区分好看和真正有用 | 支持 `hit` / `actioned` / `needs_review` |
| 导出精选卡 | 能进入 Wiki/Obsidian | 一键导出 selected cards 为 Markdown/JSON |
| 原视频复核链接 | 降低复核成本 | timestamp 可跳到原视频或至少定位源 |
| 卡片评分 | 优先处理高价值内容 | 支持 impact / novelty / actionability |

### P2: 接入 Terry 的其他系统

| 系统 | 连接方式 | 目标 |
| --- | --- | --- |
| Wiki / Obsidian | 导出精选卡和母题映射 | 把被击中的卡纳入长期知识网络 |
| 飞书 | 完成通知、处理队列、优化 backlog | 从一次性脚本变成可运营流水线 |
| GitHub | sanitized release 自动化 | 每批公开材料可复现发布 |
| Skill 生态 | 固化成 `long-material-metabolism` skill | 下一次直接调用 skill 执行 |
| 内容生产系统 | 导出文章角度和问题清单 | 把认知卡转成写作和研究输入 |

## 建议的系统架构

```text
source material
  -> transcript extractor
  -> structured extractor
  -> cognitive asset builder
  -> HTML workbench
  -> human selection
  -> wiki / obsidian / feishu / github / skill
```

关键原则：

- 自动化负责全量处理。
- 人只负责判断哪些卡真正击中认知边界。
- 被击中的内容才进入长期知识系统。
- 优化点必须落到 backlog，并有验收标准。

## Backlog 入口

所有优化点都按这个模板写入 `docs/OPTIMIZATION_INBOX.md`：

```markdown
## OPT-YYYYMMDD-001 标题

- Status: proposed | accepted | doing | done | dropped
- Stage: transcript | structure | synthesis | html | integration | release
- Problem:
- Expected change:
- Acceptance check:
- Notes:
```

## 当前建议先做的 5 件事

1. 把 `zhangxiaojun_bilibili_transcripts.py` 泛化为素材无关的 `extract_transcripts.py`。
2. 给 HTML 工作台增加卡片标记和导出 selected cards。
3. 建立 `_material.json`，记录每批素材的角色、来源、版权边界、处理状态。
4. 写一个 `run_material_pipeline.py`，把 transcript -> structured -> synthesis -> html 串成单命令。
5. 做一个 Wiki/Obsidian 导出器，只导出人工选中的高价值卡。

## 不建议马上做的事

- 不急着把所有主持人都做成 Agent。
- 不急着把完整逐字稿公开。
- 不急着把所有卡都塞进 Wiki。
- 不急着做复杂数据库；当前文件系统 + JSONL 足够支撑下一轮。
- 不急着做全自动“认知吸收”，最后筛选仍需要 Terry 判断。
