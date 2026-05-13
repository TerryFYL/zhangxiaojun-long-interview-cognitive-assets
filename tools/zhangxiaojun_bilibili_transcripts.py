#!/usr/bin/env python3
"""Batch transcript extraction for 张小珺商业访谈录 on Bilibili.

Default behavior processes interview-like episodes only. Use --all-videos to
include the five explainer/non-interview videos from the same space.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


UP_NAME = "张小珺商业访谈录"
UP_MID = "280780745"
BASE_DIR = Path.home() / "transcripts" / UP_NAME
INDEX_FILE = BASE_DIR / "_index.json"
PROGRESS_FILE = BASE_DIR / "_progress.json"
LOG_FILE = BASE_DIR / "_run.log"

DEFAULT_MODEL = "tiny"
DEFAULT_FFMPEG_DIRS = [
    "/opt/homebrew/bin",
    "/opt/homebrew/Cellar/ffmpeg/8.1/bin",
    "/usr/local/bin",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class VideoItem:
    seq: int
    bvid: str
    aid: int
    title: str
    created: int
    length: str
    play: int
    comment: int
    is_interview: bool

    @property
    def url(self) -> str:
        return f"https://www.bilibili.com/video/{self.bvid}"

    @property
    def created_date(self) -> str:
        return datetime.fromtimestamp(self.created).strftime("%Y-%m-%d")


VIDEOS: list[VideoItem] = [
    VideoItem(1, "BV1YR5E6EE9o", 116551235669764, "对姚顺宇的4小时访谈：请允许我小疯一下！在Anthropic和Gemini训模型、技术预测、英雄主义已过去", 1778457600, "228:01", 66957, 312, True),
    VideoItem(2, "BV1iVoVBgERD", 116457333588484, "对罗福莉的3.5小时访谈：AI范式已然巨变！OpenClaw、智能体框架、Agent范式很吃Post-train、卡的分配比例、巨变下的组织", 1777001400, "214:39", 336954, 1478, True),
    VideoItem(3, "BV13BdfBoELd", 116431815443051, "对洪乐潼的4小时访谈：AI for Math、把数学变成Lean、数学天书中的证明、直觉、被创造的与被发现的", 1776654000, "263:11", 54519, 249, True),
    VideoItem(4, "BV1sLX9B4EqD", 116313401918882, "【数据的综述】和谢晨聊，新时代的石油、历史、版图、数据金字塔、定价与Recipe", 1774839600, "156:51", 33095, 108, True),
    VideoItem(5, "BV1tew5zVEDf", 116236243435948, "对谢赛宁的7小时马拉松访谈：世界模型、逃出硅谷、反OpenAI、AMI Labs、两次拒绝Ilya、杨立昆、李飞飞和42", 1773631800, "404:38", 174447, 481, True),
    VideoItem(6, "BV1arcjzpE1B", 116062532141170, "对星海图高继扬的3小时访谈：鲶鱼、曾国藩、机器人、Waymo与Momenta的两面、一只狼与许华哲的离开", 1770973878, "184:14", 43933, 100, True),
    VideoItem(7, "BV1ZczaBJE58", 115959151005514, "印奇出任阶跃星辰董事长的访谈：聪明人的诱惑、取舍、超长链路残酷淘汰赛、阶跃函数和超多元方程", 1769396664, "120:05", 99097, 147, True),
    VideoItem(8, "BV1awiDBDEWS", 115857313300913, "全球大模型第一股的上市访谈，和智谱CEO张鹏聊：敢问路在何方？", 1767842704, "144:36", 121719, 333, True),
    VideoItem(9, "BV1knvYBDEjs", 115807753406655, "Manus决定出售前最后的访谈：啊，这奇幻的2025年漂流啊…", 1767090169, "211:01", 411688, 3070, True),
    VideoItem(10, "BV13AmpBiE2o", 115690346384262, "对投资人朱啸虎的第三次访谈：现实主义、AI的盛筵与泡泡、和共识错开15度、《王者荣耀》", 1765294780, "46:27", 194214, 389, True),
    VideoItem(11, "BV1fiybB4EDU", 115460884530838, "对李想的第二次3小时访谈：CEO大模型、MoE、梁文锋、VLA、能量、记忆、对抗人性、亲密关系、人类的智慧", 1761794442, "163:53", 113682, 133, True),
    VideoItem(12, "BV1pkyqBxEdB", 115449392204906, "干货！开源一段论文探索之旅给大家", 1761618286, "262:38", 41861, 85, False),
    VideoItem(13, "BV1hFe1zSEXp", 115099134134471, "对话Kimi创始人杨植麟：K2、Agentic LLM、缸中之脑、艰难的泛化、用L4解决L3、长文本影响智商、“站在无限的开端”", 1756273680, "99:39", 216822, 335, True),
    VideoItem(14, "BV1vMtUzJEC7", 114992632368942, "对话禾赛李一帆：你仔细想行业的机会来自哪？是国家、民族的机会", 1754649809, "186:04", 88208, 126, True),
    VideoItem(15, "BV1cc8kzmEBs", 114945941311077, "逐段讲解Kimi K2报告并对照ChatGPT Agent、Qwen3-Coder等：“系统工程的力量”", 1753936053, "140:39", 32232, 30, False),
    VideoItem(16, "BV1N2uXzNEBa", 114877775547446, "Lovart创始人陈冕复盘应用创业这两年：这一刻就是好爽啊！！哈哈哈哈哈", 1752896272, "104:57", 78083, 43, True),
    VideoItem(17, "BV1F1GHzLE2k", 114817629163336, "余凯口述30年史：世界不止刀光剑影，是一部人来人往的江湖故事", 1751980353, "153:47", 93267, 138, True),
    VideoItem(18, "BV1WLgQz8Enk", 114778487917310, "机器人泡沫了吗？和10亿美金创始人聊：资本轰炸下的具身智能真相", 1751454000, "158:11", 38848, 89, True),
    VideoItem(19, "BV1PDKozTEZJ", 114749060679808, "95年，离职字节和Kimi，Agent创业：“融资风生水起，我如履薄冰”", 1750933054, "158:17", 50174, 30, True),
    VideoItem(20, "BV17sNEz2ER8", 114704114519888, "人类驯服可控核聚变还有多少路程？对能量奇点创始人杨钊3小时访谈", 1750247200, "153:43", 189347, 606, True),
    VideoItem(21, "BV1zQL9z3ETw", 114401956858323, "【独家对话奔驰全球CEO康林松】转型之中的139岁巨人", 1745635858, "34:07", 44355, 208, True),
    VideoItem(22, "BV1q6RzYnENi", 114291948652862, "逐篇解析机器人基座模型和VLA经典论文——“人就是最智能的VLA”", 1743957575, "149:42", 34063, 52, False),
    VideoItem(23, "BV1N7oBYNEoU", 114212156212682, "Manus全球爆火，我们独家对话Manus创始人肖弘！", 1742739465, "70:50", 57559, 98, True),
    VideoItem(24, "BV1ZmAQekEMc", 114054265835426, "逐篇讲解DeepSeek、Kimi、MiniMax注意力机制新论文——“硬件上的暴力美学”", 1740351600, "156:13", 31245, 46, False),
    VideoItem(25, "BV1xuK5eREJi", 113990210421078, "逐篇讲解DeepSeek关键9篇论文及创新点——“勇敢者的游戏”", 1739353577, "200:54", 53432, 157, False),
    VideoItem(26, "BV1Kt68YBEzq", 113735733740587, "【李想2024唯一深度对谈（纯享版）】张小珺对话李想", 1735469707, "87:14", 116028, 63, True),
]


thread_local = threading.local()
print_lock = threading.Lock()


def log(message: str) -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    with print_lock:
        print(line, flush=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def safe_filename(value: str, max_len: int = 90) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", value)
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._ ")
    return cleaned[:max_len].strip("._ ")


def video_stem(video: VideoItem) -> str:
    return safe_filename(f"{video.seq:02d}_{video.bvid}_{video.title}", 110)


def output_paths(video: VideoItem) -> dict[str, Path]:
    stem = video_stem(video)
    return {
        "md": BASE_DIR / f"{stem}.md",
        "srt": BASE_DIR / "srt" / f"{stem}.srt",
        "json": BASE_DIR / "json" / f"{stem}.json",
    }


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_runtime_paths() -> None:
    paths = [
        str(Path.home() / "Library/Python/3.9/bin"),
        str(Path.home() / ".local/bin"),
        *DEFAULT_FFMPEG_DIRS,
    ]
    current = os.environ.get("PATH", "")
    for path in reversed(paths):
        if path and path not in current:
            current = path + ":" + current
    os.environ["PATH"] = current


def find_ffmpeg_dir() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return str(Path(exe).parent)
    for directory in DEFAULT_FFMPEG_DIRS:
        candidate = Path(directory) / "ffmpeg"
        if candidate.exists():
            return directory
    return None


def request_json(url: str, cookie_header: str = "") -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def load_transcript_config_cookie() -> str:
    config = Path.home() / ".config/transcript/config.toml"
    if not config.exists():
        return ""
    text = config.read_text(encoding="utf-8", errors="ignore")
    values: dict[str, str] = {}
    for key in ("sessdata", "bili_jct", "buvid3"):
        m = re.search(rf'^{key}\s*=\s*"(.*)"\s*$', text, re.M)
        if m and m.group(1):
            values[key] = m.group(1)
    if not values.get("sessdata"):
        return ""
    parts = [f"SESSDATA={values['sessdata']}"]
    if values.get("bili_jct"):
        parts.append(f"bili_jct={values['bili_jct']}")
    if values.get("buvid3"):
        parts.append(f"buvid3={values['buvid3']}")
    return "; ".join(parts)


def get_cid(video: VideoItem) -> int:
    url = "https://api.bilibili.com/x/web-interface/view?" + urllib.parse.urlencode({"bvid": video.bvid})
    data = request_json(url)
    if data.get("code") != 0:
        raise RuntimeError(f"view api failed: {data.get('message')}")
    return int(data["data"]["cid"])


def try_official_subtitle(video: VideoItem) -> list[dict[str, Any]]:
    cookie = load_transcript_config_cookie()
    if not cookie:
        return []
    cid = get_cid(video)
    query = urllib.parse.urlencode({"bvid": video.bvid, "cid": cid})
    data = request_json(f"https://api.bilibili.com/x/player/v2?{query}", cookie_header=cookie)
    subtitles = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
    if not subtitles:
        return []

    chosen = None
    for sub in subtitles:
        lan = (sub.get("lan") or "").lower()
        doc = sub.get("lan_doc") or ""
        if "zh" in lan or "中文" in doc or "ai" in lan:
            chosen = sub
            break
    chosen = chosen or subtitles[0]
    sub_url = chosen.get("subtitle_url") or ""
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url
    if not sub_url:
        return []

    sub_data = request_json(sub_url, cookie_header=cookie)
    segments = []
    for item in sub_data.get("body", []):
        text = (item.get("content") or "").strip()
        if not text:
            continue
        segments.append(
            {
                "start": float(item.get("from", 0)),
                "end": float(item.get("to", item.get("from", 0))),
                "text": text,
                "source": "bilibili-subtitle",
                "language": chosen.get("lan_doc") or chosen.get("lan") or "",
            }
        )
    return segments


def download_audio(video: VideoItem, tmpdir: Path, ffmpeg_dir: str | None) -> Path:
    output = tmpdir / "audio.%(ext)s"
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "5",
        "--no-playlist",
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "-o",
        str(output),
    ]
    if ffmpeg_dir:
        cmd.extend(["--ffmpeg-location", ffmpeg_dir])
    cmd.append(video.url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "yt-dlp failed")[-1000:])
    candidates = sorted(tmpdir.glob("audio*"), key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 1000 and not candidate.name.endswith(".part"):
            return candidate
    raise RuntimeError("audio download produced no usable file")


def get_model(model_name: str, cpu_threads: int):
    model_key = f"model_{model_name}_{cpu_threads}"
    model = getattr(thread_local, model_key, None)
    if model is None:
        from faster_whisper import WhisperModel

        log(f"加载 faster-whisper 模型: {model_name}")
        model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=cpu_threads, num_workers=1)
        setattr(thread_local, model_key, model)
    return model


def transcribe_with_faster_whisper(video: VideoItem, model_name: str, cpu_threads: int, ffmpeg_dir: str | None) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix=f"zxj_{video.bvid}_") as td:
        tmpdir = Path(td)
        audio = download_audio(video, tmpdir, ffmpeg_dir)
        model = get_model(model_name, cpu_threads)
        segments_iter, info = model.transcribe(
            str(audio),
            language="zh",
            beam_size=5,
            vad_filter=True,
            initial_prompt=(
                "这是一档中文商业科技深度访谈，常见词包括 AI、Agent、OpenAI、Anthropic、Gemini、"
                "DeepMind、Kimi、Manus、OpenClaw、世界模型、具身智能、大模型、创业、投资。"
            ),
        )
        segments = []
        for seg in segments_iter:
            text = seg.text.strip()
            if not text:
                continue
            segments.append(
                {
                    "start": float(seg.start),
                    "end": float(seg.end),
                    "text": text,
                    "source": "faster-whisper",
                    "model": model_name,
                    "language": getattr(info, "language", "zh"),
                }
            )
        return segments


def transcribe_with_openai_whisper(video: VideoItem, model_name: str, device: str, ffmpeg_dir: str | None) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix=f"zxj_{video.bvid}_") as td:
        tmpdir = Path(td)
        audio = download_audio(video, tmpdir, ffmpeg_dir)

        import whisper

        model_key = f"openai_whisper_{model_name}_{device}"
        model = getattr(thread_local, model_key, None)
        if model is None:
            log(f"加载 openai-whisper 模型: {model_name} device={device}")
            model = whisper.load_model(model_name, device=device)
            setattr(thread_local, model_key, model)

        result = model.transcribe(
            str(audio),
            language="zh",
            fp16=False,
            initial_prompt=(
                "这是一档中文商业科技深度访谈，常见词包括 AI、Agent、OpenAI、Anthropic、Gemini、"
                "DeepMind、Kimi、Manus、OpenClaw、世界模型、具身智能、大模型、创业、投资。"
            ),
        )
        segments = []
        for seg in result.get("segments", []):
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            segments.append(
                {
                    "start": float(seg.get("start", 0)),
                    "end": float(seg.get("end", seg.get("start", 0))),
                    "text": text,
                    "source": "openai-whisper",
                    "model": model_name,
                    "language": result.get("language", "zh"),
                    "device": device,
                }
            )
        return segments


def fmt_ts(seconds: float) -> str:
    total = int(seconds)
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    if h:
        return f"[{h}:{m:02d}:{s:02d}]"
    return f"[{m}:{s:02d}]"


def fmt_srt_ts(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    s = total % 60
    m = (total // 60) % 60
    h = total // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def render_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for i, seg in enumerate(segments, 1):
        start = fmt_srt_ts(float(seg["start"]))
        end = fmt_srt_ts(float(seg.get("end", seg["start"])))
        blocks.append(f"{i}\n{start} --> {end}\n{seg['text']}")
    return "\n\n".join(blocks) + "\n"


def write_outputs(video: VideoItem, segments: list[dict[str, Any]], method: str, model: str) -> Path:
    paths = output_paths(video)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "up_name": UP_NAME,
        "up_mid": UP_MID,
        "bvid": video.bvid,
        "aid": video.aid,
        "url": video.url,
        "title": video.title,
        "published_at": video.created_date,
        "length": video.length,
        "is_interview": video.is_interview,
        "method": method,
        "model": model if method == "faster-whisper" else "",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "segments": segments,
    }
    save_json(paths["json"], payload)
    paths["srt"].write_text(render_srt(segments), encoding="utf-8")

    lines = [
        f"# {video.title}",
        "",
        f"- **UP主**: {UP_NAME}",
        f"- **来源**: {video.url}",
        f"- **BV号**: {video.bvid}",
        f"- **发布时间**: {video.created_date}",
        f"- **时长**: {video.length}",
        f"- **提取方式**: {method}" + (f" ({model})" if method in {"faster-whisper", "openai-whisper"} else ""),
        f"- **提取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
    ]
    lines.extend(f"{fmt_ts(float(seg['start']))} {seg['text']}" for seg in segments)
    paths["md"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths["md"]


def collect_existing_done(videos: list[VideoItem]) -> set[str]:
    done = set()
    for video in videos:
        md = output_paths(video)["md"]
        if md.exists() and md.stat().st_size > 1000:
            done.add(video.bvid)
    return done


def process_one(video: VideoItem, args: argparse.Namespace, ffmpeg_dir: str | None) -> dict[str, Any]:
    paths = output_paths(video)
    if not args.force and paths["md"].exists() and paths["md"].stat().st_size > 1000:
        return {"bvid": video.bvid, "status": "skip", "file": str(paths["md"])}

    started = time.time()
    try:
        segments = []
        method = "bilibili-subtitle"
        if not args.force_whisper:
            segments = try_official_subtitle(video)

        if not segments:
            if args.no_whisper:
                raise RuntimeError("no official subtitle and --no-whisper was set")
            if args.engine == "openai-whisper":
                method = "openai-whisper"
                segments = transcribe_with_openai_whisper(video, args.model, args.device, ffmpeg_dir)
            else:
                method = "faster-whisper"
                segments = transcribe_with_faster_whisper(video, args.model, args.cpu_threads, ffmpeg_dir)

        if not segments:
            raise RuntimeError("empty transcript")

        out = write_outputs(video, segments, method, args.model)
        return {
            "bvid": video.bvid,
            "status": "ok",
            "method": method,
            "file": str(out),
            "seconds": round(time.time() - started, 1),
            "segments": len(segments),
        }
    except Exception as exc:
        return {"bvid": video.bvid, "status": "fail", "error": str(exc)[-1200:]}


def select_videos(args: argparse.Namespace) -> list[VideoItem]:
    selected = VIDEOS if args.all_videos else [v for v in VIDEOS if v.is_interview]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        selected = [v for v in selected if v.bvid in wanted or str(v.seq) in wanted]
    if args.start:
        selected = [v for v in selected if v.seq >= args.start]
    if args.end:
        selected = [v for v in selected if v.seq <= args.end]
    return selected


def write_index(selected: list[VideoItem], all_videos: bool) -> None:
    payload = {
        "up_name": UP_NAME,
        "up_mid": UP_MID,
        "space_url": f"https://space.bilibili.com/{UP_MID}/video",
        "source_checked_at": "2026-05-11",
        "mode": "all_videos" if all_videos else "interviews_only",
        "selected_count": len(selected),
        "total_known_videos": len(VIDEOS),
        "videos": [
            {
                "seq": v.seq,
                "bvid": v.bvid,
                "aid": v.aid,
                "title": v.title,
                "created": v.created,
                "created_date": v.created_date,
                "length": v.length,
                "play": v.play,
                "comment": v.comment,
                "is_interview": v.is_interview,
                "url": v.url,
            }
            for v in VIDEOS
        ],
    }
    save_json(INDEX_FILE, payload)


def show_status(args: argparse.Namespace) -> None:
    selected = select_videos(args)
    progress = load_json(PROGRESS_FILE, {})
    done = collect_existing_done(selected)
    failed = progress.get("failed", [])
    print(f"UP主: {UP_NAME}")
    print(f"模式: {'全部视频' if args.all_videos else '仅访谈'}")
    print(f"选中: {len(selected)} / 已知投稿: {len(VIDEOS)}")
    print(f"已完成文件: {len(done)}")
    print(f"失败记录: {len(failed)}")
    print(f"输出目录: {BASE_DIR}")
    if failed:
        print("\n最近失败:")
        for item in failed[-10:]:
            print(f"  {item.get('bvid')}: {item.get('error', '')[:160]}")


def run_batch(args: argparse.Namespace) -> None:
    add_runtime_paths()
    selected = select_videos(args)
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "srt").mkdir(exist_ok=True)
    (BASE_DIR / "json").mkdir(exist_ok=True)
    write_index(selected, args.all_videos)

    ffmpeg_dir = find_ffmpeg_dir()
    if not ffmpeg_dir and not args.no_whisper:
        raise RuntimeError("ffmpeg not found; cannot run Whisper fallback")

    progress = load_json(PROGRESS_FILE, {"done": [], "failed": []})
    done = set(progress.get("done", [])) | collect_existing_done(selected)
    failed = [f for f in progress.get("failed", []) if f.get("bvid") not in done]
    tasks = [v for v in selected if args.force or v.bvid not in done]

    log(f"启动任务: mode={'all' if args.all_videos else 'interviews'}, selected={len(selected)}, pending={len(tasks)}, workers={args.workers}, engine={args.engine}, model={args.model}, ffmpeg_dir={ffmpeg_dir}")
    if not tasks:
        log("没有待处理任务")
        return

    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_one, video, args, ffmpeg_dir): video for video in tasks}
        for future in as_completed(futures):
            video = futures[future]
            completed += 1
            result = future.result()
            if result["status"] in {"ok", "skip"}:
                done.add(video.bvid)
                failed = [f for f in failed if f.get("bvid") != video.bvid]
                log(f"[{completed}/{len(tasks)}] OK {video.bvid} {result.get('method', result['status'])} {video.title[:50]}")
            else:
                failed.append({"bvid": video.bvid, "title": video.title, "error": result.get("error", "")})
                log(f"[{completed}/{len(tasks)}] FAIL {video.bvid} {video.title[:50]} :: {result.get('error', '')[:240]}")

            progress = {
                "done": sorted(done),
                "failed": failed,
                "last_update": datetime.now().isoformat(timespec="seconds"),
                "selected_count": len(selected),
                "mode": "all_videos" if args.all_videos else "interviews_only",
            }
            save_json(PROGRESS_FILE, progress)

    log(f"任务结束: done={len(done)}, failed={len(failed)}, output={BASE_DIR}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract 张小珺商业访谈录 transcripts from Bilibili.")
    parser.add_argument("--run", action="store_true", help="run extraction")
    parser.add_argument("--status", action="store_true", help="show progress")
    parser.add_argument("--all-videos", action="store_true", help="include non-interview explainer videos")
    parser.add_argument("--only", default="", help="comma-separated seq or BV ids to run")
    parser.add_argument("--start", type=int, default=0, help="minimum original sequence number")
    parser.add_argument("--end", type=int, default=0, help="maximum original sequence number")
    parser.add_argument("--workers", type=int, default=1, help="parallel workers")
    parser.add_argument("--engine", choices=["faster-whisper", "openai-whisper"], default="faster-whisper", help="ASR engine for Whisper fallback")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="faster-whisper model")
    parser.add_argument("--device", default="cpu", help="device for openai-whisper, e.g. cpu or mps")
    parser.add_argument("--cpu-threads", type=int, default=4, help="CPU threads per worker")
    parser.add_argument("--force", action="store_true", help="overwrite existing transcript files")
    parser.add_argument("--force-whisper", action="store_true", help="skip official subtitle attempt")
    parser.add_argument("--no-whisper", action="store_true", help="only try official Bilibili subtitles")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.status:
        show_status(args)
        return 0
    if args.run:
        run_batch(args)
        return 0
    print("Use --run to extract or --status to inspect progress.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
