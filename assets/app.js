// AI 每日要闻 — SPA front-end
// Features: search, sidebar archive, category filter, keyword cloud,
// theme toggle, copy-link, per-day lazy load, route via #/<date>[/<itemId>]
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ---- state ----
  const state = {
    index: [],            // [{date,title,summary,counts}]
    posts: new Map(),     // date -> full post obj (cached)
    currentDate: null,
    filter: "all",        // all | hero | mini | quick
    query: "",
    keywords: [],
    recentBundle: null,   // bundled recent 30 days for cross-day search
    view: "news",         // "news" | "papers"
    papers: null,         // {papers: [...], tags: [...]}
    paperTagFilter: "all",// "all" or a tag key
  };

  // ---- date helpers (LOCAL TZ) ----
  function localYMD(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }
  function dateLabel(s) {
    const now = new Date();
    const t0 = localYMD(now);
    const t1 = localYMD(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1));
    const t2 = localYMD(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 2));
    if (s === t0) return "今天";
    if (s === t1) return "昨天";
    if (s === t2) return "前天";
    return s;
  }

  // ---- theme ----
  function initTheme() {
    const saved = localStorage.getItem("theme");
    const sys = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    const t = saved || sys;
    document.documentElement.setAttribute("data-theme", t);
    const btn = $("#theme-toggle");
    if (btn) btn.textContent = t === "dark" ? "🌙" : "☀️";
  }
  function toggleTheme() {
    const cur = document.documentElement.getAttribute("data-theme") || "dark";
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    const btn = $("#theme-toggle");
    if (btn) btn.textContent = next === "dark" ? "🌙" : "☀️";
  }

  // ---- toast ----
  let toastTimer = 0;
  function toast(msg) {
    const t = $("#toast");
    if (!t) return;
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 1800);
  }

  // ---- data loading ----
  async function loadIndex() {
    const r = await fetch("data/index.json", { cache: "no-cache" });
    state.index = await r.json();
  }
  async function loadKeywords() {
    try {
      const r = await fetch("data/keywords.json", { cache: "no-cache" });
      state.keywords = await r.json();
    } catch (e) { state.keywords = []; }
  }
  async function loadRecentBundle() {
    try {
      const r = await fetch("data.json", { cache: "no-cache" });
      const j = await r.json();
      state.recentBundle = j.posts || [];
      for (const p of state.recentBundle) state.posts.set(p.date, p);
    } catch (e) { state.recentBundle = []; }
  }
  async function loadPost(date) {
    if (state.posts.has(date)) return state.posts.get(date);
    const r = await fetch(`data/${date}.json`, { cache: "no-cache" });
    if (!r.ok) throw new Error(`Failed to load ${date}`);
    const p = await r.json();
    state.posts.set(date, p);
    return p;
  }
  async function loadPapers() {
    if (state.papers) return state.papers;
    try {
      const r = await fetch("data/papers.json", { cache: "no-cache" });
      if (!r.ok) throw new Error("no papers");
      state.papers = await r.json();
    } catch (e) {
      state.papers = { papers: [], tags: [] };
    }
    return state.papers;
  }

  // ---- routing ----
  function parseHash() {
    // #/YYYY-MM-DD or #/YYYY-MM-DD/itemId or #/papers or #/papers/<tag>
    const h = location.hash.replace(/^#\/?/, "");
    const [first, ...rest] = h.split("/");
    return { first: first || null, rest: rest.join("/") || null };
  }
  function setHash(date, anchor) {
    const v = anchor ? `#/${date}/${anchor}` : `#/${date}`;
    if (location.hash !== v) history.replaceState(null, "", v);
  }

  // ---- render: sidebar (archive list) ----
  function renderSidebar() {
    const nav = $("#dates");
    if (!nav) return;
    nav.innerHTML = state.index.map((p) => {
      const total = p.counts.hero + p.counts.mini + p.counts.quick;
      const isCurrent = p.date === state.currentDate;
      const todayStr = localYMD(new Date());
      const isToday = p.date === todayStr;
      return `<a href="#/${p.date}" class="date-link${isCurrent ? " active" : ""}" data-date="${p.date}">
        <span class="date-label">${dateLabel(p.date)}</span>
        ${isToday ? '<span class="badge-today">TODAY</span>' : ""}
        <span class="date-meta">${total} 条</span>
      </a>`;
    }).join("");
  }

  // ---- render: keyword cloud ----
  function renderCloud() {
    const c = $("#cloud");
    if (!c) return;
    if (!state.keywords.length) {
      c.innerHTML = '<div class="muted small">数据积累中…</div>';
      return;
    }
    const max = state.keywords[0].count;
    c.innerHTML = state.keywords.map((k) => {
      const w = 0.7 + (k.count / max) * 0.9; // 0.7em – 1.6em
      return `<button class="cloud-tag" data-word="${escAttr(k.word)}" style="font-size:${w}em">${escHtml(k.word)}<sup>${k.count}</sup></button>`;
    }).join("");
  }

  // ---- render: filters ----
  function renderFilters() {
    $$(".chip").forEach((b) => {
      b.classList.toggle("active", b.dataset.filter === state.filter);
    });
  }

  // ---- render: main content ----
  async function renderPost(date) {
    const main = $("#content");
    if (!main) return;
    main.innerHTML = '<div class="loading">加载中…</div>';
    // Restore news-mode sidebar header
    const archiveTitle = document.querySelector(".sidebar-section .sidebar-title");
    if (archiveTitle) archiveTitle.textContent = "归档";
    let post;
    try {
      post = await loadPost(date);
    } catch (e) {
      main.innerHTML = `<div class="empty">未找到 ${escHtml(date)}</div>`;
      return;
    }
    state.currentDate = date;
    document.title = `${post.title} · AI 每日要闻`;

    const filtered = post.sections
      .filter((s) => state.filter === "all" || s.kind === state.filter)
      .filter((s) => s.items.length);

    let html = `<article class="post">
      <header class="post-header">
        <div class="post-date-row">
          <time class="post-date">${escHtml(post.date)}</time>
          <span class="post-date-label">${escHtml(dateLabel(post.date))}</span>
        </div>
        <h1 class="post-title">${escHtml(post.title)}</h1>
        ${post.summary ? `<p class="post-summary">${escHtml(post.summary)}</p>` : ""}
      </header>`;

    if (!filtered.length) {
      html += `<div class="empty">没有匹配 "${escHtml(state.filter)}" 的内容</div>`;
    }

    for (const sec of filtered) {
      html += `<section class="sec sec-${sec.kind}">
        <h2 class="sec-title">${escHtml(sec.title)}</h2>
        <div class="sec-items sec-items-${sec.kind}">`;
      for (let i = 0; i < sec.items.length; i++) {
        html += renderItem(sec.items[i], i, post.date, sec.kind);
      }
      html += `</div></section>`;
    }
    html += `</article>`;
    main.innerHTML = html;

    // Apply search highlight if any
    if (state.query) applySearchFilter();

    // Scroll to anchor if present
    const { rest: anchor } = parseHash();
    if (anchor) {
      const el = document.getElementById(anchor);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("flash");
        setTimeout(() => el.classList.remove("flash"), 1600);
      }
    }
  }

  function renderItem(item, idx, date, kind) {
    const num = String(idx + 1).padStart(2, "0");
    const id = item.id;
    const links = item.links.map((l) =>
      `<a class="item-link" href="${escAttr(l.url)}" target="_blank" rel="noopener noreferrer">${escHtml(l.text)} ↗</a>`
    ).join("");

    // Try to parse "要点: ... · 详情: ... · 影响: ..." structured body
    let bodyHtml = "";
    if (item.body) {
      const segs = item.body.split(/\s*·\s*/);
      const tagRe = /^(要点|详情|影响|来源|背景|看点)[：:]\s*(.+)$/;
      const tagged = [];
      const plain = [];
      for (const s of segs) {
        const m = s.match(tagRe);
        if (m) tagged.push({ tag: m[1], text: m[2] });
        else plain.push(s);
      }
      if (tagged.length) {
        bodyHtml = `<div class="card-meta">${tagged.map(t =>
          `<div class="meta-row"><span class="meta-tag meta-${t.tag}">${escHtml(t.tag)}</span><span class="meta-text">${escHtml(t.text)}</span></div>`
        ).join("")}</div>`;
        if (plain.length) bodyHtml += `<div class="card-text">${escHtml(plain.join(" · "))}</div>`;
      } else {
        bodyHtml = `<div class="card-text">${escHtml(item.body)}</div>`;
      }
    }

    return `<div class="card card-${kind}" id="${escAttr(id)}" data-kind="${kind}" data-date="${date}">
      <div class="card-num" data-num="${num}"></div>
      <div class="card-body">
        <div class="card-headline">${escHtml(item.headline)}</div>
        ${bodyHtml}
        ${links ? `<div class="card-links">${links}</div>` : ""}
      </div>
      <button class="card-copy" title="复制此条链接" data-copy="${escAttr(id)}" aria-label="复制链接">🔗</button>
    </div>`;
  }

  // ---- render: papers view ----
  // Tag colors are defined in CSS as .tag-<key>; this list mirrors build.py TAG_LABELS.
  const TAG_FALLBACK = {
    "hf-trending":    { label: "HF 热门",    emoji: "🔥" },
    "top-conference": { label: "顶会论文",   emoji: "🏆" },
    "arxiv-hot":      { label: "arXiv 热门", emoji: "📈" },
    "agent":          { label: "Agent",      emoji: "🤖" },
    "rl":             { label: "RL",         emoji: "🎯" },
    "multimodal":     { label: "多模态",     emoji: "🎨" },
    "benchmark":      { label: "评测",       emoji: "📊" },
    "reasoning":      { label: "推理",       emoji: "🧠" },
    "code":           { label: "代码",       emoji: "💻" },
    "robotics":       { label: "机器人",     emoji: "🦾" },
    "survey":         { label: "综述",       emoji: "📚" },
    "open-source":    { label: "开源",       emoji: "🔓" },
  };
  function tagMeta(key) {
    return TAG_FALLBACK[key] || { label: key, emoji: "🏷" };
  }

  async function renderPapers() {
    const main = $("#content");
    if (!main) return;
    main.innerHTML = '<div class="loading">加载论文…</div>';
    const data = await loadPapers();
    document.title = "📚 论文 · AI 每日要闻";

    // Relabel sidebar archive header for papers view
    const archiveTitle = document.querySelector(".sidebar-section .sidebar-title");
    if (archiveTitle) archiveTitle.textContent = "📅 论文日期";

    const allPapers = data.papers || [];
    const tags = data.tags || [];

    // Filter by tag + free-text query
    const q = state.query.trim().toLowerCase();
    const filtered = allPapers.filter((p) => {
      const tagMatch = state.paperTagFilter === "all"
        || (p.tags || []).includes(state.paperTagFilter);
      if (!tagMatch) return false;
      if (!q) return true;
      const blob = [
        p.title, p.summary, (p.authors || []).join(" "),
        p.venue, (p.tags || []).join(" "),
      ].join(" ").toLowerCase();
      return blob.includes(q);
    });

    let html = `<article class="papers-page">
      <header class="post-header">
        <div class="post-date-row">
          <span class="post-date-label">📚 论文精选</span>
          <span class="muted small">共 ${allPapers.length} 篇 · Agent / 大模型 / 强化学习</span>
        </div>
        <h1 class="post-title">最新最热 AI 论文</h1>
        <p class="post-summary">汇总 HuggingFace 热门、arXiv 高引、顶会（NeurIPS / ICML / ICLR / ACL …）的代表性论文，每日同步更新。</p>
      </header>`;

    // Tag filter chips
    html += `<div class="paper-tagbar">
      <button class="tag-chip${state.paperTagFilter === "all" ? " active" : ""}" data-tag="all">全部 <sup>${allPapers.length}</sup></button>`;
    for (const t of tags) {
      const meta = tagMeta(t.key);
      const active = state.paperTagFilter === t.key ? " active" : "";
      html += `<button class="tag-chip tag-${t.key}${active}" data-tag="${escAttr(t.key)}">${meta.emoji} ${escHtml(meta.label)} <sup>${t.count}</sup></button>`;
    }
    html += `</div>`;

    if (!filtered.length) {
      html += `<div class="empty">没有匹配的论文 · 调整筛选或清空搜索框试试</div>`;
    } else {
      // Group by `added` date (newest first)
      const groups = new Map();
      for (const p of filtered) {
        const d = p.added || p.published || "未注明日期";
        if (!groups.has(d)) groups.set(d, []);
        groups.get(d).push(p);
      }
      const dates = Array.from(groups.keys()).sort().reverse();
      for (const d of dates) {
        const items = groups.get(d);
        const anchor = `date-${d}`;
        html += `<section class="papers-day" id="${escAttr(anchor)}">
          <div class="papers-day-header">
            <h2 class="papers-day-date">📅 ${escHtml(d)}</h2>
            <span class="papers-day-count">${items.length} 篇</span>
          </div>
          <div class="papers-grid">`;
        for (const p of items) html += renderPaperCard(p);
        html += `</div></section>`;
      }
    }
    html += `</article>`;
    main.innerHTML = html;

    // Render sidebar date list (papers-mode)
    renderPapersSidebar(filtered);
  }

  function renderPapersSidebar(papers) {
    const nav = $("#dates");
    if (!nav) return;
    const counts = new Map();
    for (const p of papers) {
      const d = p.added || p.published || "未注明日期";
      counts.set(d, (counts.get(d) || 0) + 1);
    }
    const dates = Array.from(counts.keys()).sort().reverse();
    if (!dates.length) {
      nav.innerHTML = `<li class="muted small">暂无论文</li>`;
      return;
    }
    nav.innerHTML = dates.map((d) => {
      return `<li><a href="#/papers" class="date-link" data-paper-date="${escAttr(d)}"><span class="date-label">${escHtml(d)}</span><span class="date-meta">${counts.get(d)} 篇</span></a></li>`;
    }).join("");
  }

  function renderPaperCard(p) {
    const id = p.id || slugifyClient(p.title || "paper");
    const url = p.url || p.pdf_url || "#";
    const authors = (p.authors || []).slice(0, 4).join(" · ");
    const moreAuthors = (p.authors || []).length > 4 ? ` 等 ${p.authors.length} 人` : "";
    const venueLine = [p.venue, p.published].filter(Boolean).join(" · ");

    const tagChips = (p.tags || []).map((k) => {
      const m = tagMeta(k);
      return `<span class="paper-tag tag-${escAttr(k)}">${m.emoji} ${escHtml(m.label)}</span>`;
    }).join("");

    const stars = p.stars
      ? `<span class="paper-stars" title="HuggingFace likes">❤ ${p.stars.toLocaleString()}</span>`
      : "";

    const links = [];
    if (p.url) links.push(`<a class="item-link" href="${escAttr(p.url)}" target="_blank" rel="noopener noreferrer">原文 ↗</a>`);
    if (p.pdf_url && p.pdf_url !== p.url) links.push(`<a class="item-link" href="${escAttr(p.pdf_url)}" target="_blank" rel="noopener noreferrer">PDF ↗</a>`);

    return `<div class="paper-card" id="${escAttr(id)}">
      <div class="paper-tags-row">${tagChips}${stars}</div>
      <a class="paper-title" href="${escAttr(url)}" target="_blank" rel="noopener noreferrer">${escHtml(p.title || "(untitled)")}</a>
      ${authors ? `<div class="paper-authors">${escHtml(authors)}${escHtml(moreAuthors)}</div>` : ""}
      ${venueLine ? `<div class="paper-venue">${escHtml(venueLine)}</div>` : ""}
      ${p.summary ? `<p class="paper-summary">${escHtml(p.summary)}</p>` : ""}
      ${links.length ? `<div class="card-links">${links.join("")}</div>` : ""}
    </div>`;
  }

  function slugifyClient(s) {
    return String(s).toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "paper";
  }

  function updateTopnav() {
    $$(".topnav-link").forEach((a) => {
      a.classList.toggle("active", a.dataset.view === state.view);
    });
    // Hide news-only sidebar sections in papers view
    document.body.classList.toggle("view-papers", state.view === "papers");
  }
  function applySearchFilter() {
    const q = state.query.trim().toLowerCase();
    const cards = $$(".card");
    if (!q) {
      cards.forEach((c) => c.classList.remove("hidden", "match"));
      $$(".sec").forEach((s) => s.classList.remove("hidden"));
      return;
    }
    let total = 0;
    cards.forEach((c) => {
      const text = c.textContent.toLowerCase();
      const match = text.includes(q);
      c.classList.toggle("hidden", !match);
      c.classList.toggle("match", match);
      if (match) total++;
    });
    // Hide section if no items visible
    $$(".sec").forEach((s) => {
      const any = s.querySelectorAll(".card:not(.hidden)").length > 0;
      s.classList.toggle("hidden", !any);
    });
  }

  // Cross-day search: when user types, also surface other dates with hits
  function crossDaySearchHints() {
    const q = state.query.trim().toLowerCase();
    if (!q || !state.recentBundle) return [];
    const hits = [];
    for (const p of state.recentBundle) {
      if (p.date === state.currentDate) continue;
      let count = 0;
      for (const s of p.sections) {
        for (const it of s.items) {
          const text = (it.headline + " " + it.body).toLowerCase();
          if (text.includes(q)) count++;
        }
      }
      if (count) hits.push({ date: p.date, count });
    }
    return hits.slice(0, 5);
  }

  function renderSearchHints() {
    const hints = crossDaySearchHints();
    let bar = $("#search-hints");
    if (!hints.length) { if (bar) bar.remove(); return; }
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "search-hints";
      bar.className = "search-hints";
      $("#content").prepend(bar);
    } else {
      const c = $("#content");
      if (bar.parentNode !== c) c.prepend(bar);
    }
    bar.innerHTML = `<span class="muted small">其他日期匹配：</span>` + hints.map(h =>
      `<a class="hint-pill" href="#/${h.date}">${dateLabel(h.date)} <em>(${h.count})</em></a>`
    ).join("");
  }

  // ---- copy link ----
  async function copyItemLink(id) {
    const url = `${location.origin}${location.pathname}#/${state.currentDate}/${id}`;
    try {
      await navigator.clipboard.writeText(url);
      toast("链接已复制 📋");
    } catch (e) {
      // Fallback
      const ta = document.createElement("textarea");
      ta.value = url;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); toast("链接已复制 📋"); }
      catch (err) { toast("复制失败"); }
      ta.remove();
    }
  }

  // ---- escape ----
  function escHtml(s) {
    return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  }
  function escAttr(s) {
    return String(s).replace(/["&<>]/g, (c) => ({ '"': "&quot;", "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  }

  // ---- events ----
  function bindEvents() {
    // Search input
    const q = $("#q");
    let debounceT = 0;
    q.addEventListener("input", (e) => {
      clearTimeout(debounceT);
      debounceT = setTimeout(() => {
        state.query = e.target.value;
        if (state.view === "papers") {
          renderPapers();
        } else {
          applySearchFilter();
          renderSearchHints();
        }
      }, 120);
    });

    // Keyboard shortcuts: / to focus, Esc to clear
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && document.activeElement.tagName !== "INPUT") {
        e.preventDefault();
        q.focus();
      } else if (e.key === "Escape" && document.activeElement === q) {
        q.value = ""; state.query = "";
        if (state.view === "papers") renderPapers();
        else { applySearchFilter(); renderSearchHints(); }
      }
    });

    // Sidebar nav + chips + cloud + copy + theme + tag chip + topnav
    document.addEventListener("click", (e) => {
      const link = e.target.closest(".date-link");
      if (link) {
        e.preventDefault();
        const d = link.dataset.date;
        location.hash = `#/${d}`;
        return;
      }
      const chip = e.target.closest(".chip");
      if (chip) {
        state.filter = chip.dataset.filter;
        renderFilters();
        if (state.currentDate) renderPost(state.currentDate);
        return;
      }
      const tagChip = e.target.closest(".paper-tagbar .tag-chip");
      if (tagChip) {
        state.paperTagFilter = tagChip.dataset.tag;
        renderPapers();
        return;
      }
      const paperDate = e.target.closest("[data-paper-date]");
      if (paperDate) {
        e.preventDefault();
        const d = paperDate.dataset.paperDate;
        const target = document.getElementById(`date-${d}`);
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
          // Visual highlight
          target.classList.add("flash");
          setTimeout(() => target.classList.remove("flash"), 1200);
        }
        // Mark active link
        document.querySelectorAll("#dates .date-link").forEach((a) => a.classList.remove("active"));
        paperDate.classList.add("active");
        return;
      }
      const word = e.target.closest(".cloud-tag");
      if (word) {
        q.value = word.dataset.word;
        state.query = word.dataset.word;
        if (state.view === "papers") renderPapers();
        else { applySearchFilter(); renderSearchHints(); }
        return;
      }
      const copy = e.target.closest(".card-copy");
      if (copy) {
        copyItemLink(copy.dataset.copy);
        return;
      }
      const themeBtn = e.target.closest("#theme-toggle");
      if (themeBtn) { toggleTheme(); return; }
      // Topnav handled via hashchange (regular anchor) — no JS needed,
      // but reset paperTagFilter when going to /papers without a tag.
      const topnav = e.target.closest(".topnav-link");
      if (topnav && topnav.dataset.view === "papers") {
        state.paperTagFilter = "all";
      }
    });

    // Hash routing
    window.addEventListener("hashchange", route);
  }

  async function route() {
    const { first, rest } = parseHash();

    // Papers view
    if (first === "papers") {
      state.view = "papers";
      if (rest) state.paperTagFilter = rest;
      updateTopnav();
      await renderPapers();
      // Sync search results live (papers re-renders on each search input)
      return;
    }

    // News view (default)
    state.view = "news";
    updateTopnav();
    const date = first;
    const target = date && state.index.find((p) => p.date === date)
      ? date
      : (state.index[0] && state.index[0].date);
    if (!target) {
      $("#content").innerHTML = `<div class="empty">还没有任何内容，请等待下次更新。</div>`;
      return;
    }
    if (!date) setHash(target);
    await renderPost(target);
    renderSidebar();
  }

  // ---- service worker ----
  function registerSW() {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    }
  }

  // ---- init ----
  async function init() {
    initTheme();
    bindEvents();
    await loadIndex();
    await Promise.all([loadKeywords(), loadRecentBundle()]);
    renderSidebar();
    renderCloud();
    renderFilters();
    await route();
    registerSW();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
