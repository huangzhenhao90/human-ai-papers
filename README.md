# AI Papers

一个统一的中文 AI 论文索引，当前包含：

- 组织与商业：来自 ob-ai-papers
- 用户与交互：来自 ur-ai-papers
- 心理健康：本项目内的受控 OpenAlex + MiniMax 流水线

网站打开后直接进入统一论文流。同一论文可属于多个频道；页面只显示一次，但保留每个频道自己的相关度、摘要与标签。

正式网站：https://human-ai-papers.vercel.app

GitHub：https://github.com/huangzhenhao90/human-ai-papers

频道不是写死在页面中的。名称、顺序、颜色、是否必需与数据目录统一登记在 `config/channels.yaml`；发布层、校验器和前端会读取同一份注册信息，为后续增加第四、第五个频道保留了稳定入口。

## 当前数据

- 1,895 篇 2023 年至今的规范论文
- 组织与商业：1,656 篇
- 用户与交互：262 篇
- 心理健康：9 篇受控验证样本
- 32 篇跨频道论文

心理健康目前只完成小批量端到端验证，不代表历史全量回填已经完成。

## 本地启动

### 1. Python 环境

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

### 2. 一条命令更新完整项目

默认执行：刷新 OB / UR 远端引用、保留失败频道的上一版有效快照、构建统一索引、生成 RSS，并验证全部公开文件：

    python scripts/update_project.py

本地默认不会调用付费模型。心理健康支持四种显式模式：

    python scripts/update_project.py --mh-mode fetch
    python scripts/update_project.py --mh-mode dry-run
    python scripts/update_project.py --mh-mode execute --mh-limit 12 --mh-batch-size 4

只有 `execute` 且存在 `MINIMAX_API_KEY` 时才会产生付费请求。运行审计写入 `data/reports/update-run.json`。

### 3. 分步运行

同步 OB / UR 正式发布数据：

    python scripts/sync_legacy.py

脚本读取两个旧仓库的 origin/main，不读取它们的脏工作树。

心理健康候选：

免费 dry-run：

    python scripts/fetch_mental_health.py --dry-run

免费抓取受控候选：

    python scripts/fetch_mental_health.py --limit 60

评分默认仍是零成本 dry-run：

    python scripts/score_mental_health.py --limit 20

只有显式传入 --execute 且环境中存在 MINIMAX_API_KEY 才会调用付费模型：

    python scripts/score_mental_health.py --execute --limit 12 --batch-size 4

大批量历史回填不属于默认命令。

生成统一索引：

    python scripts/build_unified_index.py

主要输出：

- web/public/data/papers.json
- web/public/data/papers/{stable-id}.json
- web/public/data/meta.json
- web/public/data/updates.json
- web/public/data/coverage.json
- web/public/rss.xml
- data/reports/unified-publish-report.json

### 4. 启动网站

    cd web
    npm install
    npm run dev

默认地址：http://localhost:3300

项目固定使用 Webpack；Next.js Turbopack 在当前中文目录下存在 UTF-8 路径崩溃。

## 验证

完整验证：

    make verify

仅检查公开数据之间是否一致：

    python scripts/validate_release.py

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

## 自动更新与部署

- `.github/workflows/ci.yml`：Python 测试、公开数据校验、TypeScript 与 Next.js 构建。
- `.github/workflows/daily_update.yml`：每天北京时间 10:00 同步 OB / UR，并对心理健康执行 OpenAlex 候选检索和最多 12 篇 MiniMax 双评分；已评分候选会自动排除，然后构建、校验并提交变化。
- `web/vercel.json`：将 Vercel 项目 Root Directory 设为 `web` 后可直接部署。
- 正式部署前将 GitHub Repository Variable `SITE_URL` 设置为网站域名，RSS 会使用该域名。

## 增加新频道

详见 `docs/adding-a-channel.md`。最短路径是：在 `config/channels.yaml` 注册频道，提供符合统一快照契约的 `papers.json`、`papers_full.json`、`meta.json`，再运行 `python scripts/update_project.py --skip-sync`。频道标签、颜色、筛选入口和详情摘要会随发布元数据自动出现。

## 重要语义

- /recent：过去 7 天实际发表，按 paper.date。
- RSS：按首次进入统一索引时间，用于订阅器感知新入库。
- 心理健康发布门槛：ai_relevance >= 3 且 domain_relevance >= 3。
- 关键词只负责召回候选，不直接决定正式发布。

## 暂未执行

- 旧网站下线或跳转
- 心理健康历史全量付费回填
