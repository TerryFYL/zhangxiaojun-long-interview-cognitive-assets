#!/usr/bin/env python3
"""Export a public-safe GitHub release package for the Zhang Xiaojun corpus.

This exporter deliberately does not publish raw transcripts, subtitle files,
ASR segment text, chunk-level extraction caches, or local private paths.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_NAME = "zhangxiaojun-long-interview-cognitive-assets"
SOURCE_ROOT = Path("data/zhangxiaojun-transcripts")
STRUCTURED_ROOT = SOURCE_ROOT / "structured"
DEFAULT_OUTPUT = Path("open-source") / PROJECT_NAME

DROP_KEYS = {
    "_meta",
    "source_path",
    "evidence",
    "evidence_note",
    "quote_status",
    "raw_text",
    "transcript",
    "segments",
}

DROP_TOP_LEVEL_KEYS = {
    "writing_material",
}

JSONL_FILES = [
    "claims.jsonl",
    "mental_models.jsonl",
    "decision_rules.jsonl",
    "questions.jsonl",
    "entities.jsonl",
]

SYNTHESIS_FILES = [
    "agent.md",
    "material_processing_design.md",
    "cognitive_boundary_cards.md",
    "interview_container_analysis.md",
    "question_depth_framework.md",
    "long_interview_mining_protocol.md",
    "index.html",
]

TOOL_FILES = [
    "zhangxiaojun_bilibili_transcripts.py",
    "zhangxiaojun_knowledge_extract.py",
    "build_long_interview_cognitive_assets.py",
    "build_cognitive_html_viewer.py",
    "export_public_zhangxiaojun_release.py",
]


README = """# 张小珺商业访谈录: 长访谈认知代谢公开包

这是一个围绕「张小珺商业访谈录」长访谈素材生成的认知代谢数据包。它不是访谈逐字稿仓库，也不是主持人人格 Agent，而是一套把长访谈转成可复用知识资产的工作样例。

本仓库当前包含 26 期视频的来源索引、结构化 episode cards、跨集 JSONL 数据、156 张认知边界卡、HTML 工作台、处理协议和复现脚本。

## 可以直接使用的内容

- `data/source_videos.json`: 原始 Bilibili 视频来源索引，含 BV 号、标题、发布时间、时长和原始链接。
- `data/structured/episodes/*.json`: 公开安全版 episode card，移除了原始字幕证据、ASR segment 和本地路径。
- `data/structured/*.jsonl`: claim / mental model / decision rule / question / entity 的跨集索引，移除了逐字证据字段。
- `data/structured/synthesis/cognitive_boundary_cards.md`: 156 张认知边界卡，用于发现知识增量、认识变化和行动修正。
- `data/structured/synthesis/index.html`: 可本地打开的 HTML 工作台。
- `protocol/长素材认知代谢协议.md`: 后续处理其他长访谈、播客、课程资料时可复用的协议。
- `tools/`: 本次工作流用到的脚本。

## 有意不包含的内容

本仓库不包含完整字幕、逐字稿、SRT、ASR segment JSON、chunk 级中间抽取缓存或音视频文件。

原因很简单：原视频、音频、字幕和访谈内容的权利属于原作者、平台和相关权利人。这里公开的是处理方法、结构化索引和分析性笔记；如果你需要完整转写文字，请在确认自己拥有处理权限的前提下，在本地生成。

`data/transcripts/README.md` 里保留了这一边界说明。

## 快速查看

直接用浏览器打开：

```text
data/structured/synthesis/index.html
```

这个 HTML 是静态文件，不需要后端服务。

## 数据边界

这些结果来自 ASR 字幕和 LLM 结构化处理，存在以下限制：

- ASR 可能误识别人名、英文、术语和公司名。
- timestamp 用于回到原视频复核，不等于法律意义上的引用授权。
- 公开数据移除了逐字证据字段，所以需要严肃引用时应回到原视频核对。
- 认知边界卡是分析性笔记，不是对被访者或主持人的完整观点复刻。

## 复现流程

如果你有权处理相应视频材料，可按这个流程复现：

```bash
python tools/zhangxiaojun_bilibili_transcripts.py --all-videos
python tools/zhangxiaojun_knowledge_extract.py --input-dir data/zhangxiaojun-transcripts --output-dir data/zhangxiaojun-transcripts/structured --bvids all --workers 4
python tools/build_long_interview_cognitive_assets.py --root data/zhangxiaojun-transcripts/structured
python tools/build_cognitive_html_viewer.py --synthesis-dir data/zhangxiaojun-transcripts/structured/synthesis
python tools/export_public_release.py --force
```

注意：结构化抽取脚本使用了本地 `llm_router` 接口；如果你在自己的环境运行，需要把 `chat` 调用替换成自己的 LLM provider。

## 目录结构

```text
.
├── data/
│   ├── source_videos.json
│   ├── transcripts/
│   │   └── README.md
│   └── structured/
│       ├── episodes/
│       ├── episodes_md/
│       ├── claims.jsonl
│       ├── mental_models.jsonl
│       ├── decision_rules.jsonl
│       ├── questions.jsonl
│       ├── entities.jsonl
│       └── synthesis/
├── protocol/
├── tools/
├── DATA_LICENSE.md
├── LICENSE
└── NOTICE.md
```

## 适合怎么用

最有价值的用法不是把它当摘要看完，而是把每张认知边界卡拿来做三件事：

1. 问它新增了什么知识。
2. 问它修正了什么认识。
3. 问它会如何改变下一次判断、提问、写作或行动。

这也是这套公开包的核心贡献：把长访谈从「信息消费」转成「认知代谢」。
"""


NOTICE = """# Notice

This repository is not affiliated with Bilibili, 张小珺商业访谈录, or any guest appearing in the referenced videos.

Original videos, audio, captions, subtitles, transcripts, titles where applicable, and interview content remain the property of their respective right holders.

This public package intentionally excludes raw transcripts, subtitle files, ASR segment text, chunk-level extraction caches, and audio/video files. Timestamps and BV links are provided so readers can verify claims against the original public videos.

Use the included tools only for material you are allowed to process.
"""


DATA_LICENSE = """# Data And Notes License

Code in this repository is licensed under the MIT License in `LICENSE`.

For the repository owner's original schemas, prompts, public episode cards, structured annotations, synthesis documents, and cognitive boundary cards, permission is granted under Creative Commons Attribution 4.0 International (CC BY 4.0), to the extent the repository owner can license those original contributions.

This license does not cover third-party material, including but not limited to the original Bilibili videos, audio, subtitles, transcript text, interview titles where protected, guest speech, host speech, screenshots, platform metadata, or other right-holder content.

Raw transcripts are not included in this repository. If you generate transcripts locally, you are responsible for ensuring that your use complies with applicable law, platform terms, and right-holder permissions.
"""


MIT_LICENSE = """MIT License

Copyright (c) 2026 Terry

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


GITIGNORE = """__pycache__/
*.pyc
.DS_Store
.env
.venv/
venv/

# Raw/private media and transcript outputs are intentionally excluded.
data/raw/
data/audio/
data/video/
data/transcripts/*
!data/transcripts/README.md
*.mp3
*.mp4
*.m4a
*.wav
*.srt
"""


REQUIREMENTS = """markdown>=3.6
json-repair>=0.39.0
yt-dlp>=2025.1.0
faster-whisper>=1.1.0
"""


TRANSCRIPTS_README = """# Transcripts

完整字幕、逐字稿、SRT、ASR segment JSON 和音视频文件没有包含在这个公开仓库中。

本项目公开的是长访谈认知代谢方法、结构化索引和分析性笔记。若你对素材拥有处理权限，可以在本地使用 `tools/zhangxiaojun_bilibili_transcripts.py` 生成自己的转写文件。

请不要把未获授权的完整转写文字提交到公开仓库。
"""


STRUCTURED_README = """# Structured Data

这里是公开安全版结构化数据。

已移除：

- 原始字幕/逐字稿文本
- ASR segment
- claim 的逐字 evidence 字段
- writing material / near quote 数据
- chunk 级中间抽取缓存
- 本地绝对路径和私有运行信息

保留：

- 来源 BV 号、标题、原视频链接和 timestamp
- episode 级主题、嘉宾、领域、核心问题和 Terry relevance
- 跨集 claim / mental model / decision rule / question / entity 索引
- 合成文档和认知边界卡
"""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def ensure_safe_output(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    allowed_parent = (Path.cwd() / "open-source").resolve()
    if os.path.commonpath([str(resolved), str(allowed_parent)]) != str(allowed_parent):
        raise ValueError(f"Refusing to export outside {allowed_parent}: {resolved}")
    return resolved


def clean_output(path: Path, force: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not force:
            raise FileExistsError(f"{path} already exists and is not empty; rerun with --force")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def build_video_map(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("bvid")): item for item in index.get("videos", []) if item.get("bvid")}


def sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for key, value in obj.items():
            if key in DROP_KEYS or key in DROP_TOP_LEVEL_KEYS:
                continue
            result[key] = sanitize(value)
        return result
    if isinstance(obj, list):
        return [sanitize(item) for item in obj]
    return obj


def sanitize_episode(card: dict[str, Any], video_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cleaned = sanitize(card)
    bvid = cleaned.get("bvid") or cleaned.get("episode_id")
    video = video_map.get(str(bvid), {})
    if bvid:
        cleaned["bvid"] = bvid
        cleaned["source"] = video.get("url") or f"https://www.bilibili.com/video/{bvid}"
    if not cleaned.get("url"):
        cleaned.pop("url", None)
    if video:
        cleaned["published_at"] = video.get("created_date")
        cleaned["duration"] = video.get("length")
        cleaned["is_interview"] = video.get("is_interview")
    return cleaned


def sanitize_jsonl_line(line: str, video_map: dict[str, dict[str, Any]]) -> str:
    row = sanitize(json.loads(line))
    bvid = row.get("bvid")
    if bvid and not row.get("source"):
        row["source"] = video_map.get(str(bvid), {}).get("url") or f"https://www.bilibili.com/video/{bvid}"
    return json.dumps(row, ensure_ascii=False)


def render_episode_md(card: dict[str, Any]) -> str:
    lines = [
        f"# {card.get('title', card.get('bvid', 'Untitled'))}",
        "",
        f"- BV: {card.get('bvid', '')}",
        f"- Source: {card.get('source', '')}",
        f"- Type: {card.get('episode_type', '')}",
        f"- Guest: {format_guest(card.get('guest'))}",
        f"- Published: {card.get('published_at', '')}",
        f"- Duration: {card.get('duration', '')}",
        f"- Core question: {card.get('core_question', '')}",
        f"- Takeaway: {card.get('one_sentence_takeaway', '')}",
        "",
        "## Domains",
    ]
    for item in card.get("domains", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Terry Relevance"])
    for item in card.get("terry_relevance", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Key Claims"])
    for item in card.get("key_claims", []) or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- {item.get('timestamp', '')} {item.get('claim', '')}".rstrip())
    lines.extend(["", "## Mental Models"])
    for item in card.get("mental_models", []) or []:
        if not isinstance(item, dict):
            continue
        lines.append(f"- **{item.get('name', '')}**: {item.get('definition', '')}")
    lines.extend(["", "## Decision Rules"])
    for item in card.get("decision_rules", []) or []:
        if not isinstance(item, dict):
            continue
        timestamp = item.get("timestamp", "")
        suffix = f" ({timestamp})" if timestamp else ""
        lines.append(f"- {item.get('rule', '')}{suffix}")
    lines.extend(["", "## Open Questions"])
    for item in card.get("open_questions", []) or []:
        question = item.get("question") if isinstance(item, dict) else str(item)
        lines.append(f"- {question}")
    lines.extend(["", "## ASR Caveats"])
    for item in card.get("asr_caveats", []) or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def format_guest(guest: Any) -> str:
    if not isinstance(guest, dict):
        return ""
    parts = [guest.get("name", ""), guest.get("role", ""), guest.get("org", "")]
    return " / ".join(str(part) for part in parts if part)


def redact_text(text: str) -> str:
    replacements = {
        str(STRUCTURED_ROOT.resolve()): "data/structured",
        str(SOURCE_ROOT.resolve()): "data/source-private-not-included",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    users_prefix = "/" + "Users" + "/"
    text = re.sub(
        re.escape(users_prefix) + r"[^/\s<>'\"；]+/transcripts/张小珺商业访谈录",
        "private/transcripts-not-included",
        text,
    )
    text = re.sub(re.escape(users_prefix) + r"[^/\s<>'\"；]+/[^\s<>'\"；]+", "$HOME/<private-path>", text)
    text = re.sub(r"source_dir=[^；\n<]+", "source_dir=data/structured", text)
    return text


def copy_public_synthesis(out_root: Path) -> None:
    src = STRUCTURED_ROOT / "synthesis"
    dst = out_root / "data" / "structured" / "synthesis"
    dst.mkdir(parents=True, exist_ok=True)
    for name in SYNTHESIS_FILES:
        source_file = src / name
        if not source_file.exists():
            continue
        write_text(dst / name, redact_text(source_file.read_text(encoding="utf-8")))

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_material": "张小珺商业访谈录 / Bilibili space 280780745",
        "raw_transcripts_included": False,
        "chunk_cache_included": False,
        "synthesis_files": [name for name in SYNTHESIS_FILES if (src / name).exists()],
    }
    write_json(dst / "_public_manifest.json", manifest)


def copy_tools(out_root: Path) -> None:
    dst = out_root / "tools"
    dst.mkdir(parents=True, exist_ok=True)
    for name in TOOL_FILES:
        src = Path("tools") / name
        if not src.exists():
            continue
        target = "export_public_release.py" if name == "export_public_zhangxiaojun_release.py" else name
        shutil.copy2(src, dst / target)


def export_release(out_root: Path) -> None:
    index = read_json(SOURCE_ROOT / "_index.json")
    video_map = build_video_map(index)

    public_index = {
        "up_name": index.get("up_name"),
        "up_mid": index.get("up_mid"),
        "space_url": index.get("space_url"),
        "source_checked_at": index.get("source_checked_at"),
        "total_known_videos": index.get("total_known_videos"),
        "selected_count": index.get("selected_count"),
        "mode": index.get("mode"),
        "raw_transcripts_included": False,
        "videos": index.get("videos", []),
    }
    write_json(out_root / "data" / "source_videos.json", public_index)

    structured_out = out_root / "data" / "structured"
    write_text(structured_out / "README.md", STRUCTURED_README)

    episode_cards: list[dict[str, Any]] = []
    for src_path in sorted((STRUCTURED_ROOT / "episodes").glob("*.json")):
        card = sanitize_episode(read_json(src_path), video_map)
        episode_cards.append(card)
        write_json(structured_out / "episodes" / src_path.name, card)
        write_text(structured_out / "episodes_md" / f"{card.get('bvid', src_path.stem)}.md", render_episode_md(card))

    structured_index = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "episode_count": len(episode_cards),
        "raw_transcripts_included": False,
        "removed_fields": sorted(DROP_KEYS | DROP_TOP_LEVEL_KEYS),
        "episodes": [
            {
                "bvid": card.get("bvid"),
                "title": card.get("title"),
                "source": card.get("source"),
                "episode_type": card.get("episode_type"),
                "guest": card.get("guest"),
                "one_sentence_takeaway": card.get("one_sentence_takeaway"),
            }
            for card in episode_cards
        ],
    }
    write_json(structured_out / "index.json", structured_index)

    for name in JSONL_FILES:
        src_file = STRUCTURED_ROOT / name
        if not src_file.exists():
            continue
        lines = []
        for line in src_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                lines.append(sanitize_jsonl_line(line, video_map))
        write_text(structured_out / name, "\n".join(lines))

    copy_public_synthesis(out_root)
    copy_tools(out_root)

    write_text(out_root / "README.md", README)
    write_text(out_root / "NOTICE.md", NOTICE)
    write_text(out_root / "DATA_LICENSE.md", DATA_LICENSE)
    write_text(out_root / "LICENSE", MIT_LICENSE)
    write_text(out_root / ".gitignore", GITIGNORE)
    write_text(out_root / "requirements.txt", REQUIREMENTS)
    write_text(out_root / "data" / "transcripts" / "README.md", TRANSCRIPTS_README)
    protocol_dir = out_root / "protocol"
    protocol_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path("长素材认知代谢协议.md"), protocol_dir / "长素材认知代谢协议.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a public-safe release repo directory.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_root = ensure_safe_output(Path(args.output))
    clean_output(out_root, args.force)
    export_release(out_root)
    print(out_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
