# 增加一个研究频道

## 1. 注册频道

在 `config/channels.yaml` 的 `channels` 数组末尾增加一项：

```yaml
- id: edu
  short: EDU
  label: 教育与学习
  description: 学习科学、教学设计与教育技术
  color: "#8a6338"
  soft_color: "#f4ede3"
  order: 40
  required: false
  data_dir: data/exports/education
  source_kind: native
```

`id` 只能使用小写字母、数字和连字符；`order` 必须唯一。新频道首次回填期间建议设为 `required: false`，数据稳定后再改为 `true`。

## 2. 提供频道快照

`data_dir` 至少包含：

- `papers.json`：列表字段。
- `papers_full.json`：详情字段；可以比列表多摘要、完整作者等信息。
- `meta.json`：至少包含 `generated_at`。

每篇论文必须有标题，并尽量提供 DOI 或 arXiv ID；没有标准标识符时，统一层会用规范化标题、年份和第一作者生成指纹。评分字段使用 `ai_score` 与 `domain_score`，频道摘要与标签使用 `tldr`、`topic_tags`。

## 3. 构建并校验

```bash
python scripts/update_project.py --skip-sync
pytest -q
cd web && npm run typecheck && npm run build
```

发布层会自动完成稳定 ID、跨频道去重、频道画像合并、筛选计数、详情文件、RSS 与覆盖率报告。前端从 `meta.json` 读取频道注册信息，不需要为新频道增加 React 分支或 CSS 类。

## 4. 接入自动数据源

频道注册只定义发布边界；抓取与评分仍应放在独立适配器中，最终写出上述快照契约。若要加入每日任务，把适配器接到 `scripts/update_project.py`，并保留以下规则：

- 单频道失败时沿用上一版有效快照，并在 `updates.json` 标记 `stale` 与失败原因。
- 付费模型调用必须显式开启并设置硬上限。
- 关键词只负责候选召回，不能绕过正式发布阈值。
