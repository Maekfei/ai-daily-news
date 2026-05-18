/* =========================================================
   ai-daily-news front-end app
   - Loads data.json (all posts pre-built by build.py)
   - Renders by selected date or by search query
   - Highlights matches
   ========================================================= */
(function () {
  "use strict";

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));
  const escHtml = (s) =>
    String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const KIND_META = {
    hero: { label: "Agent 重点", emoji: "🎯" },
    mini: { label: "大模型 & 行业动态", emoji: "📰" },
    quick: { label: "一句话快讯", emoji: "💡" },
    other: { label: "其他", emoji: "📌" },
  };

  let DATA = null;
  let activeDate = null;
  let searchTerm = "";
  let searchTimer = null;

  // ---- init ----
  document.addEventListener("DOMContentLoaded", init);

  async function init() {
    try {
      const res = await fetch("data.json", { cache: "no-store" });
      DATA = await res.json();
    } catch (e) {
      console.error("Failed to load data.json", e);
      $("#main").innerHTML = '<div class="empty"><span class="emoji">⚠️</span><p>加载数据失败，请稍后再试</p></div>';
      return;
    }
    if (!DATA.posts || DATA.posts.length === 0) {
      renderEmpty();
      return;
    }
    DATA.posts.sort((a, b) => b.date.localeCompare(a.date));
    activeDate = readHash() || DATA.posts[0].date;
    renderSidebar();
    bindUI();
    render();
  }

  // ---- URL hash routing ----
  function readHash() {
    const m = location.hash.match(/^#\/?(\d{4}-\d{2}-\d{2})/);
    return m ? m[1] : null;
  }
  function writeHash(date) {
    if (!date) return;
    history.replaceState(null, "", "#/" + date);
  }
  window.addEventListener("hashchange", () => {
    const d = readHash();
    if (d && d !== activeDate) {
      activeDate = d;
      $("#search-input").value = "";
      searchTerm = "";
      $("#search-wrap").classList.remove("has-value");
      render();
    }
  });

  // ---- bind UI ----
  function bindUI() {
    const input = $("#search-input");
    input.addEventListener("input", (e) => {
      const v = e.target.value.trim();
      $("#search-wrap").classList.toggle("has-value", !!v);
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        searchTerm = v.toLowerCase();
        render();
      }, 120);
    });
    $("#search-clear").addEventListener("click", () => {
      input.value = "";
      $("#search-wrap").classList.remove("has-value");
      searchTerm = "";
      render();
      input.focus();
    });
    // keyboard shortcut "/"
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && document.activeElement !== input) {
        e.preventDefault();
        input.focus();
      }
      if (e.key === "Escape" && document.activeElement === input) {
        input.value = "";
        searchTerm = "";
        $("#search-wrap").classList.remove("has-value");
        render();
      }
    });
    // sidebar toggle (mobile)
    const tgl = $("#menu-toggle");
    const sb = $("#sidebar");
    const ov = $("#sidebar-overlay");
    if (tgl) {
      tgl.addEventListener("click", () => {
        sb.classList.toggle("open");
        ov.classList.toggle("open");
      });
      ov.addEventListener("click", () => {
        sb.classList.remove("open");
        ov.classList.remove("open");
      });
    }
  }

  // ---- sidebar ----
  function renderSidebar() {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const ymd = (d) => d.toISOString().slice(0, 10);
    const todayStr = ymd(today);
    const yest = new Date(today); yest.setDate(today.getDate() - 1);
    const yestStr = ymd(yest);

    const dateLabel = (d) => {
      if (d === todayStr) return "今天";
      if (d === yestStr) return "昨天";
      return d;
    };

    const items = DATA.posts.map((p) => {
      const isToday = p.date === todayStr;
      return `<li>
        <a href="#/${p.date}" data-date="${p.date}" class="${p.date === activeDate ? "active" : ""}">
          <span class="dot"></span>
          <span class="date-text">${dateLabel(p.date)}</span>
          ${isToday ? '<span class="badge-today">TODAY</span>' : ""}
        </a>
      </li>`;
    }).join("");

    // stats
    let totalNews = 0, totalAgent = 0;
    DATA.posts.forEach((p) => {
      p.sections.forEach((s) => {
        const c = (s.items || []).length;
        totalNews += c;
        if (s.kind === "hero") totalAgent += c;
      });
    });

    $("#sidebar").innerHTML = `
      <h3>📅 日期归档</h3>
      <ul class="date-list">${items}</ul>
      <h3>📊 统计</h3>
      <div class="stats-card">
        <div class="stat-row"><span>总期数</span><span class="num">${DATA.posts.length}</span></div>
        <div class="stat-row"><span>累计新闻</span><span class="num">${totalNews}</span></div>
        <div class="stat-row"><span>Agent 重点</span><span class="num">${totalAgent}</span></div>
      </div>
    `;
    // delegate clicks (so the active state updates instantly)
    $$("#sidebar .date-list a").forEach((a) => {
      a.addEventListener("click", (e) => {
        const d = a.dataset.date;
        if (d) {
          $$("#sidebar .date-list a").forEach((x) => x.classList.remove("active"));
          a.classList.add("active");
          activeDate = d;
          $("#search-input").value = "";
          searchTerm = "";
          $("#search-wrap").classList.remove("has-value");
          // close mobile sidebar
          $("#sidebar").classList.remove("open");
          $("#sidebar-overlay").classList.remove("open");
          writeHash(d);
          render();
        }
      });
    });
  }

  function setSidebarActive(date) {
    $$("#sidebar .date-list a").forEach((a) =>
      a.classList.toggle("active", a.dataset.date === date)
    );
  }

  // ---- main render ----
  function render() {
    if (searchTerm) {
      renderSearch();
    } else {
      setSidebarActive(activeDate);
      writeHash(activeDate);
      renderDay(activeDate);
    }
  }

  function renderEmpty() {
    $("#main").innerHTML = `
      <div class="empty">
        <span class="emoji">📭</span>
        <p>暂无内容，等待今日 10:00 自动推送...</p>
      </div>
    `;
  }

  function renderDay(date) {
    const post = DATA.posts.find((p) => p.date === date);
    if (!post) {
      $("#main").innerHTML = `<div class="empty"><span class="emoji">🤔</span><p>未找到该日期的内容</p></div>`;
      return;
    }

    const sectionsHtml = post.sections.map((sec) => renderSection(sec)).join("");
    const counts = post.sections
      .filter((s) => (s.items || []).length)
      .map((s) => `${KIND_META[s.kind].emoji} ${s.items.length}`)
      .join(" · ");

    $("#main").innerHTML = `
      <header class="page-header">
        <h1>${escHtml(post.title)}</h1>
        <div class="meta-row">
          <span>📅 ${post.date}</span>
          ${counts ? `<span>${counts}</span>` : ""}
        </div>
        ${post.summary ? `<div class="summary">${inlineMd(post.summary)}</div>` : ""}
      </header>
      ${sectionsHtml}
    `;
  }

  function renderSection(sec) {
    const meta = KIND_META[sec.kind] || KIND_META.other;
    const items = sec.items || [];
    if (!items.length) return "";

    let inner = "";
    if (sec.kind === "hero") {
      inner = items
        .map(
          (it, i) => `
          <article class="news-card" data-variant="${(i % 4) + 1}">
            <span class="num-badge">${i + 1}</span>
            <h3 class="card-title">${inlineMd(it.title)}</h3>
            <ul class="card-fields">
              ${(it.fields || []).map(renderField).join("")}
            </ul>
            ${renderSource(it.source)}
          </article>
        `
        )
        .join("");
    } else if (sec.kind === "mini") {
      inner = `<div class="mini-grid">${items
        .map(
          (it) => `
          <div class="mini-card">
            ${it.title ? `<div class="mini-title">${inlineMd(it.title)}</div>` : ""}
            ${it.desc ? `<div class="mini-desc">${inlineMd(it.desc)}</div>` : ""}
            ${
              it.source && it.source.url
                ? `<a class="mini-link" href="${escHtml(it.source.url)}" target="_blank" rel="noopener">🔗 ${escHtml(domainOf(it.source.url))}</a>`
                : ""
            }
          </div>`
        )
        .join("")}</div>`;
    } else if (sec.kind === "quick") {
      inner = items.map((t) => `<div class="quick-card">${inlineMd(t)}</div>`).join("");
    } else {
      inner = `<div class="news-card">${escHtml(JSON.stringify(items))}</div>`;
    }

    return `
      <h2 class="section-heading" data-kind="${sec.kind}">
        <span class="ico">${meta.emoji}</span>
        <span>${escHtml(sec.name || meta.label)}</span>
        <span class="count">${items.length} 条</span>
      </h2>
      ${inner}
    `;
  }

  function renderField(f) {
    const cls = "field-" + slugify(f.label || "");
    return `<li class="${cls}"><span class="field-label">${escHtml(f.label)}：</span>${inlineMd(f.value)}</li>`;
  }
  function renderSource(src) {
    if (!src) return "";
    if (src.url) {
      return `<a class="source-link" href="${escHtml(src.url)}" target="_blank" rel="noopener">🔗 ${escHtml(src.text)}<span class="domain">· ${escHtml(domainOf(src.url))}</span></a>`;
    }
    return `<div class="source-link">🔗 ${escHtml(src.text)}</div>`;
  }

  // ---- search ----
  function renderSearch() {
    const q = searchTerm;
    const results = []; // {post, kind, item, html}

    DATA.posts.forEach((post) => {
      post.sections.forEach((sec) => {
        (sec.items || []).forEach((it, idx) => {
          const blob = makeSearchBlob(it, sec.kind);
          if (blob.toLowerCase().includes(q)) {
            results.push({ post, sec, it, idx });
          }
        });
      });
    });

    setSidebarActive(null);

    if (results.length === 0) {
      $("#main").innerHTML = `
        <header class="page-header">
          <h1>🔍 搜索：${escHtml(searchTerm)}</h1>
          <div class="meta-row"><span>没有匹配结果</span></div>
        </header>
        <div class="no-results">
          <span class="emoji">🤷</span>
          <p>未找到匹配 "${escHtml(searchTerm)}" 的内容，试试别的关键词？</p>
        </div>
      `;
      return;
    }

    // group by date
    const byDate = new Map();
    results.forEach((r) => {
      if (!byDate.has(r.post.date)) byDate.set(r.post.date, []);
      byDate.get(r.post.date).push(r);
    });

    const sortedDates = Array.from(byDate.keys()).sort().reverse();
    const html = sortedDates
      .map((d) => {
        const grp = byDate.get(d);
        const cards = grp.map(renderSearchHit).join("");
        return `<div class="day-divider">📅 ${d} · ${grp.length} 条</div>${cards}`;
      })
      .join("");

    $("#main").innerHTML = `
      <header class="page-header">
        <h1>🔍 搜索结果</h1>
        <div class="meta-row">
          <span>关键词："<b style="color:var(--accent)">${escHtml(searchTerm)}</b>"</span>
          <span>共 <b style="color:var(--accent)">${results.length}</b> 条结果，分布在 <b>${sortedDates.length}</b> 期</span>
        </div>
      </header>
      ${html}
    `;
  }

  function renderSearchHit(r) {
    const { sec, it, idx } = r;
    if (sec.kind === "hero") {
      const fields = (it.fields || []).map((f) => {
        return `<li class="field-${slugify(f.label)}"><span class="field-label">${escHtml(f.label)}：</span>${highlight(f.value)}</li>`;
      }).join("");
      return `
        <article class="news-card" data-variant="${(idx % 4) + 1}">
          <span class="num-badge">${idx + 1}</span>
          <h3 class="card-title">${highlight(it.title)}</h3>
          <ul class="card-fields">${fields}</ul>
          ${renderSource(it.source)}
        </article>
      `;
    }
    if (sec.kind === "mini") {
      return `
        <div class="mini-card" style="margin-bottom:14px">
          ${it.title ? `<div class="mini-title">${highlight(it.title)}</div>` : ""}
          ${it.desc ? `<div class="mini-desc">${highlight(it.desc)}</div>` : ""}
          ${it.source && it.source.url ? `<a class="mini-link" href="${escHtml(it.source.url)}" target="_blank" rel="noopener">🔗 ${escHtml(domainOf(it.source.url))}</a>` : ""}
        </div>`;
    }
    if (sec.kind === "quick") {
      return `<div class="quick-card">${highlight(it)}</div>`;
    }
    return "";
  }

  function makeSearchBlob(it, kind) {
    if (kind === "hero") {
      const fields = (it.fields || []).map((f) => f.label + " " + f.value).join(" ");
      const src = it.source ? (it.source.text || "") + " " + (it.source.url || "") : "";
      return [it.title, fields, src].join(" ");
    }
    if (kind === "mini") {
      return [it.title || "", it.desc || "", it.source ? it.source.url || "" : ""].join(" ");
    }
    if (kind === "quick") return String(it);
    return "";
  }

  // ---- inline md (links, bold, code) + highlight ----
  function inlineMd(text) {
    if (text == null) return "";
    let s = escHtml(text);
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      (_, t, u) => `<a href="${u}" target="_blank" rel="noopener">${t}</a>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    if (searchTerm) s = applyHighlight(s, searchTerm);
    return s;
  }

  function highlight(text) {
    return inlineMd(text); // inlineMd already calls applyHighlight if searchTerm set
  }

  function applyHighlight(html, term) {
    // highlight inside text nodes only (avoid breaking tags)
    const re = new RegExp("(" + escapeRe(term) + ")", "gi");
    // simple split-on-tag approach
    return html.replace(/(<[^>]+>)|([^<]+)/g, (m, tag, txt) => {
      if (tag) return tag;
      return txt.replace(re, '<mark class="hl">$1</mark>');
    });
  }

  function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
  function slugify(s) { return String(s).trim().toLowerCase().replace(/\s+/g, "-").slice(0, 20); }
  function domainOf(url) { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; } }
})();
