# AI Papers 项目协作规则

## 项目目标

本仓库提供一个统一网站，聚合三个频道：

- ob：组织与商业
- ur：用户与交互
- mh：心理健康

## 不可破坏的契约

1. ob-ai-papers 与 ur-ai-papers 是只读上游，未经用户单独授权不得修改、提交、推送或停用。
2. 同一论文可属于多个频道；统一发布时去重，但 channel_profiles 不能互相覆盖。
3. 公开 ID 必须由 canonical key 确定性生成，不能直接复用旧 SQLite 数字 ID。
4. /recent 永远表示过去 7 天实际发表，按 paper.date 判断；RSS 可按首次进入统一索引时间排序，两者文案不得混用。
5. 心理健康正式发布要求 ai_relevance >= 3 且 domain_relevance >= 3。关键词只召回候选，不能直接决定发布。
6. 大批量付费 LLM 回填必须先报告候选量、调用上限与预计影响；默认只允许 dry-run 或小批量验证。
7. 不提交 .env、API key、SQLite 快照、抓取缓存或其他敏感数据。

## 验证要求

每次修改至少执行与改动相称的验证：

- 发布层：pytest
- 心理健康流水线：配置、召回和输出契约测试
- 前端：npm run build
- 页面交互：桌面和手机尺寸浏览器冒烟测试

更新链路不能只看任务成功；还要分别检查 papers.json、meta.json、updates.json、rss.xml 与可见页面。

## 项目状态入口

- 当前进展：00_项目进展.md
- 文件索引：00_项目索引.md
- 设计规格：docs/superpowers/specs/2026-07-12-unified-ai-papers-design.md
- 实施计划：docs/superpowers/specs/2026-07-12-unified-ai-papers-implementation.md
