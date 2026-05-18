#!/usr/bin/env python3
"""
Static site generator for ai-daily-news (Card UI v2).

Parses markdown files (posts/YYYY-MM-DD.md) into structured cards:
  - H1 = page title
  - blockquote = summary
  - H2 sections:
      "Agent 重点"        -> hero news cards (numbered, with 要点/详情/影响 fields)
      "大模型" / "行业动态" -> mini news grid
      "一句话快讯" / "快讯"  -> quick news list
  - Anything else falls back to a plain markdown render.
"""
from __future__ import annotations

import html
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    import markdown  # type: ignore
except ImportError:
    print("ERROR: pip install markdown", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")

# ---------------------------------------------------------------- helpers ----

def md_inline_to_html(text: str) -> str:
    """Convert a single line of markdown (links + bold) to safe HTML."""
    out = html.escape(text)
    # links must run before bold so that **[x](url)** still works
    out = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s\)]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2))}" target="_blank" rel="noopener">{m.group(1)}</a>',
        out,
    )
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def slugify(s: str) -> str:
    return re.sub(r"\s+", "-", s.strip().lower())[:30]


# ---------------------------------------------------------------- parser -----

def parse_post(md_text: str) -> dict:
    """Parse the markdown into a structured tree."""
    # strip optional YAML frontmatter
    if md_text.startswith("---\n"):
        end = md_text.find("\n---\n", 4)
        if end != -1:
            md_text = md_text[end + 5:]

    lines = md_text.splitlines()
    i = 0
    n = len(lines)

    title = None
    summary = None
    sections: list[dict] = []  # {kind, name, items}
    pre_section_lines: list[str] = []  # markdown before first H2

    # Phase 1: title & summary, then split by H2
    current_section: dict | None = None
    while i < n:
        line = lines[i]
        s = line.rstrip()
        if title is None and s.startswith("# "):
            title = s[2:].strip()
            i += 1
            continue
        if summary is None and s.startswith("> "):
            summary = s[2:].strip()
            i += 1
            continue
        if s.startswith("## "):
            name = s[3:].strip()
            kind = classify_section(name)
            current_section = {"kind": kind, "name": name, "lines": []}
            sections.append(current_section)
            i += 1
            continue
        if current_section is None:
            pre_section_lines.append(line)
        else:
            current_section["lines"].append(line)
        i += 1

    # Phase 2: parse contents of each section by kind
    for sec in sections:
        kind = sec["kind"]
        if kind == "hero":
            sec["items"] = parse_hero_items(sec["lines"])
        elif kind == "mini":
            sec["items"] = parse_mini_items(sec["lines"])
        elif kind == "quick":
            sec["items"] = parse_quick_items(sec["lines"])
        else:
            sec["items"] = []
            sec["raw_md"] = "\n".join(sec["lines"]).strip()

    return {
        "title": title or "AI 要闻",
        "summary": summary,
        "sections": sections,
        "pre_md": "\n".join(pre_section_lines).strip(),
    }


def classify_section(name: str) -> str:
    n = name.lower()
    if "agent" in n or "重点" in name or "焦点" in name or "要点" in name:
        return "hero"
    if "快讯" in name or "一句话" in name or "tldr" in n or "tldr" in name.lower():
        return "quick"
    if "大模型" in name or "行业" in name or "动态" in name or "其他" in name or "次要" in name:
        return "mini"
    return "other"


def parse_hero_items(lines: list[str]) -> list[dict]:
    """Each hero item starts with `### N. Title` and has bullet fields below."""
    items: list[dict] = []
    cur: dict | None = None
    for line in lines:
        s = line.rstrip()
        m = re.match(r"^###\s+(?:\d+[\.\、\)]\s*)?(.+)$", s)
        if m:
            if cur:
                items.append(cur)
            cur = {"title": m.group(1).strip(), "fields": [], "source": None}
            continue
        if cur is None:
            continue
        # source link line: "🔗 [text](url)" (also tolerate "- 🔗 ...")
        ms = re.match(r"^\s*[-*]?\s*🔗\s*(.+)$", s)
        if ms:
            content = ms.group(1).strip()
            lm = LINK_RE.search(content)
            if lm:
                cur["source"] = {"text": lm.group(1), "url": lm.group(2)}
            else:
                cur["source"] = {"text": content, "url": None}
            continue
        # field bullet: "- **Label**: value..."
        mf = re.match(r"^\s*[-*]\s*\*\*([^*]+)\*\*[:：]?\s*(.*)$", s)
        if mf:
            label = mf.group(1).strip()
            value = mf.group(2).strip()
            cur["fields"].append({"label": label, "value": value})
            continue
        # continuation line of previous field (indent or plain)
        if s.strip() and cur["fields"] and not s.startswith("#"):
            cur["fields"][-1]["value"] += " " + s.strip()
    if cur:
        items.append(cur)
    return items


def parse_mini_items(lines: list[str]) -> list[dict]:
    """Mini items are bullets like `- **Title** — desc. [src](url)`."""
    items: list[dict] = []
    cur: dict | None = None
    for line in lines:
        s = line.rstrip()
        m = re.match(r"^\s*[-*]\s+(.+)$", s)
        if m:
            if cur:
                items.append(cur)
            content = m.group(1).strip()
            cur = parse_mini_content(content)
            continue
        # continuation
        if cur and s.strip() and not s.startswith("#"):
            cur["desc"] = (cur.get("desc") or "") + " " + s.strip()
    if cur:
        items.append(cur)
    return items


def parse_mini_content(content: str) -> dict:
    """Extract title (bold), desc, and source link from a single-line bullet."""
    title = None
    desc = content
    # bold title
    bm = re.match(r"^\*\*([^*]+)\*\*\s*[—\-:：]?\s*(.*)$", content)
    if bm:
        title = bm.group(1).strip()
        desc = bm.group(2).strip()
    # extract source link (last link in content)
    src = None
    links = list(LINK_RE.finditer(desc))
    if links:
        last = links[-1]
        # if the last link is at the end and label is "来源"/"src"/"source", treat as source
        tail_label = last.group(1).strip().lower()
        if tail_label in ("来源", "source", "src", "link", "原文") or last.end() >= len(desc) - 2:
            src = {"text": last.group(1), "url": last.group(2)}
            # remove the link from desc
            desc = (desc[:last.start()] + desc[last.end():]).rstrip(" .。·-—()（）[]")
    return {"title": title, "desc": desc.strip(), "source": src}


def parse_quick_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    cur: str | None = None
    for line in lines:
        s = line.rstrip()
        m = re.match(r"^\s*[-*]\s+(.+)$", s)
        if m:
            if cur:
                items.append(cur)
            cur = m.group(1).strip()
            continue
        if cur is not None and s.strip() and not s.startswith("#"):
            cur += " " + s.strip()
    if cur:
        items.append(cur)
    return items


# ---------------------------------------------------------------- render -----

GRAD_CLASSES = ["", "with-grad-2", "with-grad-3", "with-grad-4"]


def render_hero_card(idx: int, item: dict) -> str:
    fields_html = []
    for f in item["fields"]:
        label = f["label"]
        cls = f"field-{slugify(label)}"
        fields_html.append(
            f'<li class="{cls}"><span class="field-label">{html.escape(label)}：</span>'
            f'{md_inline_to_html(f["value"])}</li>'
        )
    src_html = ""
    if item.get("source"):
        src = item["source"]
        if src.get("url"):
            host = urlparse(src["url"]).netloc.replace("www.", "")
            src_html = (
                f'<a class="source-link" href="{html.escape(src["url"])}" target="_blank" rel="noopener">'
                f'🔗 {html.escape(src["text"])} <span style="opacity:0.6;font-size:0.85em;">· {html.escape(host)}</span></a>'
            )
        else:
            src_html = f'<div class="source-link">🔗 {html.escape(src["text"])}</div>'
    return (
        f'<article class="news-card">'
        f'<h3><span class="num-badge">{idx}</span>{md_inline_to_html(item["title"])}</h3>'
        f'<ul class="news-fields">{"".join(fields_html)}</ul>'
        f'{src_html}'
        f'</article>'
    )


def render_mini_card(item: dict) -> str:
    title_html = ""
    if item.get("title"):
        title_html = f'<div class="mini-title">{md_inline_to_html(item["title"])}</div>'
    desc_html = f'<div class="mini-desc">{md_inline_to_html(item.get("desc",""))}</div>' if item.get("desc") else ""
    src_html = ""
    if item.get("source"):
        s = item["source"]
        host = urlparse(s["url"]).netloc.replace("www.", "") if s.get("url") else ""
        src_html = f'<a class="mini-link" href="{html.escape(s["url"])}" target="_blank" rel="noopener">🔗 {html.escape(host or s["text"])}</a>'
    return f'<div class="mini-news">{title_html}{desc_html}{src_html}</div>'


def render_section(sec: dict, grad_class: str) -> str:
    name = sec["name"]
    kind = sec["kind"]
    title_html = f'<h2 class="section-title {grad_class}">{html.escape(name)}</h2>'
    if kind == "hero":
        cards = "".join(render_hero_card(i + 1, it) for i, it in enumerate(sec["items"]))
        return f'<section class="news-section">{title_html}{cards}</section>'
    if kind == "mini":
        cards = "".join(render_mini_card(it) for it in sec["items"])
        return f'<section class="news-section">{title_html}<div class="mini-news-grid">{cards}</div></section>'
    if kind == "quick":
        items = "".join(f'<li>{md_inline_to_html(t)}</li>' for t in sec["items"])
        return f'<section class="news-section">{title_html}<ul class="quick-news-list">{items}</ul></section>'
    # fallback
    md = markdown.Markdown(extensions=["extra", "sane_lists"])
    body = md.convert(sec.get("raw_md", ""))
    return f'<section class="news-section">{title_html}<div class="fallback-md">{body}</div></section>'


# ---------------------------------------------------------------- pages ------

HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="每日 AI Agent 要闻 · 由 Hermes Agent 自动汇编">
<meta property="og:title" content="{title}">
<meta property="og:description" content="每日 AI Agent 要闻自动归档">
<meta property="og:type" content="website">
<link rel="stylesheet" href="{css}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🤖</text></svg>">
</head>
<body>
<header class="site-header">
  <h1>🤖 每日 AI Agent 要闻</h1>
  <p>由 Hermes Agent 自动汇编 · 每天 10:00 更新</p>
  <div class="nav-meta">
    <a href="{home}">🏠 首页</a>
    <a href="https://github.com/Maekfei/ai-daily-news" target="_blank" rel="noopener">⭐ GitHub</a>
  </div>
</header>
<div class="container">
"""

FOOT = """</div>
<footer class="site-footer">
  <p>© {year} · 自动生成于 {now} · Powered by <a href="https://github.com/NousResearch" target="_blank" rel="noopener">Hermes Agent</a> <span class="heart">❤</span></p>
</footer>
</body>
</html>
"""


def wrap_page(title: str, body: str, *, css: str, home: str) -> str:
    return (
        HEAD.format(title=html.escape(title), css=css, home=home)
        + body
        + FOOT.format(year=datetime.now().year, now=datetime.now().strftime("%Y-%m-%d %H:%M UTC"))
    )


def render_post_page(date: str, post: dict) -> str:
    sections_html = "".join(
        render_section(sec, GRAD_CLASSES[i % len(GRAD_CLASSES)]) for i, sec in enumerate(post["sections"])
    )
    summary_html = (
        f'<div class="summary">{md_inline_to_html(post["summary"])}</div>' if post.get("summary") else ""
    )
    body = (
        f'<a class="back-link" href="index.html">← 返回首页</a>'
        f'<header class="post-header">'
        f'<h1>{md_inline_to_html(post["title"])}</h1>'
        f'<div class="post-date">📅 {date}</div>'
        f'{summary_html}'
        f'</header>'
        f'{sections_html}'
    )
    return wrap_page(
        f'{post["title"]} · 每日 AI Agent 要闻',
        body,
        css="assets/style.css",
        home="index.html",
    )


def render_index(all_posts: list[tuple[str, dict]]) -> str:
    if not all_posts:
        body = '<div class="empty"><p>📭 暂无内容，等待今日 10:00 自动推送...</p></div>'
        return wrap_page("每日 AI Agent 要闻", body, css="assets/style.css", home="index.html")

    latest_date, latest = all_posts[0]
    summary_html = (
        f'<div class="summary">{md_inline_to_html(latest["summary"])}</div>' if latest.get("summary") else ""
    )
    # count items across sections
    counts = []
    for sec in latest["sections"]:
        c = len(sec.get("items", []))
        if c:
            counts.append(f"{sec['name']} ×{c}")
    counts_str = " · ".join(counts) if counts else ""

    parts = []
    parts.append('<h2 class="section-title">📌 最新一期</h2>')
    parts.append(
        f'<article class="hero-card">'
        f'<span class="badge">LATEST</span>'
        f'<h2><a href="{latest_date}.html">{md_inline_to_html(latest["title"])}</a></h2>'
        f'<div class="meta-row"><span>📅 {latest_date}</span>'
        + (f'<span>📊 {counts_str}</span>' if counts_str else "")
        + f'</div>'
        f'{summary_html}'
        f'<a href="{latest_date}.html" class="read-more">阅读全文 →</a>'
        f'</article>'
    )

    if len(all_posts) > 1:
        parts.append('<h2 class="section-title with-grad-3">🗂️ 历史归档</h2>')
        parts.append('<ul class="archive-grid">')
        for d, p in all_posts[1:]:
            parts.append(
                f'<li class="archive-card"><a href="{d}.html">'
                f'<div class="date">📅 {d}</div>'
                f'<div class="title">{md_inline_to_html(p["title"])}</div>'
                f'</a></li>'
            )
        parts.append('</ul>')

    return wrap_page("每日 AI Agent 要闻", "\n".join(parts), css="assets/style.css", home="index.html")


# ---------------------------------------------------------------- main -------

def main() -> None:
    POSTS_DIR.mkdir(exist_ok=True)
    md_files = sorted(
        [p for p in POSTS_DIR.iterdir() if DATE_RE.match(p.name)],
        key=lambda p: p.stem,
        reverse=True,
    )

    all_posts: list[tuple[str, dict]] = []
    for path in md_files:
        post = parse_post(path.read_text(encoding="utf-8"))
        all_posts.append((path.stem, post))

    # write per-post pages
    for date, post in all_posts:
        out = ROOT / f"{date}.html"
        out.write_text(render_post_page(date, post), encoding="utf-8")
        print(f"  ✓ {out.name}  · {len(post['sections'])} sections")

    # write index
    (ROOT / "index.html").write_text(render_index(all_posts), encoding="utf-8")
    print(f"  ✓ index.html  ({len(all_posts)} posts)")


if __name__ == "__main__":
    main()
