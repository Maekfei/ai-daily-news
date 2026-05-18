# 🤖 每日 AI Agent 要闻

由 [Hermes Agent](https://github.com/NousResearch) 自动汇编的 AI 行业每日动态，重点关注 **AI Agent / 智能体** 进展。

🌐 **网站**: https://maekfei.github.io/ai-daily-news/

## 📅 更新频率

每天早上 **10:00 (Asia/Shanghai)** 自动更新。

## 📁 结构

```
.
├── index.html              # 首页（最新一期 + 历史归档）
├── YYYY-MM-DD.html         # 每日详情页（自动生成）
├── posts/                  # markdown 源文件
│   └── YYYY-MM-DD.md
├── assets/style.css        # 样式
└── scripts/build.py        # 静态站点生成器
```

## 🛠️ 本地构建

```bash
pip install markdown
python3 scripts/build.py
```

## ⚙️ 自动化流程

定时任务 (cron) 每天 10:00 触发：
1. 用 web_search 搜集 24 小时内的 AI Agent 相关要闻
2. 整理成 markdown 写入 `posts/YYYY-MM-DD.md`
3. 运行 `scripts/build.py` 重新生成静态页面
4. `git push` 到本仓库 → GitHub Pages 自动部署

---

⚡ Powered by [Hermes Agent](https://github.com/NousResearch) · 🎨 自动 dark mode
