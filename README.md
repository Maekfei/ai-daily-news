# AI 每日要闻 · Daily AI News

> 聚焦 **AI Agent / 智能体** 的每日行业要闻精选 — 每天上午 10:00 (UTC+8) 自动更新。

🔗 **网站**：<https://maekfei.github.io/ai-daily-news/>
📡 **RSS**：<https://maekfei.github.io/ai-daily-news/feed.xml>
🗺️ **Sitemap**：<https://maekfei.github.io/ai-daily-news/sitemap.xml>

---

## 它做了什么

- 每天 10:00 由 cron job 自动搜集 AI 行业新闻（重点 Agent / 框架 / 协议 / 融资）
- 按 `🎯 Agent 重点 / 📰 大模型 & 行业动态 / 💡 一句话快讯` 分类整理
- 写入 `posts/YYYY-MM-DD.md`，由 `scripts/build.py` 渲染成 SPA
- 通过 `git push` 部署到 GitHub Pages

## 项目结构

```
posts/                  # 每日 markdown 原文（数据源）
  └── YYYY-MM-DD.md
scripts/
  └── build.py          # 解析 markdown → data + 索引 + RSS + sitemap + OG 图
assets/
  ├── style.css         # Dashboard 样式（dark + light）
  └── app.js            # SPA：搜索、分类、词云、复制链接、按需加载
data/
  ├── index.json        # 日期索引（侧边栏用）
  ├── keywords.json     # 7 天关键词词云
  └── YYYY-MM-DD.json   # 每日完整数据（按需加载）
data.json               # 最近 30 天打包（冷启动 + 跨日搜索）
og/                     # 每期 Open Graph SVG 图
sw.js                   # Service Worker（离线缓存）
feed.xml, sitemap.xml   # 自动生成
cron-prompt.md          # cron job 当前 prompt 备份
```

## 本地构建

```bash
python3 scripts/build.py
# 然后用任意静态服务器预览：
python3 -m http.server 8000
```

## 功能

- ✅ Dark + Light 主题切换（跟随系统）
- ✅ 全文搜索 + 跨日期搜索提示（`/` 聚焦）
- ✅ 分类筛选（Agent / 大模型 / 快讯）
- ✅ 7 天关键词词云
- ✅ 卡片复制链接（`#/<date>/<itemId>`）
- ✅ 离线缓存（PWA Service Worker）
- ✅ RSS 订阅 / Sitemap / Open Graph 图
- ✅ 隐私友好的访问统计（GoatCounter）

## 数据声明

内容由 AI 自动整理，建议核实原文链接。本仓库为个人归档，不构成任何投资/技术建议。

## License

MIT
