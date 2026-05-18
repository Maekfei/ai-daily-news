#!/usr/bin/env python3
"""
Static site generator for ai-daily-news (v3 — SPA with sidebar + search).

Parses markdown files (posts/YYYY-MM-DD.md) into a structured `data.json`
and writes a single SPA `index.html` shell that renders client-side.

Markdown format expected:
    # Title
    > optional summary

    ## H2 section name (classified into hero/mini/quick/other)
    ### N. Hero item title  (only inside hero sections)
    - **要点**: ...
    - **详情**: ...
    - **影响**: ...
    - 🔗 [source text](https://...)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)")


# ---------------------------------------------------------------- parser -----

def parse_post(md_text: str) -> dict:
    if md_text.startswith("---\n"):
        end = md_text.find("\n---\n", 4)
        if end != -1:
            md_text = md_text[end + 5:]

    lines = md_text.splitlines()
    title = None
    summary = None
    sections: list[dict] = []
    current: dict | None = None
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if title is None and line.startswith("# "):
            title = line[2:].strip()
        elif summary is None and line.startswith("> "):
            summary = line[2:].strip()
        elif line.startswith("## "):
            name = line[3:].strip()
            current = {"kind": classify(name), "name": name, "lines": []}
            sections.append(current)
        else:
            if current is not None:
                current["lines"].append(line)
        i += 1

    for sec in sections:
        kind = sec["kind"]
        if kind == "hero":
            sec["items"] = parse_hero(sec["lines"])
        elif kind == "mini":
            sec["items"] = parse_mini(sec["lines"])
        elif kind == "quick":
            sec["items"] = parse_quick(sec["lines"])
        else:
            sec["items"] = parse_quick(sec["lines"])  # fallback
        sec.pop("lines", None)

    return {
        "title": title or "AI 要闻",
        "summary": summary,
        "sections": sections,
    }


def classify(name: str) -> str:
    n = name.lower()
    if "agent" in n or "重点" in name or "焦点" in name:
        return "hero"
    if "快讯" in name or "一句话" in name or "tldr" in n:
        return "quick"
    if "大模型" in name or "行业" in name or "动态" in name or "其他" in name:
        return "mini"
    return "other"


def parse_hero(lines: list[str]) -> list[dict]:
    items: list[dict] = []
    cur: dict | None = None
    for s in lines:
        line = s.rstrip()
        m = re.match(r"^###\s+(?:\d+[\.\、\)]\s*)?(.+)$", line)
        if m:
            if cur:
                items.append(cur)
            cur = {"title": m.group(1).strip(), "fields": [], "source": None}
            continue
        if cur is None:
            continue
        ms = re.match(r"^\s*[-*]?\s*🔗\s*(.+)$", line)
        if ms:
            content = ms.group(1).strip()
            lm = LINK_RE.search(content)
            if lm:
                cur["source"] = {"text": lm.group(1), "url": lm.group(2)}
            else:
                cur["source"] = {"text": content, "url": None}
            continue
        mf = re.match(r"^\s*[-*]\s*\*\*([^*]+)\*\*[:：]?\s*(.*)$", line)
        if mf:
            cur["fields"].append({"label": mf.group(1).strip(), "value": mf.group(2).strip()})
            continue
        # continuation line
        if line.strip() and cur["fields"] and not line.startswith("#"):
            cur["fields"][-1]["value"] += " " + line.strip()
    if cur:
        items.append(cur)
    return items


def parse_mini(lines: list[str]) -> list[dict]:
    items: list[dict] = []
    cur: dict | None = None
    for s in lines:
        line = s.rstrip()
        m = re.match(r"^\s*[-*]\s+(.+)$", line)
        if m:
            if cur:
                items.append(cur)
            cur = parse_mini_content(m.group(1).strip())
            continue
        if cur and line.strip() and not line.startswith("#"):
            cur["desc"] = (cur.get("desc") or "") + " " + line.strip()
    if cur:
        items.append(cur)
    return items


def parse_mini_content(content: str) -> dict:
    title = None
    desc = content
    bm = re.match(r"^\*\*([^*]+)\*\*\s*[—\-:：]?\s*(.*)$", content)
    if bm:
        title = bm.group(1).strip()
        desc = bm.group(2).strip()
    src = None
    links = list(LINK_RE.finditer(desc))
    if links:
        last = links[-1]
        tail_label = last.group(1).strip().lower()
        if tail_label in ("来源", "source", "src", "link", "原文") or last.end() >= len(desc) - 2:
            src = {"text": last.group(1), "url": last.group(2)}
            desc = (desc[:last.start()] + desc[last.end():]).rstrip(" .。·-—()（）[]")
    return {"title": title, "desc": desc.strip(), "source": src}


def parse_quick(lines: list[str]) -> list[str]:
    items: list[str] = []
    cur: str | None = None
    for s in lines:
        line = s.rstrip()
        m = re.match(r"^\s*[-*]\s+(.+)$", line)
        if m:
            if cur:
                items.append(cur)
            cur = m.group(1).strip()
            continue
        if cur is not None and line.strip() and not line.startswith("#"):
            cur += " " + line.strip()
    if cur:
        items.append(cur)
    return items


# ---------------------------------------------------------------- shell ------

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日 AI Agent 要闻</title>
<meta name="description" content="每日 AI Agent 要闻 · 由 Hermes Agent 自动汇编">
<meta property="og:title" content="每日 AI Agent 要闻">
<meta property="og:description" content="每天 10:00 自动归档的 AI Agent 行业动态">
<meta property="og:type" content="website">
<link rel="stylesheet" href="assets/style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🤖</text></svg>">
</head>
<body>
<header class="topbar">
  <button id="menu-toggle" class="menu-toggle" aria-label="切换菜单">☰</button>
  <a href="#" class="logo">
    <span class="emoji">🤖</span>
    <span class="text-full grad-text">每日 AI Agent 要闻</span>
  </a>
  <div class="search-wrap" id="search-wrap">
    <span class="search-icon">🔍</span>
    <input id="search-input" type="search" placeholder="搜索新闻 (按 / 快速聚焦)" autocomplete="off" spellcheck="false">
    <button id="search-clear" class="search-clear" aria-label="清除">✕</button>
  </div>
  <div class="topbar-actions">
    <a href="https://github.com/Maekfei/ai-daily-news" target="_blank" rel="noopener" title="GitHub">⭐</a>
  </div>
</header>

<div class="layout">
  <aside id="sidebar" class="sidebar"></aside>
  <div id="sidebar-overlay" class="sidebar-overlay"></div>
  <main id="main" class="main">
    <div class="empty"><span class="emoji">⏳</span><p>加载中...</p></div>
  </main>
</div>

<footer class="site-footer">
  <p>Powered by <a href="https://github.com/NousResearch" target="_blank" rel="noopener">Hermes Agent</a> <span class="heart">❤</span> · <a href="https://github.com/Maekfei/ai-daily-news" target="_blank" rel="noopener">源码</a></p>
</footer>

<script src="assets/app.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------- main -------

def main() -> None:
    POSTS_DIR.mkdir(exist_ok=True)
    md_files = sorted(
        [p for p in POSTS_DIR.iterdir() if DATE_RE.match(p.name)],
        key=lambda p: p.stem,
        reverse=True,
    )
    posts: list[dict] = []
    for path in md_files:
        post = parse_post(path.read_text(encoding="utf-8"))
        post["date"] = path.stem
        posts.append(post)
        sec_summary = ", ".join(f'{s["name"]}({len(s.get("items",[]))})' for s in post["sections"])
        print(f"  ✓ {path.stem}  · {sec_summary}")

    data = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "posts": posts,
    }
    (ROOT / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (ROOT / "index.html").write_text(INDEX_HTML, encoding="utf-8")

    # Clean up old per-post HTML files (legacy from v1/v2 build)
    for old in ROOT.glob("20*.html"):
        if DATE_RE.match(old.name.replace(".html", ".md")) or re.match(r"^\d{4}-\d{2}-\d{2}\.html$", old.name):
            old.unlink()
            print(f"  ✗ removed legacy {old.name}")

    print(f"  ✓ data.json   ({len(posts)} posts)")
    print(f"  ✓ index.html  (SPA shell)")


if __name__ == "__main__":
    main()
