# 新素材处理 Runbook

适用于下一批长访谈、长播客、长课程、长对谈或直播回放。

## 0. 先判断素材角色

处理前先给素材定角色，不要直接开跑。

| 角色 | 关注点 | 输出侧重 |
| --- | --- | --- |
| 内容矿源 | 嘉宾或讲者输出了什么知识、判断、案例 | claims、models、decision rules |
| 访谈容器样本 | 主持人如何撑开长时间对话 | container analysis |
| 提问力样本 | 问题如何把人带向更深处 | question depth framework |
| 人格魅力样本 | 表达、叙事、节奏如何维持注意力 | narrative / delivery analysis |
| 自我对照材料 | 它照出了 Terry 哪些缺口 | cognitive boundary cards |

一批素材可以有多重角色，但分析时要分层。

## 1. 建目录

推荐：

```text
data/<material-slug>/
  _index.json
  json/
  structured/
    episodes/
    episodes_md/
    synthesis/
```

命名建议：

- `material-slug` 用英文、数字、短横线。
- 不把人名、节目名和平台都混进目录名。
- 公开仓库里不要放完整转写，除非确认权利边界。

## 2. 抽取 transcript

如果来自 B 站，可参考现有脚本改造成新的来源列表：

```bash
python tools/zhangxiaojun_bilibili_transcripts.py --all-videos
```

后续应把这个脚本泛化为：

```bash
python tools/extract_transcripts.py \
  --source bilibili \
  --space-url "<space or playlist url>" \
  --output data/<material-slug>
```

质量门槛：

- 每个 transcript JSON 必须有 `title`、`url`、`length`、`segments`。
- ASR 模型、字幕来源和生成时间要保留。
- 不把 ASR 当最终事实，后续引用必须能回到 timestamp。

## 3. 生成结构化层

当前命令：

```bash
python tools/zhangxiaojun_knowledge_extract.py \
  --input-dir data/<material-slug> \
  --output-dir data/<material-slug>/structured \
  --bvids all \
  --workers 4
```

输出：

- `structured/episodes/*.json`
- `structured/episodes_md/*.md`
- `structured/claims.jsonl`
- `structured/mental_models.jsonl`
- `structured/decision_rules.jsonl`
- `structured/questions.jsonl`
- `structured/entities.jsonl`
- `structured/writing_material.jsonl`

质量门槛：

- chunk 输出必须是严格 JSON。
- episode fold 只生成小 meta，具体条目本地聚合。
- 失败项进入 `failures/`，不要静默跳过。
- 对重要人物名、公司名、论文名保留 ASR caveat。

## 4. 生成认知代谢层

```bash
python tools/build_long_interview_cognitive_assets.py \
  --root data/<material-slug>/structured \
  --source-json-dir data/<material-slug>/json \
  --material-name "<素材名>" \
  --host-name "<主持人或节目名>" \
  --material-role "<内容矿源 / 提问力样本 / 访谈容器样本 / 人格魅力样本 / 自我对照材料>" \
  --comparison-notes "<与既有样本的对照>" \
  --cards-per-episode 6
```

输出：

- `material_processing_design.md`
- `cognitive_boundary_cards.md`
- `interview_container_analysis.md`
- `question_depth_framework.md`
- `long_interview_mining_protocol.md`
- `agent.md`
- `_cognitive_assets_manifest.json`

## 5. 生成 HTML 工作台

```bash
python tools/build_cognitive_html_viewer.py \
  --synthesis-dir data/<material-slug>/structured/synthesis \
  --title "<素材名>认知代谢工作台"
```

HTML 是首选阅读界面，Markdown 是源文件。

## 6. 人工使用闭环

跑完不代表完成。真正的完成是至少筛一遍认知卡。

建议流程：

1. 打开 `index.html`。
2. 按不足类型筛选。
3. 标出 `hit` 卡：真正击中 Terry 认知边界的内容。
4. 回原视频 timestamp 复核高价值卡。
5. 把复核后的卡送入 Wiki / Obsidian / 写作系统 / 项目判断。
6. 判断是否值得进一步做 Skill 或 Agent。

## 7. 是否做 Agent

不默认做 Agent。

适合做 Agent 的条件：

- 对象有稳定问题风格或判断框架。
- Terry 未来会反复调用它。
- 有足够材料支持行为模式蒸馏。
- 目标是可交互能力，而不是一次性总结。

不适合做 Agent 时，优先沉淀成：

- checklist
- protocol
- HTML workbench
- searchable dataset
- cognitive card deck
- writing angle bank

## 8. 发布边界

公开发布默认只放：

- 来源索引。
- sanitized episode cards。
- sanitized JSONL。
- synthesis 文档。
- HTML 工作台。
- 工具脚本。
- 协议文档。

默认不放：

- 完整字幕。
- 逐字稿。
- SRT。
- ASR segment JSON。
- chunk 缓存。
- 音视频文件。
