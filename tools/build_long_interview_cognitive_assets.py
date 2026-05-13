#!/usr/bin/env python3
"""Build cognitive-metabolism assets from structured long-interview data.

The design fixed here is intentionally not a "host personality agent".
It treats long interviews as:

1. content mines for knowledge increments,
2. mirrors for recognition shifts,
3. traces of interview-container craft,
4. sources for better future questions.
"""

from __future__ import annotations

import json
import re
import argparse
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from json_repair import repair_json
except Exception:  # pragma: no cover
    repair_json = None


ROOT = Path("data/zhangxiaojun-transcripts/structured")
OUT_DIR = ROOT / "synthesis"
SOURCE_JSON_DIR: Path | None = None
MODEL = "openrouter/openai/gpt-4.1-mini"
MATERIAL_NAME = "张小珺访谈"
HOST_NAME = "张小珺"
MATERIAL_ROLE = "内容矿源、访谈容器样本、自我对照材料"
COMPARISON_NOTES = """- 不准备做张小珺访谈 Agent。
- 感觉张小珺的问题不少并不是最想学的问题；相比之下，凉子的问题更能引导到更深的远方。
- 但非常佩服张小珺能让访谈持续几个小时，想研究她如何撑开长访谈。
- 罗永浩长访谈更多来自个人魅力，这是另一种机制。"""
CARDS_PER_EPISODE = 6


def build_design_md() -> str:
    return f"""# 长素材认知代谢设计 v0.1

## 核心定位

本协议用于处理长访谈、长播客、长课程、长对谈等高密度素材。目标不是做主持人人格 Agent，也不是普通摘要，而是把长素材转成 Terry 可反复调用的认知扩展工具。

这里的“认知”同时包含两层：

- **知识**：事实、机制、案例、行业经验、术语、具体做法。
- **认识**：理解方式、判断框架、价值排序、问题感、世界观、自我校准。

因此，每条可吸收内容都要同时追问：

1. 它新增了什么知识？
2. 它修正了什么认识？
3. 它会如何改变下一次判断、提问、写作或行动？

## 当前素材的角色

{MATERIAL_NAME} 目前不默认做“主持人/被访者人格 Agent”。它在本轮里的角色是：

- **内容矿源**：长时间素材让强嘉宾/讲述者泄露大量判断、经验和隐含模型。
- **容器样本**：研究素材如何让话题持续展开，而不是只评价单个问题是否最深。
- **自我对照材料**：用真实经验和长时间展开方式，照出 Terry 的知识缺口、认识缺口、提问缺口和耐心缺口。

当前素材定位：{MATERIAL_ROLE}

对照说明：
{COMPARISON_NOTES}

## 四类产物

1. **认知边界卡**：知识增量 + 认识修正 + 行动变化。
2. **访谈容器分析**：为什么这类长访谈能持续展开，哪些能力可学，哪些要谨慎模仿。
3. **问题深度框架**：区分事实问题、机制问题、张力问题、世界观问题、存在问题。
4. **长访谈挖掘协议**：以后处理凉子、罗永浩或其他长访谈时复用。

## 认知边界卡 Schema

每张卡必须包含：

- 标题
- 来源：BV号 + timestamp
- 访谈内容
- 知识增量
- 认识变化
- Terry 可能的原默认判断
- 指出的不足：知识不足 / 经验不足 / 模型不足 / 判断过粗 / 问题意识不足 / 耐心不足 / 世界观不足
- 可迁移模型
- 行动修正
- 复核状态

## 判断一条素材是否值得吸收

优先级从高到低：

1. 会改变 Terry 下一次判断的内容。
2. 能暴露 Terry 缺少的一手经验或行业内部机制。
3. 能把一个粗判断拆成更细的判断框架。
4. 能生成一个后续研究问题。
5. 能进入写作或产品判断。
6. 仅仅“有趣”但不会改变判断的内容，暂缓。

## 反模式

- 不把长访谈做成普通摘要。
- 不把主持人风格和嘉宾知识混在一起。
- 不把“认知”窄化成 mental model，忽略具体知识。
- 不追求全量卡片，优先可改变判断的卡片。
- 不急着做全量，先让 MVP 批次进入真实使用闭环。
"""


@dataclass
class EpisodeBundle:
    bvid: str
    title: str
    card: dict[str, Any]
    duration: str


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    candidates = [text]
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            pass
        if repair_json:
            try:
                repaired = repair_json(candidate, return_objects=True)
                if isinstance(repaired, dict):
                    return repaired
            except Exception:
                pass
    raise ValueError("No valid JSON object found")


def chat_markdown(prompt: str, max_tokens: int = 6000) -> str:
    from llm_router import call

    last_error: Exception | None = None
    for attempt in range(4):
        try:
            text, provider = call.chat(
                [
                    {"role": "system", "content": "你是 Terry 的中文知识代谢编辑器。只输出 Markdown，不要寒暄。"},
                    {"role": "user", "content": prompt},
                ],
                model=MODEL,
                max_tokens=max_tokens,
                timeout=240,
            )
            break
        except Exception as exc:
            last_error = exc
            time.sleep(3 + attempt * 5)
    else:
        raise RuntimeError(f"Markdown generation failed after retries: {last_error}") from last_error
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text + f"\n\n---\n\n生成信息：provider={provider}；generated_at={datetime.now().isoformat(timespec='seconds')}\n"


def chat_json(prompt: str, max_tokens: int = 5000) -> tuple[dict[str, Any], str]:
    from llm_router import call

    last_error: Exception | None = None
    for attempt in range(4):
        try:
            text, provider = call.chat(
                [
                    {"role": "system", "content": "你是 Terry 的认知边界卡抽取器。只输出严格 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                model=MODEL,
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                timeout=240,
            )
            break
        except Exception as exc:
            last_error = exc
            time.sleep(3 + attempt * 5)
    else:
        raise RuntimeError(f"JSON generation failed after retries: {last_error}") from last_error
    return extract_json_object(text), provider


def load_bundles() -> list[EpisodeBundle]:
    bundles: list[EpisodeBundle] = []
    source_json_dir = SOURCE_JSON_DIR or (ROOT.parent / "json")
    for path in sorted((ROOT / "episodes").glob("*.json")):
        card = read_json(path)
        bvid = card.get("bvid") or card.get("episode_id") or card.get("id") or path.stem
        matches = sorted(source_json_dir.glob(f"*{bvid}*.json"))
        duration = ""
        if matches:
            source = read_json(matches[0])
            duration = source.get("length", "")
        bundles.append(EpisodeBundle(bvid=bvid, title=card.get("title", path.stem), card=card, duration=duration))
    return bundles


def compact_episode_for_cards(bundle: EpisodeBundle) -> dict[str, Any]:
    card = bundle.card
    return {
        "bvid": bundle.bvid,
        "title": bundle.title,
        "duration": bundle.duration,
        "core_question": card.get("core_question"),
        "one_sentence_takeaway": card.get("one_sentence_takeaway"),
        "terry_relevance": card.get("terry_relevance", []),
        "key_claims": card.get("key_claims", []),
        "mental_models": card.get("mental_models", []),
        "decision_rules": card.get("decision_rules", []),
        "open_questions": card.get("open_questions", []),
        "writing_material": card.get("writing_material", []),
        "asr_caveats": card.get("asr_caveats", []),
    }


def cognitive_cards_prompt(bundle: EpisodeBundle) -> str:
    compact = compact_episode_for_cards(bundle)
    return f"""请基于下面这一集的结构化长素材卡，生成 {CARDS_PER_EPISODE} 张“认知边界卡”。

Terry 对“认知”的定义：
- 知识：事实、机制、案例、行业经验、术语、具体做法。
- 认识：理解方式、判断框架、价值排序、问题感、世界观、自我校准。

抽取目标：
- 不要做普通摘要。
- 优先找能扩展 Terry 知识边界或修正 Terry 认识边界的内容。
- 可以推测 Terry 的“可能默认判断”，但必须写成“可能”而非断言。
- 每张卡都要有来源，必须包含素材 ID 和 timestamp；timestamp 从输入条目里取。
- 不要输出空泛卡片，例如“AI很重要”“组织很重要”。

输出严格 JSON：
{{
  "episode": "{bundle.bvid}",
  "cards": [
    {{
      "title": "",
      "source": ["{bundle.bvid} [timestamp]"],
      "interview_observation": "访谈内容具体说了什么",
      "knowledge_increment": "新增了什么知识、事实、机制、经验或案例",
      "recognition_shift": "它如何修正认识、判断框架或问题感",
      "possible_old_default": "Terry 过去可能的默认判断，用'可能'表述",
      "insufficiency_type": "知识不足|经验不足|模型不足|判断过粗|问题意识不足|耐心不足|世界观不足",
      "transferable_model": "可迁移模型，一句话",
      "action_correction": "下一次判断、提问、写作或产品行动应该如何变化",
      "verification_status": "ASR需复核|观点需回看原片|可先使用但需标注来源"
    }}
  ]
}}

Episode JSON:
{json.dumps(compact, ensure_ascii=False)}
"""


def generate_cognitive_cards(bundles: list[EpisodeBundle]) -> list[dict[str, Any]]:
    all_cards: list[dict[str, Any]] = []
    providers: list[str] = []
    cache_dir = OUT_DIR / "_cognitive_card_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for bundle in bundles:
        cache_path = cache_dir / f"{bundle.bvid}.json"
        if cache_path.exists():
            cached = read_json(cache_path)
            data = cached.get("data", {})
            provider = cached.get("provider", "cache")
        else:
            data, provider = chat_json(cognitive_cards_prompt(bundle), max_tokens=6500)
            cache_path.write_text(
                json.dumps(
                    {
                        "bvid": bundle.bvid,
                        "title": bundle.title,
                        "provider": provider,
                        "generated_at": datetime.now().isoformat(timespec="seconds"),
                        "data": data,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        providers.append(f"{bundle.bvid}:{provider}")
        cards = data.get("cards", [])
        if not isinstance(cards, list) or len(cards) < 4:
            raise RuntimeError(f"Too few cognitive cards for {bundle.bvid}")
        for card in cards:
            if isinstance(card, dict):
                card["episode_bvid"] = bundle.bvid
                card["episode_title"] = bundle.title
                all_cards.append(card)
    render_cognitive_cards(all_cards, providers)
    return all_cards


def render_cognitive_cards(cards: list[dict[str, Any]], providers: list[str]) -> None:
    lines = [
        "# 长访谈认知边界卡 v0.1",
        "",
        "> 认知 = 知识 + 认识。本文件不是访谈摘要，而是用于照出 Terry 的知识缺口、认识修正、判断细化和行动变化。",
        "",
        "## 使用方式",
        "",
        "- 先看“知识增量”：我具体新增了什么事实、机制、经验？",
        "- 再看“认识变化”：它如何改变我的理解方式或判断框架？",
        "- 最后看“行动修正”：下一次做判断、提问、写作或产品设计时，我要怎么变？",
        "",
    ]
    allowed_types = {
        "知识不足",
        "经验不足",
        "模型不足",
        "判断过粗",
        "问题意识不足",
        "耐心不足",
        "世界观不足",
    }
    for idx, card in enumerate(cards, 1):
        insufficiency_type = card.get("insufficiency_type", "")
        if insufficiency_type not in allowed_types:
            if "世界观" in insufficiency_type:
                insufficiency_type = "世界观不足"
            elif "经验" in insufficiency_type:
                insufficiency_type = "经验不足"
            elif "知识" in insufficiency_type:
                insufficiency_type = "知识不足"
            elif "问题" in insufficiency_type:
                insufficiency_type = "问题意识不足"
            elif "耐心" in insufficiency_type:
                insufficiency_type = "耐心不足"
            elif "模型" in insufficiency_type or "认知" in insufficiency_type or "认识" in insufficiency_type:
                insufficiency_type = "模型不足"
            else:
                insufficiency_type = "判断过粗"
        lines.extend(
            [
                f"## CB-{idx:03d} {card.get('title', '')}",
                "",
                f"- 来源：{'; '.join(card.get('source', []) or [])}",
                f"- 集数：{card.get('episode_title', '')}",
                f"- 不足类型：{insufficiency_type}",
                f"- 复核状态：{card.get('verification_status', '')}",
                "",
                "**访谈内容**",
                "",
                card.get("interview_observation", ""),
                "",
                "**知识增量**",
                "",
                card.get("knowledge_increment", ""),
                "",
                "**认识变化**",
                "",
                card.get("recognition_shift", ""),
                "",
                "**Terry 可能的原默认判断**",
                "",
                card.get("possible_old_default", ""),
                "",
                "**可迁移模型**",
                "",
                card.get("transferable_model", ""),
                "",
                "**行动修正**",
                "",
                card.get("action_correction", ""),
                "",
            ]
        )
    lines.extend(
        [
            "---",
            "",
            "生成信息：",
            f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
            f"- providers: {', '.join(providers)}",
        ]
    )
    (OUT_DIR / "cognitive_boundary_cards.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_other_assets(bundles: list[EpisodeBundle], cognitive_cards: list[dict[str, Any]]) -> None:
    synthesis = (OUT_DIR / "agent.md").read_text(encoding="utf-8") if (OUT_DIR / "agent.md").exists() else ""
    compact_index = [
        {
            "bvid": b.bvid,
            "title": b.title,
            "duration": b.duration,
            "core_question": b.card.get("core_question"),
            "takeaway": b.card.get("one_sentence_takeaway"),
        }
        for b in bundles
    ]
    cards_brief = [
        {
            "title": c.get("title"),
            "source": c.get("source"),
            "knowledge_increment": c.get("knowledge_increment"),
            "recognition_shift": c.get("recognition_shift"),
            "insufficiency_type": c.get("insufficiency_type"),
            "action_correction": c.get("action_correction"),
        }
        for c in cognitive_cards
    ]

    container_prompt = f"""请生成 Markdown 文件《长素材容器分析：{MATERIAL_NAME} v0.1》。

素材定位：
{MATERIAL_ROLE}

用户判断/对照说明：
{COMPARISON_NOTES}

请基于输入材料谨慎分析，不要神化 {HOST_NAME}。要明确证据边界：当前结构化数据主要来自内容产物，不一定有逐句主持人问题标注，因此容器分析多半是从长素材产物和内容展开方式做出的推断。

必须包含：
1. 结论摘要
2. 证据边界
3. {HOST_NAME} 或该素材可学的“容器能力”
4. 她的问题局限，以及为什么仍然能产出高价值材料
5. 与对照对象的能力分型
6. Terry 可以如何练习长访谈/深聊/客户访谈能力
7. 不该模仿的部分

Episode index:
{json.dumps(compact_index, ensure_ascii=False)}

当前 synthesis:
{synthesis[:16000]}
"""
    (OUT_DIR / "interview_container_analysis.md").write_text(chat_markdown(container_prompt, 5500), encoding="utf-8")

    question_prompt = f"""请生成 Markdown 文件《问题深度框架 v0.1》。

背景：
- Terry 要用这套框架比较不同长访谈/播客/对谈中的提问质量、容器能力和人格魅力。
- 本轮素材：{MATERIAL_NAME}。
- 对照说明：{COMPARISON_NOTES}

要求：
- 不依赖外部事实，只建立可操作框架。
- 区分“问题深度”和“访谈容器”。
- 给出 Level 1-7 的问题深度分层。
- 每层给定义、典型句式、适用场景、误用风险。
- 增加一个“远方问题”的定义：能把人从事实带到机制、张力、价值、命运、世界观的问题。
- 最后给 Terry 的练习法：如何把一个浅问题连续改写成深问题。
"""
    (OUT_DIR / "question_depth_framework.md").write_text(chat_markdown(question_prompt, 5000), encoding="utf-8")

    protocol_prompt = f"""请生成 Markdown 文件《长访谈/播客挖掘协议 v0.1》。

这是后续处理凉子、罗永浩、张小珺、播客、课程或其他长素材的固定协议。必须把“认知=知识+认识”写入协议。

必须包含：
1. 输入素材要求
2. 处理阶段：raw transcript -> episode card -> cognitive boundary cards -> container/question analysis -> synthesis
3. 每阶段产物 schema
4. 如何区分内容矿源、访谈容器、提问力、人格魅力
5. 如何对照 Terry 自己：知识缺口、认识缺口、经验缺口、提问缺口、耐心缺口
6. 质量门槛：来源、timestamp、ASR复核、不要空泛总结
7. 何时适合做 Agent，何时不适合做 Agent
8. 下一轮处理新访谈/播客时的具体执行步骤

注意：
- 不要编造固定 ASR 数值阈值；只要求抽样检查和人工复核。
- Agent 部分要区分：做“被访者/主持人人格 Agent”和做“素材检索/分析工具”是两件不同的事。

可参考这些认知边界卡摘要：
{json.dumps(cards_brief[:20], ensure_ascii=False)}
"""
    (OUT_DIR / "long_interview_mining_protocol.md").write_text(chat_markdown(protocol_prompt, 6000), encoding="utf-8")


def main() -> int:
    global ROOT, OUT_DIR, SOURCE_JSON_DIR, MODEL, MATERIAL_NAME, HOST_NAME, MATERIAL_ROLE, COMPARISON_NOTES, CARDS_PER_EPISODE

    parser = argparse.ArgumentParser(description="Build reusable cognitive-metabolism assets from structured long-form material.")
    parser.add_argument("--root", default=str(ROOT), help="structured data root containing episodes/*.json")
    parser.add_argument("--output-dir", default="", help="output synthesis dir; defaults to ROOT/synthesis")
    parser.add_argument("--source-json-dir", default="", help="optional raw transcript JSON dir for duration lookup")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--material-name", default=MATERIAL_NAME, help="e.g. 张小珺访谈 / 凉子访谈 / 罗永浩长谈 / 某播客")
    parser.add_argument("--host-name", default=HOST_NAME, help="host/person/show name used in container analysis")
    parser.add_argument("--material-role", default=MATERIAL_ROLE)
    parser.add_argument("--comparison-notes", default=COMPARISON_NOTES)
    parser.add_argument("--cards-per-episode", type=int, default=CARDS_PER_EPISODE)
    args = parser.parse_args()

    ROOT = Path(args.root).expanduser().resolve()
    OUT_DIR = Path(args.output_dir).expanduser().resolve() if args.output_dir else ROOT / "synthesis"
    SOURCE_JSON_DIR = Path(args.source_json_dir).expanduser().resolve() if args.source_json_dir else None
    MODEL = args.model
    MATERIAL_NAME = args.material_name
    HOST_NAME = args.host_name
    MATERIAL_ROLE = args.material_role
    COMPARISON_NOTES = args.comparison_notes
    CARDS_PER_EPISODE = args.cards_per_episode

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "material_processing_design.md").write_text(build_design_md() + "\n", encoding="utf-8")
    bundles = load_bundles()
    cognitive_cards = generate_cognitive_cards(bundles)
    generate_other_assets(bundles, cognitive_cards)
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL,
        "material_name": MATERIAL_NAME,
        "host_name": HOST_NAME,
        "root": str(ROOT),
        "output_files": [
            str(OUT_DIR / "material_processing_design.md"),
            str(OUT_DIR / "cognitive_boundary_cards.md"),
            str(OUT_DIR / "interview_container_analysis.md"),
            str(OUT_DIR / "question_depth_framework.md"),
            str(OUT_DIR / "long_interview_mining_protocol.md"),
        ],
        "episode_count": len(bundles),
        "cognitive_card_count": len(cognitive_cards),
    }
    (OUT_DIR / "_cognitive_assets_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
