#!/usr/bin/env python3
"""
Static site generator for ai-daily-news.

Reads markdown files from posts/*.md and generates:
  - index.html (homepage with latest post + archive grid)
  - <date>.html  (one HTML page per post, at site root)

Each post markdown file MUST be named YYYY-MM-DD.md and may start with
an optional title block:
    # Title here

The first H1 (if present) is used as the post title; otherwise we fall
back to the date itself.
"""
from __future__ import annotations

import os
import re
import sys
import html
from datetime import datetime
from pathlib import Path

try:
    import markdown  # type: ignore
except ImportError:
    print("ERROR: 'markdown' package not installed. Run: pip install markdown", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")

HEADER = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="每日 AI Agent 要闻 - 由 Hermes Agent 自动汇编">
<link rel="stylesheet" href="{css_path}">
</head>
<body>
<header class="site-header">
  <h1>🤖 每日 AI Agent 要闻</h1>
  <p>由 Hermes Agent 自动汇编 · 重点关注 AI Agent / 智能体进展</p>
  <div class="meta"><a href="{home_path}">首页</a> · <a href="https://github.com/Maekfei/ai-daily-news" target="_blank">GitHub</a></div>
</header>
<div class="container">
"""

FOOTER = """</div>
<footer class="site-footer">
  <p>© {year} · 自动生成于 {now} · <a href="https://github.com/Maekfei/ai-daily-news" target="_blank">源码</a></p>
</footer>
</body>
</html>
"""


def read_post(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    # Strip optional YAML frontmatter
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5:]
    # Try to grab first H1
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = m.group(1).strip() if m else f"{path.stem} AI 要闻"
    md = markdown.Markdown(extensions=["extra", "sane_lists", "toc"])
    body_html = md.convert(text)
    return {
        "date": path.stem,
        "title": title,
        "body": body_html,
        "raw": text,
    }


def render_page(title: str, body_html: str, *, css_path: str, home_path: str) -> str:
    head = HEADER.format(title=html.escape(title), css_path=css_path, home_path=home_path)
    foot = FOOTER.format(year=datetime.now().year, now=datetime.now().strftime("%Y-%m-%d %H:%M UTC"))
    return head + body_html + foot


def build_post_page(post: dict) -> str:
    body = (
        f'<article class="post">'
        f'<a class="back-link" href="index.html">← 返回首页</a>'
        f'<h1>{html.escape(post["title"])}</h1>'
        f'<div class="post-date">📅 {post["date"]}</div>'
        f'{post["body"]}'
        f'</article>'
    )
    return render_page(
        title=f'{post["title"]} · 每日 AI Agent 要闻',
        body_html=body,
        css_path="assets/style.css",
        home_path="index.html",
    )


def build_index(posts: list[dict]) -> str:
    if not posts:
        body = '<div class="empty"><p>📭 暂无内容，等待今日 10:00 自动推送...</p></div>'
        return render_page("每日 AI Agent 要闻", body, css_path="assets/style.css", home_path="index.html")

    latest = posts[0]
    parts = []
    parts.append(f'<h2 class="section-title">📌 最新一期</h2>')
    parts.append(
        f'<div class="latest-card">'
        f'<span class="badge">LATEST</span>'
        f'<h2><a href="{latest["date"]}.html">{html.escape(latest["title"])}</a></h2>'
        f'<div class="post-date">📅 {latest["date"]}</div>'
        f'{latest["body"]}'
        f'</div>'
    )

    if len(posts) > 1:
        parts.append('<h2 class="section-title">🗂️ 历史归档</h2>')
        parts.append('<ul class="archive-list">')
        for p in posts[1:]:
            parts.append(
                f'<li class="archive-item"><a href="{p["date"]}.html">'
                f'<div class="date">📅 {p["date"]}</div>'
                f'<div class="title">{html.escape(p["title"])}</div>'
                f'</a></li>'
            )
        parts.append('</ul>')

    return render_page("每日 AI Agent 要闻", "\n".join(parts), css_path="assets/style.css", home_path="index.html")


def main() -> None:
    POSTS_DIR.mkdir(exist_ok=True)
    md_files = sorted(
        [p for p in POSTS_DIR.iterdir() if DATE_RE.match(p.name)],
        key=lambda p: p.stem,
        reverse=True,
    )
    posts = [read_post(p) for p in md_files]

    # Write per-post HTML
    for post in posts:
        out = ROOT / f'{post["date"]}.html'
        out.write_text(build_post_page(post), encoding="utf-8")
        print(f"  ✓ {out.name}")

    # Write index
    (ROOT / "index.html").write_text(build_index(posts), encoding="utf-8")
    print(f"  ✓ index.html  ({len(posts)} posts)")


if __name__ == "__main__":
    main()
