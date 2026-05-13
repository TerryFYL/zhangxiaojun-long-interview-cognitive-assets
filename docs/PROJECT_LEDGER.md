# 项目总账

这个项目的价值不在于“张小珺这一批材料已经处理完”，而在于形成了一套可重复运行的长素材认知代谢流水线。

## 项目定位

把长访谈、长播客、长课程、长对谈从“信息消费材料”转成“可复用认知资产”。

核心产物不是摘要，而是：

- 认知边界卡：知识增量、认识变化、自我对照、行动修正。
- episode cards：单集结构化索引。
- JSONL evidence bank：claims、mental models、decision rules、questions、entities。
- HTML 工作台：用于搜索、筛选、浏览、复核。
- 处理协议：可迁移到其他视频、播客和访谈资料。

## 当前基线

- 素材来源：张小珺商业访谈录 B站空间。
- 视频数量：26。
- episode cards：26。
- cognitive boundary cards：156。
- claims：312。
- mental models：208。
- decision rules：156。
- questions：312。
- entities：4259。
- 展示层：静态 HTML 工作台。
- 发布边界：不公开完整逐字稿、SRT、ASR segment、chunk 缓存、音视频文件。

## 最值得沉淀的部分

### 1. 可执行流程

最重要的是把流程保成可运行脚本，而不是只写成方法论。

当前关键脚本：

- `tools/zhangxiaojun_bilibili_transcripts.py`
- `tools/zhangxiaojun_knowledge_extract.py`
- `tools/build_long_interview_cognitive_assets.py`
- `tools/build_cognitive_html_viewer.py`
- `tools/export_public_release.py`

后续优化应优先进入脚本、schema、HTML 控件或质量门槛，而不是散落在笔记里。

### 2. 数据结构和质量门槛

稳定结构比单次结果更重要。

应长期保留：

- episode JSON schema。
- cognitive boundary card schema。
- claims / mental_models / decision_rules / questions JSONL 格式。
- timestamp 复核要求。
- ASR caveat。
- “认知 = 知识 + 认识”的处理定义。

### 3. 关键工程决策

这些决策对后续复用影响很大：

- 长素材不要一次性 fold 成大 JSON；采用 chunk 严格 schema + episode 小 meta + 本地聚合。
- Markdown 作为源文件，HTML 作为首选阅读界面。
- 不默认把素材做成 Agent；先判断它是内容矿源、访谈容器样本、提问力样本还是人格魅力样本。
- 公开发布采用 sanitized release，完整转写默认只留本地。

### 4. 真实使用反馈

后续最有价值的不是“再多生成一些卡”，而是记录哪些卡真正改变了判断。

建议新增三个使用标记：

- `hit`: 真的击中 Terry 的知识或认识边界。
- `actioned`: 已进入下一次判断、提问、写作或产品动作。
- `needs_review`: 需要回到原视频或原文复核。

### 5. 系统连接点

这套流水线天然可以连接：

- Obsidian / Wiki：沉淀被击中的认知卡。
- 飞书：通知处理完成、沉淀待办、维护素材队列。
- GitHub：公开 sanitized 数据包和工具。
- Skill / Agent：当某类素材形成稳定能力后，再蒸馏为可运行 Skill 或 Agent。
- 内容生产系统：把认知卡转成文章角度、问题清单或研究选题。

## 不值得过度整理的部分

- 临时运行日志。
- chunk 缓存的全部细节。
- 未复核的逐字 evidence。
- 已经被脚本固化的重复说明。
- 只对张小珺这批素材有意义、无法迁移的手工步骤。

## 后续维护原则

每次处理新素材，只沉淀三类变化：

1. 流程变化：命令、脚本、schema、质量门槛发生改变。
2. 认知变化：某张卡或某个素材改变了 Terry 的判断。
3. 系统连接变化：接入了 Wiki、飞书、Obsidian、GitHub、Agent 或其他工具。

其他过程噪音不进入长期文档。
