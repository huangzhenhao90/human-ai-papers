# AI Papers

一个统一的中文 AI 论文索引，当前包含：

- 组织与商业：来自 ob-ai-papers
- 用户与交互：来自 ur-ai-papers
- 心理健康：本项目内的受控 OpenAlex + MiniMax 流水线

网站打开后直接进入统一论文流。同一论文可属于多个频道；页面只显示一次，但保留每个频道自己的相关度、摘要与标签。

## 当前数据

- 1,840 篇 2023 年至今的规范论文
- 组织与商业：1,618 篇
- 用户与交互：243 篇
- 心理健康：9 篇受控验证样本
- 30 篇跨频道论文

心理健康目前只完成小批量端到端验证，不代表历史全量回填已经完成。

## 本地启动

### 1. Python 环境

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

### 2. 同步 OB / UR 正式发布数据

    python scripts/sync_legacy.py

脚本读取两个旧仓库的 origin/main，不读取它们的脏工作树。

### 3. 心理健康候选

免费 dry-run：

    python scripts/fetch_mental_health.py --dry-run

免费抓取受控候选：

    python scripts/fetch_mental_health.py --limit 60

评分默认仍是零成本 dry-run：

    python scripts/score_mental_health.py --limit 20

只有显式传入 --execute 且环境中存在 MINIMAX_API_KEY 才会调用付费模型：

    python scripts/score_mental_health.py --execute --limit 12 --batch-size 4

大批量历史回填不属于默认命令。

### 4. 生成统一索引

    python scripts/build_unified_index.py

主要输出：

- web/public/data/papers.json
- web/public/data/papers/{stable-id}.json
- web/public/data/meta.json
- web/public/data/updates.json
- web/public/data/coverage.json
- web/public/rss.xml
- data/reports/unified-publish-report.json

### 5. 启动网站

    cd web
    npm install
    npm run dev

默认地址：http://localhost:3300

项目固定使用 Webpack；Next.js Turbopack 在当前中文目录下存在 UTF-8 路径崩溃。

## 验证

Python：

    pytest -q

前端：

    cd web
    npm run typecheck
    npm run build

生产浏览器冒烟：

    python /Users/huang/.agents/skills/webapp-testing/scripts/with_server.py \
      --server "cd web && npm run start" --port 3300 -- \
      python tests/browser_smoke.py

## 重要语义

- /recent：过去 7 天实际发表，按 paper.date。
- RSS：按首次进入统一索引时间，用于订阅器感知新入库。
- 心理健康发布门槛：ai_relevance >= 3 且 domain_relevance >= 3。
- 关键词只负责召回候选，不直接决定正式发布。

## 暂未执行

- GitHub 远端创建与推送
- Vercel 部署
- 旧网站下线或跳转
- 心理健康历史全量付费回填
