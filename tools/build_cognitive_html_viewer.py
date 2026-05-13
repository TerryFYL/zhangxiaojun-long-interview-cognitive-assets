#!/usr/bin/env python3
"""Build a standalone HTML viewer for long-material cognitive assets."""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime
from pathlib import Path

import markdown


SECTION_TITLES = [
    "访谈内容",
    "知识增量",
    "认识变化",
    "Terry 可能的原默认判断",
    "可迁移模型",
    "行动修正",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def parse_cognitive_cards(markdown_text: str) -> list[dict[str, str]]:
    pattern = re.compile(r"^## CB-(\d+)\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(markdown_text))
    cards: list[dict[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown_text)
        block = markdown_text[start:end].strip()
        card: dict[str, str] = {
            "id": f"CB-{int(match.group(1)):03d}",
            "title": match.group(2).strip(),
            "source": "",
            "episode": "",
            "insufficiency": "",
            "verification": "",
        }
        for key, label in [
            ("source", "来源"),
            ("episode", "集数"),
            ("insufficiency", "不足类型"),
            ("verification", "复核状态"),
        ]:
            m = re.search(rf"^- {label}：(.+)$", block, re.MULTILINE)
            if m:
                card[key] = m.group(1).strip()

        for section in SECTION_TITLES:
            section_pattern = re.compile(
                rf"\*\*{re.escape(section)}\*\*\s*(.*?)(?=\n\*\*(?:{'|'.join(map(re.escape, SECTION_TITLES))})\*\*|\Z)",
                re.DOTALL,
            )
            m = section_pattern.search(block)
            card[section] = m.group(1).strip() if m else ""
        cards.append(card)
    return cards


def render_markdown(markdown_text: str) -> str:
    if not markdown_text:
        return "<p class=\"muted\">暂无内容。</p>"
    return markdown.markdown(markdown_text, extensions=["tables", "fenced_code", "toc"])


def build_html(synthesis_dir: Path, title: str) -> str:
    cards_md = read_text(synthesis_dir / "cognitive_boundary_cards.md")
    cards = parse_cognitive_cards(cards_md)
    docs = {
        "design": {
            "label": "处理设计",
            "html": render_markdown(read_text(synthesis_dir / "material_processing_design.md")),
        },
        "container": {
            "label": "容器分析",
            "html": render_markdown(read_text(synthesis_dir / "interview_container_analysis.md")),
        },
        "question": {
            "label": "问题深度",
            "html": render_markdown(read_text(synthesis_dir / "question_depth_framework.md")),
        },
        "protocol": {
            "label": "挖掘协议",
            "html": render_markdown(read_text(synthesis_dir / "long_interview_mining_protocol.md")),
        },
    }
    types = sorted({c["insufficiency"] for c in cards if c["insufficiency"]})
    episodes = sorted({c["episode"] for c in cards if c["episode"]})
    counts: dict[str, int] = {}
    for c in cards:
        counts[c["insufficiency"]] = counts.get(c["insufficiency"], 0) + 1
    max_count = max(counts.values()) if counts else 1

    cards_json = json.dumps(cards, ensure_ascii=False)
    docs_json = json.dumps(docs, ensure_ascii=False)
    type_options = "\n".join(f"<option value=\"{html.escape(t)}\">{html.escape(t)}</option>" for t in types)
    episode_options = "\n".join(f"<option value=\"{html.escape(e)}\">{html.escape(e)}</option>" for e in episodes)
    bars = "\n".join(
        f"""
        <div class="bar-row">
          <span>{html.escape(k)}</span>
          <div class="bar-track"><div class="bar-fill" style="width:{(v / max_count) * 100:.1f}%"></div></div>
          <strong>{v}</strong>
        </div>
        """
        for k, v in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f5ef;
      --panel: #fffefa;
      --panel-2: #f0f6f4;
      --ink: #20211f;
      --muted: #6b6f72;
      --line: #d7d6ce;
      --accent: #0f766e;
      --accent-2: #b45309;
      --accent-soft: #e1f2ee;
      --shadow: 0 12px 28px rgba(33, 35, 32, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.65;
      letter-spacing: 0;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 10;
      border-bottom: 1px solid var(--line);
      background: rgba(247, 245, 239, 0.94);
      backdrop-filter: blur(14px);
    }}
    .topbar {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 18px 28px 14px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 20px;
      align-items: end;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.25;
      font-weight: 760;
    }}
    .subtitle {{
      margin-top: 5px;
      color: var(--muted);
      font-size: 13px;
    }}
    .tabs {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    button, select, input {{
      font: inherit;
    }}
    .tab, .control-button {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      border-radius: 7px;
      padding: 8px 11px;
      cursor: pointer;
      min-height: 38px;
    }}
    .tab.active, .control-button.active {{
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }}
    main {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px 28px 48px;
    }}
    .cards-layout {{
      display: grid;
      grid-template-columns: minmax(260px, 320px) 1fr;
      gap: 20px;
      align-items: start;
    }}
    aside {{
      position: sticky;
      top: 94px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      box-shadow: var(--shadow);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }}
    .stat {{
      background: var(--panel-2);
      border: 1px solid #d7e7e2;
      border-radius: 8px;
      padding: 10px;
    }}
    .stat strong {{
      display: block;
      font-size: 24px;
      line-height: 1;
      color: var(--accent);
    }}
    .stat span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .filter-stack {{
      display: grid;
      gap: 10px;
    }}
    .filter-stack label {{
      display: grid;
      gap: 5px;
      font-size: 12px;
      color: var(--muted);
    }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: white;
      min-height: 38px;
      padding: 8px 10px;
      color: var(--ink);
    }}
    .bar-chart {{
      display: grid;
      gap: 8px;
      margin-top: 16px;
      padding-top: 14px;
      border-top: 1px solid var(--line);
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: 70px 1fr 22px;
      gap: 8px;
      align-items: center;
      font-size: 12px;
      color: var(--muted);
    }}
    .bar-track {{
      height: 8px;
      border-radius: 99px;
      background: #e4e0d6;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      background: var(--accent-2);
    }}
    .card-list {{
      display: grid;
      gap: 12px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .card summary {{
      list-style: none;
      cursor: pointer;
      padding: 16px 18px;
    }}
    .card summary::-webkit-details-marker {{ display: none; }}
    .card-title {{
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 10px;
      align-items: start;
    }}
    .card-id {{
      color: var(--accent);
      font-weight: 760;
      font-size: 13px;
      white-space: nowrap;
      margin-top: 2px;
    }}
    .card h2 {{
      margin: 0;
      font-size: 17px;
      line-height: 1.45;
      font-weight: 720;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      min-height: 25px;
      padding: 2px 8px;
      border-radius: 99px;
      background: var(--accent-soft);
      color: #0f5f59;
      font-size: 12px;
      white-space: nowrap;
    }}
    .meta {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
    }}
    .card-body {{
      padding: 0 18px 18px;
      display: grid;
      gap: 12px;
    }}
    .section-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .field {{
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }}
    .field.full {{ grid-column: 1 / -1; }}
    .field h3 {{
      margin: 0 0 4px;
      font-size: 12px;
      color: var(--accent-2);
      text-transform: none;
    }}
    .field p {{
      margin: 0;
      font-size: 14px;
    }}
    .doc-view {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 26px;
      box-shadow: var(--shadow);
      max-width: 1060px;
    }}
    .doc-view h1 {{ font-size: 24px; }}
    .doc-view h2 {{
      margin-top: 28px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      font-size: 20px;
    }}
    .doc-view h3 {{ font-size: 16px; color: var(--accent); }}
    .doc-view table {{
      width: 100%;
      border-collapse: collapse;
      margin: 14px 0;
      font-size: 14px;
    }}
    .doc-view th, .doc-view td {{
      border: 1px solid var(--line);
      padding: 8px 10px;
      vertical-align: top;
    }}
    .doc-view th {{ background: var(--panel-2); }}
    .doc-view code, .doc-view pre {{
      background: #f0eee6;
      border-radius: 6px;
    }}
    .doc-view code {{ padding: 1px 4px; }}
    .doc-view pre {{
      padding: 12px;
      overflow-x: auto;
    }}
    .muted {{ color: var(--muted); }}
    .empty {{
      padding: 40px;
      text-align: center;
      color: var(--muted);
      background: var(--panel);
      border: 1px dashed var(--line);
      border-radius: 8px;
    }}
    @media (max-width: 900px) {{
      .topbar {{ grid-template-columns: 1fr; align-items: start; }}
      .tabs {{ justify-content: flex-start; }}
      .cards-layout {{ grid-template-columns: 1fr; }}
      aside {{ position: static; }}
      .section-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div>
        <h1>{html.escape(title)}</h1>
        <div class="subtitle">认知 = 知识 + 认识；用于筛选知识增量、认识变化和行动修正。生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
      </div>
      <nav class="tabs" aria-label="视图切换">
        <button class="tab active" data-tab="cards">认知卡片</button>
        <button class="tab" data-tab="container">容器分析</button>
        <button class="tab" data-tab="question">问题深度</button>
        <button class="tab" data-tab="protocol">挖掘协议</button>
        <button class="tab" data-tab="design">处理设计</button>
      </nav>
    </div>
  </header>

  <main>
    <section id="cardsPane" class="pane">
      <div class="cards-layout">
        <aside>
          <div class="stats">
            <div class="stat"><strong>{len(cards)}</strong><span>认知边界卡</span></div>
            <div class="stat"><strong>{len(episodes)}</strong><span>来源集数</span></div>
          </div>
          <div class="filter-stack">
            <label>搜索
              <input id="searchInput" type="search" placeholder="搜索标题、知识增量、认识变化、行动修正">
            </label>
            <label>不足类型
              <select id="typeFilter">
                <option value="">全部类型</option>
                {type_options}
              </select>
            </label>
            <label>集数
              <select id="episodeFilter">
                <option value="">全部集数</option>
                {episode_options}
              </select>
            </label>
            <button id="expandAll" class="control-button" type="button">展开全部</button>
          </div>
          <div class="bar-chart" aria-label="不足类型分布">
            {bars}
          </div>
        </aside>
        <section>
          <div id="resultMeta" class="subtitle" style="margin-bottom: 12px;"></div>
          <div id="cardList" class="card-list"></div>
        </section>
      </div>
    </section>
    <section id="docPane" class="pane" hidden>
      <article id="docContent" class="doc-view"></article>
    </section>
  </main>

  <script>
    const cards = {cards_json};
    const docs = {docs_json};
    const state = {{ tab: 'cards', expanded: false }};
    const fields = ['访谈内容', '知识增量', '认识变化', 'Terry 可能的原默认判断', '可迁移模型', '行动修正'];

    const cardList = document.getElementById('cardList');
    const resultMeta = document.getElementById('resultMeta');
    const searchInput = document.getElementById('searchInput');
    const typeFilter = document.getElementById('typeFilter');
    const episodeFilter = document.getElementById('episodeFilter');
    const expandAll = document.getElementById('expandAll');
    const cardsPane = document.getElementById('cardsPane');
    const docPane = document.getElementById('docPane');
    const docContent = document.getElementById('docContent');

    function escapeHtml(value) {{
      return String(value || '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }}

    function cardMatches(card) {{
      const q = searchInput.value.trim().toLowerCase();
      const type = typeFilter.value;
      const episode = episodeFilter.value;
      if (type && card.insufficiency !== type) return false;
      if (episode && card.episode !== episode) return false;
      if (!q) return true;
      const haystack = [card.id, card.title, card.source, card.episode, card.insufficiency, ...fields.map(f => card[f])]
        .join('\\n')
        .toLowerCase();
      return haystack.includes(q);
    }}

    function renderCards() {{
      const filtered = cards.filter(cardMatches);
      resultMeta.textContent = `显示 ${{filtered.length}} / ${{cards.length}} 张卡片`;
      if (!filtered.length) {{
        cardList.innerHTML = '<div class="empty">没有匹配的认知卡片。</div>';
        return;
      }}
      cardList.innerHTML = filtered.map((card, index) => {{
        const fieldHtml = fields.map((field, fieldIndex) => `
          <div class="field ${{fieldIndex < 3 ? 'full' : ''}}">
            <h3>${{escapeHtml(field)}}</h3>
            <p>${{escapeHtml(card[field])}}</p>
          </div>
        `).join('');
        return `
          <details class="card" ${{state.expanded || index === 0 ? 'open' : ''}}>
            <summary>
              <div class="card-title">
                <span class="card-id">${{escapeHtml(card.id)}}</span>
                <h2>${{escapeHtml(card.title)}}</h2>
                <span class="badge">${{escapeHtml(card.insufficiency)}}</span>
              </div>
              <div class="meta">
                <span>${{escapeHtml(card.source)}}</span>
                <span>${{escapeHtml(card.verification)}}</span>
                <span>${{escapeHtml(card.episode)}}</span>
              </div>
            </summary>
            <div class="card-body">
              <div class="section-grid">${{fieldHtml}}</div>
            </div>
          </details>
        `;
      }}).join('');
    }}

    function showTab(tab) {{
      state.tab = tab;
      document.querySelectorAll('.tab').forEach(button => {{
        button.classList.toggle('active', button.dataset.tab === tab);
      }});
      if (tab === 'cards') {{
        cardsPane.hidden = false;
        docPane.hidden = true;
        renderCards();
        return;
      }}
      cardsPane.hidden = true;
      docPane.hidden = false;
      docContent.innerHTML = docs[tab]?.html || '<p class="muted">暂无内容。</p>';
    }}

    searchInput.addEventListener('input', renderCards);
    typeFilter.addEventListener('change', renderCards);
    episodeFilter.addEventListener('change', renderCards);
    expandAll.addEventListener('click', () => {{
      state.expanded = !state.expanded;
      expandAll.classList.toggle('active', state.expanded);
      expandAll.textContent = state.expanded ? '收起默认' : '展开全部';
      renderCards();
    }});
    document.querySelectorAll('.tab').forEach(button => {{
      button.addEventListener('click', () => showTab(button.dataset.tab));
    }});

    renderCards();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a standalone HTML workbench for cognitive assets.")
    parser.add_argument("--synthesis-dir", default="data/zhangxiaojun-transcripts/structured/synthesis")
    parser.add_argument("--output", default="", help="defaults to SYNTHESIS_DIR/index.html")
    parser.add_argument("--title", default="长素材认知代谢工作台")
    args = parser.parse_args()

    synthesis_dir = Path(args.synthesis_dir).expanduser().resolve()
    output = Path(args.output).expanduser().resolve() if args.output else synthesis_dir / "index.html"
    html_text = build_html(synthesis_dir, args.title)
    output.write_text(html_text, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
