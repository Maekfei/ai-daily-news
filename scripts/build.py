#!/usr/bin/env python3
"""
Build static site from markdown posts.

Outputs:
  data.json              — recent 30 days, lightweight index for SPA cold start
  data/<date>.json       — per-day full data (lazy loaded)
  data/index.json        — list of all dates + counts (for sidebar)
  data/keywords.json     — past-7-day keyword frequency (sidebar word cloud)
  feed.xml               — RSS 2.0 feed
  sitemap.xml            — Sitemap for search engines
  og/<date>.svg          — Open Graph card per post (rendered as SVG, GH Pages serves)
  index.html             — SPA shell with prerendered hero meta for crawlers
"""
import json
import os
import re
import sys
import html
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
DATA_DIR = ROOT / "data"
OG_DIR = ROOT / "og"
SITE_URL = "https://maekfei.github.io/ai-daily-news"
SITE_TITLE = "AI 每日要闻"
SITE_DESC = "聚焦 AI Agent / 智能体的每日行业要闻精选 — 每日 10:00 自动更新"

# Section icon/title -> kind
SECTION_MAP = {
    "Agent 重点": "hero",
    "大模型 & 行业动态": "mini",
    "大模型": "mini",
    "行业动态": "mini",
    "行业": "mini",
    "一句话快讯": "quick",
    "快讯": "quick",
}

# Stop words for keyword extraction
STOP = set("""
的 了 在 是 我 有 和 就 不 人 都 一 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己
这 那 与 及 或 但 而 之 与其 以及 等 被 把 让 已 已经 还 又 也 再 从 向 对 由
公司 产品 模型 推出 发布 宣布 新 大 最 第 月 日 年 周
ai AI Ai a an the of in on at to for and or with by from as is are was be will
""".split())

POST_RE = re.compile(r"^# (.+?)\s*$", re.M)
SUMMARY_RE = re.compile(r"^>\s*(.+?)\s*$", re.M)
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)


def slugify(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", s, flags=re.UNICODE)
    s = s.strip("-").lower()
    return s[:maxlen] or "item"


def parse_post(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    date = path.stem  # YYYY-MM-DD

    title_m = POST_RE.search(text)
    title = title_m.group(1).strip() if title_m else date

    summary_m = SUMMARY_RE.search(text)
    summary = summary_m.group(1).strip() if summary_m else ""

    sections = []
    matches = list(SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        section_title = m.group(1).strip()
        # Strip emoji prefix for matching
        bare = re.sub(r"^[^\w\u4e00-\u9fff]+", "", section_title).strip()
        kind = SECTION_MAP.get(bare, "mini")
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        items = parse_section_items(body, kind, date, idx_offset=i * 100)
        sections.append({
            "title": section_title,
            "kind": kind,
            "items": items,
        })
    return {
        "date": date,
        "title": title,
        "summary": summary,
        "sections": sections,
    }


def parse_section_items(body: str, kind: str, date: str, idx_offset: int) -> list:
    """Parse list items.
    Strategy:
      - If section has any '### N.' or '#### N.' heading, treat ONLY those as
        top-level items (sub-bullets become item body).
      - Else, treat lines starting with '1. ', '- ', or '* ' as items.
    """
    items = []
    lines = body.split("\n")
    has_h3 = any(re.match(r"^\s*#{2,4}\s+\d+[.)、]?\s+", ln) for ln in lines)

    if has_h3:
        head_re = re.compile(r"^\s*#{2,4}\s+\d+[.)、]?\s+")
    else:
        head_re = re.compile(r"^\s*(?:\d+[.)、]|[-*])\s+")

    cur = []
    seq = 0
    for ln in lines:
        if head_re.match(ln):
            if cur:
                items.append(_make_item(cur, kind, date, idx_offset + seq))
                seq += 1
            stripped = head_re.sub("", ln)
            cur = [stripped]
        elif cur:
            cur.append(ln)
    if cur:
        items.append(_make_item(cur, kind, date, idx_offset + seq))
    return items


def _make_item(lines, kind, date, seq):
    raw = "\n".join(lines).strip()
    # Find ALL links
    link_re = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    links = [{"text": m.group(1), "url": m.group(2)} for m in link_re.finditer(raw)]
    # Stripped text (no markdown links, keep visible text)
    stripped = link_re.sub(lambda m: m.group(1), raw)
    # Drop bare 🔗 prefix lines and clean leading bullets/heading marks
    cleaned_lines = []
    for ln in stripped.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        # Drop pure-link 🔗 line (already captured via links[])
        if re.match(r"^🔗\s*$", ln):
            continue
        # Strip leading bullet/dash
        ln = re.sub(r"^[-*]\s+", "", ln)
        # Strip leading 🔗 emoji
        ln = re.sub(r"^🔗\s*", "", ln)
        # Strip ### heading markers
        ln = re.sub(r"^#{2,4}\s+", "", ln)
        # Convert **bold** to plain (we'll style in CSS instead)
        ln = re.sub(r"\*\*(.+?)\*\*", r"\1", ln)
        cleaned_lines.append(ln)

    headline = cleaned_lines[0] if cleaned_lines else ""
    body_parts = cleaned_lines[1:] if len(cleaned_lines) > 1 else []
    # Filter empty / link-only lines from body
    body_parts = [p for p in body_parts if p and not re.match(r"^https?://", p)]
    body = " · ".join(body_parts) if body_parts else ""

    anchor = slugify(headline)
    return {
        "id": f"{kind}-{seq}-{anchor}",
        "kind": kind,
        "headline": headline,
        "body": body,
        "links": links,
        "primary_link": links[0]["url"] if links else "",
        "raw": raw,
    }


def extract_keywords(posts: list, days: int = 7, top_n: int = 20) -> list:
    """Word-frequency over recent N days."""
    cutoff = datetime.now() - timedelta(days=days)
    counter = Counter()
    for p in posts:
        try:
            d = datetime.strptime(p["date"], "%Y-%m-%d")
        except ValueError:
            continue
        if d < cutoff:
            continue
        for s in p["sections"]:
            for it in s["items"]:
                text = it["headline"] + " " + it["body"]
                # Tokenize: keep CJK words of len>=2 + ASCII words len>=2
                tokens = re.findall(r"[A-Za-z][A-Za-z0-9.+\-]{1,}|[\u4e00-\u9fff]{2,8}", text)
                for t in tokens:
                    tl = t.lower()
                    if tl in STOP or len(t) < 2:
                        continue
                    counter[t] += 1
    return [{"word": w, "count": c} for w, c in counter.most_common(top_n)]


def render_feed(posts: list) -> str:
    """RSS 2.0."""
    items_xml = []
    for p in posts[:30]:
        url = f"{SITE_URL}/#/{p['date']}"
        # Build a brief description from summary + first 3 headlines
        desc_parts = [p["summary"]] if p["summary"] else []
        count = 0
        for s in p["sections"]:
            for it in s["items"]:
                if count >= 5:
                    break
                desc_parts.append(f"• {it['headline']}")
                count += 1
        desc = "\n".join(desc_parts)
        try:
            pub = datetime.strptime(p["date"], "%Y-%m-%d").replace(hour=10, tzinfo=timezone(timedelta(hours=8)))
            pub_rfc = pub.strftime("%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            pub_rfc = ""
        items_xml.append(f"""    <item>
      <title>{html.escape(p['title'])}</title>
      <link>{url}</link>
      <guid isPermaLink="false">{p['date']}</guid>
      <pubDate>{pub_rfc}</pubDate>
      <description>{html.escape(desc)}</description>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{html.escape(SITE_TITLE)}</title>
    <link>{SITE_URL}/</link>
    <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>{html.escape(SITE_DESC)}</description>
    <language>zh-CN</language>
    <lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""


def render_sitemap(posts: list) -> str:
    urls = [f"{SITE_URL}/"]
    for p in posts:
        urls.append(f"{SITE_URL}/#/{p['date']}")
    items = "\n".join(
        f"  <url><loc>{html.escape(u)}</loc></url>" for u in urls
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{items}
</urlset>
"""


def render_og_svg(post: dict) -> str:
    """Generate an Open Graph card as SVG (1200x630)."""
    title = html.escape(post["title"])
    summary = html.escape(post["summary"])[:120]
    date = post["date"]
    # Pick top 3 hero items
    bullets = []
    for s in post["sections"]:
        if s["kind"] == "hero":
            for it in s["items"][:3]:
                bullets.append(html.escape(it["headline"][:50]))
            break
    if not bullets:
        for s in post["sections"]:
            for it in s["items"][:3]:
                bullets.append(html.escape(it["headline"][:50]))
            if bullets:
                break
    bullet_svg = ""
    for i, b in enumerate(bullets[:3]):
        y = 380 + i * 56
        bullet_svg += f'<text x="80" y="{y}" font-size="28" fill="#cbd5e1" font-family="system-ui,sans-serif">• {b}</text>\n'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0f172a"/>
      <stop offset="1" stop-color="#1e1b4b"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#a78bfa"/>
      <stop offset="0.5" stop-color="#f472b6"/>
      <stop offset="1" stop-color="#22d3ee"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="0" y="0" width="1200" height="6" fill="url(#accent)"/>
  <text x="80" y="120" font-size="24" fill="#94a3b8" font-family="system-ui,sans-serif">AI 每日要闻 · {date}</text>
  <text x="80" y="200" font-size="56" font-weight="700" fill="#f8fafc" font-family="system-ui,sans-serif">{title}</text>
  <text x="80" y="270" font-size="26" fill="#cbd5e1" font-family="system-ui,sans-serif">{summary}</text>
  <line x1="80" y1="320" x2="1120" y2="320" stroke="#334155" stroke-width="1"/>
  {bullet_svg}
  <text x="80" y="580" font-size="22" fill="#64748b" font-family="system-ui,sans-serif">maekfei.github.io/ai-daily-news</text>
</svg>
"""


def render_index_html(posts: list) -> str:
    """SPA shell with SEO meta. The first post drives default OG."""
    latest = posts[0] if posts else None
    title = SITE_TITLE
    desc = SITE_DESC
    og_image = f"{SITE_URL}/og/default.svg"
    if latest:
        title = f"{latest['title']} · {SITE_TITLE}"
        desc = latest["summary"] or SITE_DESC
        og_image = f"{SITE_URL}/og/{latest['date']}.svg"

    return f"""<!doctype html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}"/>
<link rel="canonical" href="{SITE_URL}/"/>
<meta property="og:title" content="{html.escape(title)}"/>
<meta property="og:description" content="{html.escape(desc)}"/>
<meta property="og:image" content="{og_image}"/>
<meta property="og:type" content="website"/>
<meta property="og:url" content="{SITE_URL}/"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{html.escape(title)}"/>
<meta name="twitter:description" content="{html.escape(desc)}"/>
<meta name="twitter:image" content="{og_image}"/>
<link rel="alternate" type="application/rss+xml" title="{html.escape(SITE_TITLE)}" href="{SITE_URL}/feed.xml"/>
<link rel="stylesheet" href="assets/style.css"/>
<script defer src="assets/app.js"></script>
<!-- GoatCounter privacy-friendly analytics -->
<script data-goatcounter="https://maekfei-ai-news.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</head>
<body>
<a class="skip" href="#main">跳到主内容</a>
<header class="topbar">
  <div class="topbar-inner">
    <div class="brand">
      <span class="brand-mark">⚡</span>
      <span class="brand-text"><strong>AI 每日要闻</strong><em>Agent 重点 · 每日 10:00</em></span>
    </div>
    <div class="search-wrap">
      <input id="q" type="search" placeholder="搜索新闻、产品、关键词…   按 / 聚焦" autocomplete="off"/>
      <kbd class="kbd">/</kbd>
    </div>
    <div class="topbar-actions">
      <button id="theme-toggle" class="icon-btn" title="切换主题" aria-label="切换主题">🌗</button>
      <a class="icon-btn" href="feed.xml" title="RSS 订阅" aria-label="RSS">📡</a>
      <a class="icon-btn" href="https://github.com/Maekfei/ai-daily-news" title="GitHub" aria-label="GitHub" target="_blank" rel="noopener">⌘</a>
    </div>
  </div>
</header>
<div class="layout">
  <aside class="sidebar" id="sidebar">
    <div class="sidebar-section">
      <div class="sidebar-title">归档</div>
      <nav id="dates"></nav>
    </div>
    <div class="sidebar-section">
      <div class="sidebar-title">分类</div>
      <div id="filters" class="chips">
        <button class="chip active" data-filter="all">全部</button>
        <button class="chip" data-filter="hero">🎯 Agent</button>
        <button class="chip" data-filter="mini">📰 大模型/行业</button>
        <button class="chip" data-filter="quick">💡 快讯</button>
      </div>
    </div>
    <div class="sidebar-section">
      <div class="sidebar-title">本周热词 <span class="muted">(7天)</span></div>
      <div id="cloud" class="cloud"></div>
    </div>
    <div class="sidebar-section sidebar-about">
      <div class="sidebar-title">关于</div>
      <p class="muted small">每日 10:00 (UTC+8) 自动汇编，重点关注 AI Agent / 智能体生态。内容由 AI 整理，建议核实原文。</p>
      <p class="muted small">数据归档：<a href="https://github.com/Maekfei/ai-daily-news" target="_blank" rel="noopener">GitHub</a></p>
    </div>
  </aside>
  <main id="main" class="main">
    <div id="content"></div>
    <footer class="page-footer">
      <p>内容由 AI 自动整理，仅供参考。Built by <a href="https://github.com/Maekfei" target="_blank" rel="noopener">Maekfei</a> · <a href="feed.xml">RSS</a> · <a href="https://github.com/Maekfei/ai-daily-news" target="_blank" rel="noopener">源码</a></p>
    </footer>
  </main>
</div>
<div id="toast" class="toast" role="status" aria-live="polite"></div>
</body>
</html>
"""


def main():
    DATA_DIR.mkdir(exist_ok=True)
    OG_DIR.mkdir(exist_ok=True)

    md_files = sorted(POSTS_DIR.glob("*.md"), reverse=True)
    posts = []
    for f in md_files:
        if f.name == ".gitkeep":
            continue
        try:
            p = parse_post(f)
            posts.append(p)
            counts = {}
            for s in p["sections"]:
                counts[s["kind"]] = counts.get(s["kind"], 0) + len(s["items"])
            print(f"  ✓ {p['date']}  · {counts}")
        except Exception as e:
            print(f"  ✗ {f.name}: {e}", file=sys.stderr)

    posts.sort(key=lambda x: x["date"], reverse=True)

    # Per-day full data
    for p in posts:
        (DATA_DIR / f"{p['date']}.json").write_text(
            json.dumps(p, ensure_ascii=False, indent=None),
            encoding="utf-8",
        )

    # Index of dates (lightweight, for sidebar)
    index = [
        {
            "date": p["date"],
            "title": p["title"],
            "summary": p["summary"],
            "counts": {
                "hero": sum(len(s["items"]) for s in p["sections"] if s["kind"] == "hero"),
                "mini": sum(len(s["items"]) for s in p["sections"] if s["kind"] == "mini"),
                "quick": sum(len(s["items"]) for s in p["sections"] if s["kind"] == "quick"),
            },
        }
        for p in posts
    ]
    (DATA_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False),
        encoding="utf-8",
    )

    # Recent 30 days bundled (for cold-start search)
    recent = posts[:30]
    (ROOT / "data.json").write_text(
        json.dumps({"posts": recent, "generated_at": datetime.now(timezone.utc).isoformat()},
                   ensure_ascii=False),
        encoding="utf-8",
    )

    # Keywords (7-day rolling)
    keywords = extract_keywords(posts, days=7, top_n=24)
    (DATA_DIR / "keywords.json").write_text(
        json.dumps(keywords, ensure_ascii=False),
        encoding="utf-8",
    )

    # Feed and sitemap
    (ROOT / "feed.xml").write_text(render_feed(posts), encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(render_sitemap(posts), encoding="utf-8")

    # OG images
    if posts:
        # Default = latest
        (OG_DIR / "default.svg").write_text(render_og_svg(posts[0]), encoding="utf-8")
    for p in posts:
        (OG_DIR / f"{p['date']}.svg").write_text(render_og_svg(p), encoding="utf-8")

    # SPA shell
    (ROOT / "index.html").write_text(render_index_html(posts), encoding="utf-8")

    print(f"  ✓ data.json   ({len(recent)} recent of {len(posts)})")
    print(f"  ✓ data/index.json + data/<date>.json × {len(posts)}")
    print(f"  ✓ data/keywords.json ({len(keywords)} words)")
    print(f"  ✓ feed.xml, sitemap.xml")
    print(f"  ✓ og/*.svg × {len(posts) + 1}")
    print(f"  ✓ index.html (SPA shell)")


if __name__ == "__main__":
    main()
