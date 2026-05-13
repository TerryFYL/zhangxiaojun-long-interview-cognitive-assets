#!/usr/bin/env python3
"""Structured knowledge extraction for 张小珺商业访谈录 transcripts.

This script treats the generated transcripts as raw sources and produces a
small knowledge dataset:

- structured/episodes/*.json: one episode card per video
- structured/claims.jsonl
- structured/mental_models.jsonl
- structured/decision_rules.jsonl
- structured/questions.jsonl
- structured/entities.jsonl

The first pass is intentionally evidence-bound: every extracted item should
carry timestamps back to the transcript.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

try:
    from json_repair import repair_json
except Exception:  # pragma: no cover - optional local dependency
    repair_json = None


DEFAULT_BVIDS = [
    "BV1YR5E6EE9o",  # 姚顺宇
    "BV1iVoVBgERD",  # 罗福莉
    "BV1tew5zVEDf",  # 谢赛宁
    "BV1knvYBDEjs",  # Manus
    "BV1hFe1zSEXp",  # 杨植麟
]


SYSTEM_PROMPT = """你是 Terry 的知识代谢抽取器。目标不是写摘要，而是把访谈转成可复用知识资产。

硬规则：
1. 只基于给定片段抽取，不要补外部知识。
2. 所有 claim / model / rule / question 必须带 timestamp 证据。
3. 这是 ASR 字幕，可能有人名、英文、术语误识别；不确定时在 confidence 写 medium/low，并在 evidence_note 标明。
4. 避免空泛总结，优先抽取可迁移到 Terry 的 AI 科研军团、产品判断、投资观察、知识系统建设的内容。
5. 输出必须是严格 JSON，不要 Markdown，不要解释。
"""


CHUNK_USER_TEMPLATE = """请从下面这个访谈片段中抽取结构化信息。

Episode:
- bvid: {bvid}
- title: {title}
- chunk_id: {chunk_id}
- time_range: {time_range}

输出 JSON schema:
{{
  "chunk_id": "...",
  "time_range": "...",
  "local_summary": "这个片段真正讲了什么，120字以内",
  "high_value_segments": [
    {{
      "timestamp": "[H:MM:SS-H:MM:SS]",
      "topic": "...",
      "why_it_matters": "...",
      "evidence_note": "基于片段的简短证据"
    }}
  ],
  "claims": [
    {{
      "claim": "一个可复用判断，不要写成流水账",
      "speaker": "能判断则写，否则 unknown",
      "topic": "...",
      "evidence": "片段中支持该 claim 的内容，转述即可",
      "timestamp": "[...]",
      "confidence": "high|medium|low",
      "terry_relevance": "对 Terry 有什么用"
    }}
  ],
  "mental_models": [
    {{
      "name": "模型名，短语",
      "definition": "模型如何工作",
      "source_observation": "来自片段的观察",
      "timestamp": "[...]",
      "where_it_applies": ["..."],
      "where_it_fails": "边界/误用风险"
    }}
  ],
  "decision_rules": [
    {{
      "rule": "当...时，应该/不应该...",
      "scope": "适用范围",
      "anti_pattern": "常见误用",
      "timestamp": "[...]",
      "source_reasoning": "为什么可以推出这条规则"
    }}
  ],
  "entities": {{
    "people": [],
    "orgs": [],
    "products": [],
    "papers": [],
    "concepts": []
  }},
  "questions": [
    {{
      "question": "这个片段引出的高质量问题",
      "why_it_matters": "...",
      "timestamp": "[...]",
      "motif": "可归属的母题"
    }}
  ],
  "writing_material": [
    {{
      "type": "hook|analogy|near_quote|article_angle",
      "text": "...",
      "timestamp": "[...]",
      "quote_status": "paraphrase_needs_verification"
    }}
  ]
}}

数量限制：
- high_value_segments 最多 3 条
- claims 最多 3 条
- mental_models 最多 2 条
- decision_rules 最多 2 条
- questions 最多 3 条
- writing_material 最多 2 条
- 不要在数组里输出 null；没有内容就输出 []

访谈片段：
{chunk_text}
"""


REPAIR_USER_TEMPLATE = """下面文本本应是 JSON，但语法可能损坏。请只做 JSON 修复：
- 保留原有信息
- 删除数组里的 null
- 补齐缺失逗号/引号/括号
- 只输出严格 JSON，不要 Markdown，不要解释

待修复文本：
{bad_json}
"""


EPISODE_META_USER_TEMPLATE = """请根据下面同一集访谈的 chunk extraction，生成这集的 Episode Meta。

Episode:
- bvid: {bvid}
- title: {title}
- source_file: {source_file}

要求：
1. 不要复述全部条目，只判断这集的主问题、类型、领域、Terry relevance。
2. Terry relevance 要具体说明它如何影响 Terry 的 AI 科研军团、产品判断、投资观察、知识系统。
3. 输出严格 JSON，所有字段都必须存在。

输出 JSON schema:
{{
  "episode_type": "interview|paper_explainer|founder_story|investor_view|industry_map|other",
  "guest": {{"name": "", "role": "", "org": ""}},
  "domains": [],
  "core_question": "",
  "one_sentence_takeaway": "",
  "terry_relevance": [],
  "asr_caveats": []
}}

Chunk extraction JSON:
{chunk_json}
"""


@dataclass(frozen=True)
class Episode:
    bvid: str
    title: str
    url: str
    source_path: Path
    segments: list[dict[str, Any]]


def timestamp(seconds: float) -> str:
    sec = int(seconds)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    if repair_json:
        for candidate in list(candidates):
            try:
                repaired = repair_json(candidate, return_objects=True)
                if isinstance(repaired, dict):
                    return repaired
            except Exception:
                pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def clean_json(value: Any) -> Any:
    if isinstance(value, list):
        return [clean_json(x) for x in value if x is not None]
    if isinstance(value, dict):
        return {k: clean_json(v) for k, v in value.items() if v is not None}
    return value


CHUNK_LIST_FIELDS = {
    "high_value_segments": ["timestamp", "topic", "why_it_matters", "evidence_note"],
    "claims": ["claim", "speaker", "topic", "evidence", "timestamp", "confidence", "terry_relevance"],
    "mental_models": ["name", "definition", "source_observation", "timestamp", "where_it_applies", "where_it_fails"],
    "decision_rules": ["rule", "scope", "anti_pattern", "timestamp", "source_reasoning"],
    "questions": ["question", "why_it_matters", "timestamp", "motif"],
    "writing_material": ["type", "text", "timestamp", "quote_status"],
}


EPISODE_REQUIRED_KEYS = [
    "episode_id",
    "bvid",
    "title",
    "episode_type",
    "guest",
    "domains",
    "core_question",
    "one_sentence_takeaway",
    "terry_relevance",
    "high_value_segments",
    "key_claims",
    "mental_models",
    "decision_rules",
    "entities",
    "open_questions",
    "writing_material",
    "asr_caveats",
]


EPISODE_META_REQUIRED_KEYS = [
    "episode_type",
    "guest",
    "domains",
    "core_question",
    "one_sentence_takeaway",
    "terry_relevance",
    "asr_caveats",
]


EPISODE_LIST_LIMITS = {
    "high_value_segments": 12,
    "key_claims": 12,
    "mental_models": 8,
    "decision_rules": 6,
    "open_questions": 12,
    "writing_material": 10,
}


def ensure_required_keys(data: dict[str, Any], keys: list[str], context: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise ValueError(f"{context} missing keys: {', '.join(missing)}")


def validate_list_items(data: dict[str, Any], schema: dict[str, list[str]], context: str) -> None:
    for list_key, item_keys in schema.items():
        items = data.get(list_key, [])
        if not isinstance(items, list):
            raise ValueError(f"{context}.{list_key} must be a list")
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"{context}.{list_key}[{idx}] must be an object")
            missing = [key for key in item_keys if not item.get(key)]
            if missing:
                raise ValueError(f"{context}.{list_key}[{idx}] missing fields: {', '.join(missing)}")


def validate_chunk_output(data: dict[str, Any]) -> None:
    ensure_required_keys(
        data,
        [
            "chunk_id",
            "time_range",
            "local_summary",
            "high_value_segments",
            "claims",
            "mental_models",
            "decision_rules",
            "entities",
            "questions",
            "writing_material",
        ],
        "chunk",
    )
    validate_list_items(data, CHUNK_LIST_FIELDS, "chunk")


def validate_episode_card(data: dict[str, Any]) -> None:
    ensure_required_keys(data, EPISODE_REQUIRED_KEYS, "episode")
    if not isinstance(data.get("guest"), dict):
        raise ValueError("episode.guest must be an object")
    if not isinstance(data.get("entities"), dict):
        raise ValueError("episode.entities must be an object")


def validate_episode_meta(data: dict[str, Any]) -> None:
    ensure_required_keys(data, EPISODE_META_REQUIRED_KEYS, "episode_meta")
    if not isinstance(data.get("guest"), dict):
        raise ValueError("episode_meta.guest must be an object")
    for key in ["domains", "terry_relevance", "asr_caveats"]:
        if not isinstance(data.get(key), list):
            raise ValueError(f"episode_meta.{key} must be a list")


def trim_episode_card(card: dict[str, Any]) -> dict[str, Any]:
    for key, limit in EPISODE_LIST_LIMITS.items():
        if isinstance(card.get(key), list):
            card[key] = card[key][:limit]
    return card


def normalize_key(value: Any) -> str:
    if isinstance(value, str):
        return re.sub(r"\s+", "", value).lower()
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def select_items(
    chunk_results: list[dict[str, Any]],
    source_key: str,
    limit: int,
    dedupe_field: str | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in chunk_results:
        for item in chunk.get(source_key, []) or []:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row.setdefault("chunk_id", chunk.get("chunk_id"))
            key_value = row.get(dedupe_field) if dedupe_field else row
            dedupe_key = normalize_key(key_value)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            selected.append(row)
            if len(selected) >= limit:
                return selected
    return selected


def merge_entities(chunk_results: list[dict[str, Any]]) -> dict[str, list[Any]]:
    merged: dict[str, list[Any]] = {"people": [], "orgs": [], "products": [], "papers": [], "concepts": []}
    seen: dict[str, set[str]] = {key: set() for key in merged}
    for chunk in chunk_results:
        entities = chunk.get("entities", {}) or {}
        if not isinstance(entities, dict):
            continue
        for etype in merged:
            for value in entities.get(etype, []) or []:
                dedupe_key = normalize_key(value)
                if dedupe_key in seen[etype]:
                    continue
                seen[etype].add(dedupe_key)
                merged[etype].append(value)
    return merged


def fallback_episode_meta(ep: Episode, compact_chunks: list[dict[str, Any]], error: str) -> dict[str, Any]:
    summaries = [x.get("local_summary", "") for x in compact_chunks if x.get("local_summary")]
    return {
        "episode_type": "interview",
        "guest": {"name": "", "role": "", "org": ""},
        "domains": [],
        "core_question": ep.title,
        "one_sentence_takeaway": summaries[0] if summaries else "",
        "terry_relevance": ["episode meta 生成失败，需人工复核；条目级抽取仍来自已验证 chunks"],
        "asr_caveats": [f"episode meta generation failed: {error[:300]}"],
    }


def load_episodes(input_dir: Path, bvids: list[str]) -> list[Episode]:
    json_dir = input_dir / "json"
    episodes: list[Episode] = []
    for bvid in bvids:
        matches = sorted(json_dir.glob(f"*{bvid}*.json"))
        if not matches:
            raise FileNotFoundError(f"No transcript JSON for {bvid} in {json_dir}")
        path = matches[0]
        data = json.loads(path.read_text(encoding="utf-8"))
        episodes.append(
            Episode(
                bvid=bvid,
                title=data.get("title", path.stem),
                url=data.get("url", f"https://www.bilibili.com/video/{bvid}"),
                source_path=path,
                segments=data.get("segments", []),
            )
        )
    return episodes


def make_chunks(ep: Episode, char_budget: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_chars = 0
    start = None
    end = None

    for seg in ep.segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        s = float(seg.get("start", 0))
        e = float(seg.get("end", s))
        line = f"[{timestamp(s)}] {text}"
        if current and current_chars + len(line) > char_budget:
            chunks.append(
                {
                    "chunk_id": f"{ep.bvid}_c{len(chunks)+1:03d}",
                    "time_range": f"[{timestamp(start or 0)}-{timestamp(end or 0)}]",
                    "text": "\n".join(current),
                }
            )
            current = []
            current_chars = 0
            start = None
            end = None
        if start is None:
            start = s
        end = e
        current.append(line)
        current_chars += len(line)

    if current:
        chunks.append(
            {
                "chunk_id": f"{ep.bvid}_c{len(chunks)+1:03d}",
                "time_range": f"[{timestamp(start or 0)}-{timestamp(end or 0)}]",
                "text": "\n".join(current),
            }
        )
    return chunks


def llm_chat_json(
    messages: list[dict[str, str]],
    tier: str,
    max_tokens: int,
    model: str = "",
    retries: int = 2,
    validator: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], str]:
    from llm_router import call

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            kwargs: dict[str, Any] = {
                "max_tokens": max_tokens,
                "timeout": 180,
                "response_format": {"type": "json_object"},
            }
            if model:
                kwargs["model"] = model
            else:
                kwargs["tier"] = tier
            text, provider = call.chat(messages, **kwargs)
            try:
                data = clean_json(extract_json_object(text))
                if validator:
                    validator(data)
                return data, provider
            except Exception:
                repair_prompt = REPAIR_USER_TEMPLATE.format(bad_json=text[:20000])
                repair_kwargs = dict(kwargs)
                repair_kwargs["max_tokens"] = max_tokens
                repaired, repair_provider = call.chat(
                    [{"role": "system", "content": "你是严格 JSON 修复器。只输出 JSON。"}, {"role": "user", "content": repair_prompt}],
                    **repair_kwargs,
                )
                provider = f"{provider}+repair:{repair_provider}"
                data = clean_json(extract_json_object(repaired))
                if validator:
                    validator(data)
                return data, provider
        except Exception as exc:
            last_error = exc
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"LLM JSON call failed: {last_error}") from last_error


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def extract_chunk(ep: Episode, chunk: dict[str, Any], out_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    chunk_path = out_dir / "chunks" / ep.bvid / f"{chunk['chunk_id']}.json"
    if chunk_path.exists() and not args.force:
        return json.loads(chunk_path.read_text(encoding="utf-8"))

    prompt = CHUNK_USER_TEMPLATE.format(
        bvid=ep.bvid,
        title=ep.title,
        chunk_id=chunk["chunk_id"],
        time_range=chunk["time_range"],
        chunk_text=chunk["text"],
    )
    try:
        data, provider = llm_chat_json(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            tier=args.chunk_tier,
            model=args.chunk_model,
            max_tokens=args.chunk_max_tokens,
            validator=validate_chunk_output,
        )
    except Exception as exc:
        data = {
            "chunk_id": chunk["chunk_id"],
            "time_range": chunk["time_range"],
            "local_summary": "",
            "high_value_segments": [],
            "claims": [],
            "mental_models": [],
            "decision_rules": [],
            "entities": {"people": [], "orgs": [], "products": [], "papers": [], "concepts": []},
            "questions": [],
            "writing_material": [],
            "_error": str(exc)[:2000],
        }
        provider = "failed"
    data["_meta"] = {
        "bvid": ep.bvid,
        "title": ep.title,
        "provider": provider,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_path": str(ep.source_path),
    }
    write_json(chunk_path, data)
    return data


def fold_episode(ep: Episode, chunk_results: list[dict[str, Any]], out_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    episode_path = out_dir / "episodes" / f"{ep.bvid}.json"
    if episode_path.exists() and not args.force:
        return json.loads(episode_path.read_text(encoding="utf-8"))

    failed_chunks = [x for x in chunk_results if x.get("_error")]
    if failed_chunks:
        failure_path = out_dir / "failures" / f"{ep.bvid}.json"
        write_json(
            failure_path,
            {
                "bvid": ep.bvid,
                "title": ep.title,
                "failed_at": "chunk_extraction",
                "failed_chunks": [
                    {
                        "chunk_id": x.get("chunk_id"),
                        "time_range": x.get("time_range"),
                        "error": x.get("_error"),
                    }
                    for x in failed_chunks
                ],
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        raise RuntimeError(f"{ep.bvid} has failed chunks; see {failure_path}")

    compact_chunks = []
    for item in chunk_results:
        compact_chunks.append(
            {
                "chunk_id": item.get("chunk_id"),
                "time_range": item.get("time_range"),
                "local_summary": item.get("local_summary"),
                "high_value_segments": item.get("high_value_segments", [])[:4],
                "claims": item.get("claims", [])[:5],
                "mental_models": item.get("mental_models", [])[:4],
                "decision_rules": item.get("decision_rules", [])[:3],
                "entities": item.get("entities", {}),
                "questions": item.get("questions", [])[:4],
                "writing_material": item.get("writing_material", [])[:3],
            }
        )
    prompt = EPISODE_META_USER_TEMPLATE.format(
        bvid=ep.bvid,
        title=ep.title,
        source_file=str(ep.source_path),
        chunk_json=json.dumps(compact_chunks, ensure_ascii=False),
    )

    try:
        meta, provider = llm_chat_json(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            tier=args.fold_tier,
            model=args.fold_model,
            max_tokens=args.fold_max_tokens,
            validator=validate_episode_meta,
        )
    except Exception as exc:
        meta = fallback_episode_meta(ep, compact_chunks, str(exc))
        provider = "meta_failed"

    card = {
        "episode_id": ep.bvid,
        "bvid": ep.bvid,
        "title": ep.title,
        "episode_type": meta.get("episode_type", "interview"),
        "guest": meta.get("guest", {"name": "", "role": "", "org": ""}),
        "domains": meta.get("domains", []),
        "core_question": meta.get("core_question", ""),
        "one_sentence_takeaway": meta.get("one_sentence_takeaway", ""),
        "terry_relevance": meta.get("terry_relevance", []),
        "high_value_segments": select_items(chunk_results, "high_value_segments", 12, "timestamp"),
        "key_claims": select_items(chunk_results, "claims", 12, "claim"),
        "mental_models": select_items(chunk_results, "mental_models", 8, "name"),
        "decision_rules": select_items(chunk_results, "decision_rules", 6, "rule"),
        "entities": merge_entities(chunk_results),
        "open_questions": select_items(chunk_results, "questions", 12, "question"),
        "writing_material": select_items(chunk_results, "writing_material", 10, "text"),
        "asr_caveats": meta.get("asr_caveats", []),
    }
    card = trim_episode_card(card)
    validate_episode_card(card)
    card["_meta"] = {
        "provider": provider,
        "aggregation": "local_from_validated_chunks",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_path": str(ep.source_path),
        "chunk_count": len(chunk_results),
    }
    write_json(episode_path, card)
    return card


def enrich_row(row: dict[str, Any], card: dict[str, Any], kind: str) -> dict[str, Any]:
    enriched = dict(row)
    enriched.update(
        {
            "kind": kind,
            "bvid": card.get("bvid"),
            "episode_title": card.get("title"),
            "episode_type": card.get("episode_type"),
            "guest": card.get("guest"),
            "source": f"https://www.bilibili.com/video/{card.get('bvid')}",
        }
    )
    return enriched


def rebuild_indexes(out_dir: Path, cards: list[dict[str, Any]]) -> None:
    for name in ["claims.jsonl", "mental_models.jsonl", "decision_rules.jsonl", "questions.jsonl", "entities.jsonl", "writing_material.jsonl"]:
        path = out_dir / name
        if path.exists():
            path.unlink()

    all_entities: list[dict[str, Any]] = []
    for card in cards:
        append_jsonl(out_dir / "claims.jsonl", [enrich_row(x, card, "claim") for x in card.get("key_claims", [])])
        append_jsonl(out_dir / "mental_models.jsonl", [enrich_row(x, card, "mental_model") for x in card.get("mental_models", [])])
        append_jsonl(out_dir / "decision_rules.jsonl", [enrich_row(x, card, "decision_rule") for x in card.get("decision_rules", [])])
        append_jsonl(out_dir / "questions.jsonl", [enrich_row(x, card, "question") for x in card.get("open_questions", [])])
        append_jsonl(out_dir / "writing_material.jsonl", [enrich_row(x, card, "writing_material") for x in card.get("writing_material", [])])

        entities = card.get("entities", {}) or {}
        for etype, values in entities.items():
            for value in values or []:
                all_entities.append(
                    {
                        "entity": value,
                        "entity_type": etype,
                        "bvid": card.get("bvid"),
                        "episode_title": card.get("title"),
                        "source": f"https://www.bilibili.com/video/{card.get('bvid')}",
                    }
                )
    append_jsonl(out_dir / "entities.jsonl", all_entities)

    index = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "episode_count": len(cards),
        "episodes": [
            {
                "bvid": c.get("bvid"),
                "title": c.get("title"),
                "episode_type": c.get("episode_type"),
                "core_question": c.get("core_question"),
                "one_sentence_takeaway": c.get("one_sentence_takeaway"),
            }
            for c in cards
        ],
    }
    write_json(out_dir / "index.json", index)


def render_episode_md(card: dict[str, Any], out_dir: Path) -> None:
    lines = [
        f"# {card.get('title', card.get('bvid'))}",
        "",
        f"- BV: {card.get('bvid')}",
        f"- 类型: {card.get('episode_type', '')}",
        f"- 核心问题: {card.get('core_question', '')}",
        f"- 一句话结论: {card.get('one_sentence_takeaway', '')}",
        "",
        "## Terry Relevance",
    ]
    for item in card.get("terry_relevance", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Key Claims"])
    for item in card.get("key_claims", []) or []:
        lines.append(f"- {item.get('timestamp','')} {item.get('claim','')}")
    lines.extend(["", "## Mental Models"])
    for item in card.get("mental_models", []) or []:
        lines.append(f"- **{item.get('name','')}**: {item.get('definition','')}")
    lines.extend(["", "## Decision Rules"])
    for item in card.get("decision_rules", []) or []:
        lines.append(f"- {item.get('rule','')} ({item.get('timestamp','')})")
    lines.extend(["", "## Open Questions"])
    for item in card.get("open_questions", []) or []:
        q = item.get("question") if isinstance(item, dict) else str(item)
        lines.append(f"- {q}")
    path = out_dir / "episodes_md" / f"{card.get('bvid')}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def process_episode(ep: Episode, out_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    chunks = make_chunks(ep, args.chunk_chars)
    print(f"[episode] {ep.bvid} chunks={len(chunks)} title={ep.title}", flush=True)
    chunk_results: list[dict[str, Any]] = []

    if args.workers <= 1:
        for chunk in chunks:
            print(f"  [chunk] {chunk['chunk_id']} {chunk['time_range']}", flush=True)
            chunk_results.append(extract_chunk(ep, chunk, out_dir, args))
    else:
        with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            future_map = {pool.submit(extract_chunk, ep, chunk, out_dir, args): chunk for chunk in chunks}
            for fut in futures.as_completed(future_map):
                chunk = future_map[fut]
                print(f"  [chunk-done] {chunk['chunk_id']} {chunk['time_range']}", flush=True)
                chunk_results.append(fut.result())
        chunk_results.sort(key=lambda x: x.get("chunk_id", ""))

    card = fold_episode(ep, chunk_results, out_dir, args)
    render_episode_md(card, out_dir)
    print(f"[episode-done] {ep.bvid}", flush=True)
    return card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/zhangxiaojun-transcripts")
    parser.add_argument("--output-dir", default="data/zhangxiaojun-transcripts/structured")
    parser.add_argument("--bvids", default=",".join(DEFAULT_BVIDS), help="comma-separated BVIDs; use all for all episodes")
    parser.add_argument("--chunk-chars", type=int, default=12000)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--chunk-tier", default="standard")
    parser.add_argument("--fold-tier", default="standard")
    parser.add_argument("--chunk-model", default="")
    parser.add_argument("--fold-model", default="")
    parser.add_argument("--chunk-max-tokens", type=int, default=2400)
    parser.add_argument("--fold-max-tokens", type=int, default=5000)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.bvids.strip().lower() == "all":
        index = json.loads((input_dir / "_index.json").read_text(encoding="utf-8"))
        bvids = [x["bvid"] for x in index.get("videos", [])]
    else:
        bvids = [x.strip() for x in args.bvids.split(",") if x.strip()]

    episodes = load_episodes(input_dir, bvids)
    cards = []
    failures = []
    for ep in episodes:
        try:
            cards.append(process_episode(ep, out_dir, args))
            rebuild_indexes(out_dir, cards)
        except Exception as exc:
            failures.append({"bvid": ep.bvid, "title": ep.title, "error": str(exc)})
            print(f"[episode-failed] {ep.bvid} {exc}", file=sys.stderr, flush=True)

    rebuild_indexes(out_dir, cards)
    if failures:
        write_json(
            out_dir / "failures" / "_run_failures.json",
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "failures": failures,
            },
        )
        print(f"[done-with-failures] output={out_dir} failures={len(failures)}", flush=True)
        return 1
    print(f"[done] output={out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
