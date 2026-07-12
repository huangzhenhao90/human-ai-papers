# 统一 AI Papers 项目设计

日期：2026-07-12  
项目目录：/Users/huang/Desktop/自己做的AI分析/human-ai-papers  
产品名：AI Papers  
状态：待用户确认书面规格

## 1. 目标

新建一个独立项目，把现有 ob-ai-papers 与 ur-ai-papers 接入同一套发布契约和网站，并新增“心理健康 × AI”研究频道。

网站打开后直接进入统一论文流。用户可在“全部领域、组织与商业、用户与交互、心理健康”之间切换，也可跨领域搜索、筛选、查看最近发表和收藏论文。

现有两个项目保持不动，作为可回溯的历史来源；新项目完成本地验收前，不下线旧网站、不修改旧仓库、不创建远端仓库或部署。

## 2. 产品结构

### 2.1 一级研究频道

| 频道 ID | 页面名称 | 主要范围 |
| --- | --- | --- |
| ob | 组织与商业 | 组织行为、管理、营销、消费者、信息系统中的 AI 研究 |
| ur | 用户与交互 | 用户研究、HCI、UX、CX、服务设计中的 AI 研究 |
| mh | 心理健康 | 心理健康筛查、评估、干预、支持、临床工作流、安全与伦理中的 AI 研究 |

一篇论文可以属于多个频道。统一论文流只展示一个规范化论文实体，并同时显示它命中的全部频道，避免当前两个项目中交叉期刊和重复 DOI 造成重复卡片。

### 2.2 页面与路由

- /：统一论文流，默认“全部领域”
- /?domain=ob|ur|mh：同一页面内切换研究频道
- /recent：按论文发表日期展示过去 7 天发表的论文，不使用入库时间伪造“新论文”
- /favorites：跨领域收藏
- /papers/[id]：统一论文详情
- /about：范围、来源、评分口径与更新说明
- /rss.xml：统一 RSS；后续可扩展为按频道订阅

### 2.3 首页

按已确认的设计草图实现：

- 顶部为 AI Papers 品牌和“全部论文、最近发表、我的收藏、关于、RSS”导航。
- 首屏说明“追踪 AI 如何改变人、组织与心理健康”。
- 三个频道使用固定但低饱和的颜色：组织与商业为绿色，用户与交互为蓝色，心理健康为紫色。
- 频道颜色只用于导航、论文卡左侧标识和少量状态，不把页面拆成三个视觉上互不相干的网站。
- 左栏保留高密度筛选；右侧为搜索、排序和论文卡片。
- 手机端隐藏固定侧栏，把筛选收进抽屉；核心搜索、频道切换和论文信息不丢失。

## 3. 数据架构

### 3.1 三个频道数据库 + 一个统一发布层

初版不直接物理合并两个旧 SQLite。现有数据库的 paper_scores 和 llm_outputs 都以 paper_id 为唯一键，只能保存一套领域分与标签；直接合并会覆盖同一篇论文在不同频道下的不同判断，而且两个数据库的数字 ID 区间互相冲突。

新项目采用：

    OB 发布数据 ─┐
    UR 发布数据 ─┼→ 频道适配器 → 稳定 ID / 跨频道去重 → 统一发布 JSON → 一个网站
    MH 主题 DB  ─┘

- OB、UR 在第一阶段继续使用各自经过验证的数据库和每日更新。
- 新项目每天同步两个旧项目的已发布 JSON，不从脏工作树直接复制数据。
- 心理健康使用新项目内的独立 SQLite 与原生更新流水线。
- 统一发布层只合并公开数据，不覆盖各频道原始评分、判断理由、TL;DR 与标签。
- 后续可以把 OB、UR 更新任务迁入新项目的共享核心，但前端发布契约和稳定 ID 不变。

建议目录：

    human-ai-papers/
      config/themes/
        ob.yaml
        ur.yaml
        mental-health.yaml
      src/core/
      src/adapters/
        legacy_ob.py
        legacy_ur.py
        native_theme.py
      data/db/
        mental-health.db
      publisher/
        stable_id.py
        normalize_contract.py
        merge_channels.py
        build_rss.py
      web/

### 3.2 去重规则

按以下顺序确定同一论文：

1. 规范化 DOI；
2. arXiv ID；
3. 规范化标题 + 发表年份 + 第一作者指纹；
4. 指纹冲突或关键信息不一致时保留为两篇，并写入迁移报告供人工复核。

统一索引先生成规范键，不沿用任一旧库的数字 ID：

- doi: 加小写规范化 DOI；
- arxiv: 加去掉版本号的 arXiv ID；
- 没有以上标识时，使用规范化标题 + 发表年份 + 第一作者生成的确定性哈希。

公开 id 使用规范键的确定性 SHA-256 摘要并编码为 URL 安全字符串，例如 p_7m3x...。规范键保留在发布报告中，不直接拿带斜杠的 DOI 当文件名或路由参数。

同一论文在不同频道中的分数、理由、TL;DR 和主题标签分别保存在 channel_profiles，不互相覆盖。跨频道公共字段优先采用信息更完整、更新时间更晚的记录，并保留 source_refs。

### 3.3 旧项目接入

提供可重复运行的同步与统一发布脚本：

    python scripts/sync_legacy.py \
      --ob ../ob-ai-papers \
      --ur ../ur-ai-papers

    python scripts/build_unified_index.py

同步与发布脚本执行：

- 从两个旧项目的正式发布版本读取 papers.json、papers_full.json 与 meta.json；
- 适配 OB、UR 当前略有差异的导出字段；
- 按 DOI / arXiv ID / 指纹合并重复论文；
- 给旧数字 ID 建立带频道的 source_refs；
- 生成 data/reports/unified-publish-report.json，记录输入数、规范论文数、跨频道重复数、冲突和跳过项；
- 可重复运行且不会重复插入。

UR 当前本地工作树落后其正式远端版本且有未提交的 meta.json 修改，因此接入必须读取 origin/main 或正式发布资产，不能直接复制当前本地文件。旧项目中的历史原始抓取记录继续留在旧仓库中审计；心理健康的新抓取记录写入新项目数据库。

## 4. 心理健康频道

### 4.1 纳入范围

纳入 AI 在以下心理健康场景中的研究：

- 风险筛查、症状识别、预测与评估；
- 数字心理干预、支持性对话、治疗辅助和个性化支持；
- 临床决策支持、心理服务工作流与专业人员协作；
- 危机识别、偏差、公平、隐私、安全、责任和监管；
- 心理健康产品的可用性、信任、依从性、关系体验与实际效果。

排除：

- 没有心理健康结局或场景的通用医疗 AI；
- 仅做脑影像、药物或生物标志物建模且不涉及心理健康服务、评估或结果的研究；
- 只在摘要中泛泛提及 wellbeing、emotion 或 mental health 的论文；
- 无研究内容的新闻、社论和产品宣传。

### 4.2 来源策略

心理健康文献比 OB、UR 更分散，来源配置增加 ingest_mode: full | query。初版来源分为四层：

1. 整刊召回、后置打分：Nature Mental Health、JMIR Mental Health、The Lancet Psychiatry、JAMA Psychiatry、American Journal of Psychiatry、World Psychiatry、Psychological Medicine、Journal of Affective Disorders、Translational Psychiatry、Internet Interventions、BJPsych Open、Clinical Psychological Science。
2. 只做“AI 强信号 AND 心理健康强信号”查询召回：npj Digital Medicine、The Lancet Digital Health、Journal of Medical Internet Research、JMIR AI、Artificial Intelligence in Medicine、Journal of Biomedical Informatics、IEEE Journal of Biomedical and Health Informatics、NEJM AI、PLOS Digital Health。
3. 会议：CLPsych 全量；CHI、CSCW 复用 UR 数据并增加心理健康频道判断；CHIL、ML4H、MLHC、AMIA Annual Symposium 使用关键词预过滤。
4. arXiv：首期使用 cs.CL、cs.HC、cs.AI、cs.LG、cs.CY、cs.SI、stat.ML、eess.AS，并强制同时命中 AI 与心理健康信号。

具体 ISSN、OpenAlex Source ID 和抓取方式写入 config/themes/mental-health.yaml，实施时逐项用出版方或官方索引核验，不凭名称猜测 ID。PubMed E-utilities 与中文核心期刊 RIS 导入列为第二阶段，避免首版同时引入新的检索协议。

首轮范围核验入口：

- Nature Mental Health aims and scope：https://www.nature.com/natmentalhealth/aims
- JMIR Mental Health focus and scope：https://mental.jmir.org/about-journal/focus-and-scope
- Internet Interventions：https://www.sciencedirect.com/journal/internet-interventions
- CLPsych proceedings：https://aclanthology.org/venues/clpsych/
- NCBI E-utilities（二期）：https://www.ncbi.nlm.nih.gov/home/develop/api/

### 4.3 评分

每篇候选论文分别得到：

- ai_relevance：AI 是否是实质研究对象或方法，0–5；
- domain_relevance：是否实质属于心理健康研究，0–5；
- evidence_stage：研究证据类型，包括概念观点、基准开发、回顾性验证、用户研究、前瞻性研究、真实部署、RCT、系统综述；
- clinical_validation：无、内部验证、外部验证、前瞻性、RCT；
- safety_evaluated、real_world_deployment、ground_truth_quality；
- 受控标签组：疾病/议题、应用场景、人群、AI 类型、证据阶段与风险。

公开论文流默认仍要求 AI 相关度与频道相关度均不低于 3。关键词只负责候选召回，不直接决定是否发布。

以下误召回在评分提示中明确判为心理健康相关度不高于 2：只有情绪或 sentiment 识别而无心理健康结局；技术语境中的 attention、stress testing、hallucination；泛医疗 AI；纯算法或纯数据集；只因 therapy、counseling、emotion、stress 单词命中；纯神经科学而无精神障碍或心理健康应用。

## 5. 采集与每日更新

### 5.1 配置驱动

新项目共享连接器、适配器和统一发布代码，频道差异放在配置中：

    config/
      themes/
        ob.yaml
        ur.yaml
        mental-health.yaml
      sources/
        journals.yaml
        conferences.yaml
      ai_types.yaml

第一阶段只有心理健康在新项目内原生抓取；OB、UR 通过正式发布 JSON 接入。交叉论文由统一发布层合并，不重复显示。

### 5.2 更新流程

    定时任务
      ├→ 同步 OB 正式发布数据
      ├→ 同步 UR 正式发布数据
      └→ 更新心理健康主题 DB
            → 增量抓取
            → 规范化
            → 只对本轮新候选做 AI 与心理健康打分
            → 为达到阈值的论文生成中文标题、TL;DR 与标签
      → 统一适配、稳定 ID、跨频道去重
      → 导出统一 JSON、RSS 和更新报告
      → 前端构建

LLM 安全阀按“心理健康本轮新增候选”控制，旧积压不能阻断当天更新。单个来源失败写入运行报告并继续处理其他来源；OB 或 UR 同步失败时保留上一版成功快照并在 updates.json 标记陈旧状态。

全量心理健康历史回填与每日增量分开。实现阶段可以完成免费元数据回填和小批量端到端验证；大批量付费 LLM 评分在输出候选量与预计调用量后再执行。

## 6. 前端数据契约

web/public/data/papers.json 的每篇论文至少包含：

    {
      "id": "p_7m3xexample",
      "title": "English title",
      "title_zh": "中文标题",
      "date": "2026-07-01",
      "journal": "Journal",
      "authors": ["Author A"],
      "channels": ["ur", "mh"],
      "channel_profiles": {
        "ur": {
          "ai_score": 5,
          "domain_score": 4,
          "topic_tags": ["用户体验"],
          "tldr": "用户与交互视角摘要"
        },
        "mh": {
          "ai_score": 5,
          "domain_score": 4,
          "topic_tags": ["数字干预"],
          "tldr": "心理健康视角摘要"
        }
      },
      "source_refs": [
        {"channel": "ur", "legacy_id": 123},
        {"channel": "mh", "legacy_id": 456}
      ],
      "ai_type_tags": ["LLM"],
      "cited_by": 0,
      "url": "https://...",
      "pdf_url": "https://..."
    }

同时导出：

- papers/[stable-id].json：每篇详情按需加载，避免三个频道合并后浏览器下载整个完整数据集；
- meta.json：每个频道和动态筛选维度的统计、生成时间、数据版本；
- coverage.json：按来源和频道的覆盖审计；
- updates.json：本轮新增、更新、失败、跳过和安全阀状态；
- rss.xml：统一订阅源，按首次进入统一索引的时间排序；它与 /recent 的“最近发表”语义明确分开。

## 7. 错误、空状态与可追踪性

- 数据加载失败：页面说明失败的数据文件和重试方式，不显示永久“加载中”。
- 某频道暂无论文：保留频道入口，说明正在回填或当前筛选没有结果。
- 全部筛选无结果：显示清空筛选动作。
- 详情数据缺失：列表页仍可用，并提供原始论文链接。
- 每次更新生成机器可读报告；前端“关于”页显示最近成功更新时间与部分失败状态。

## 8. 测试与验收

### 8.1 数据测试

- 相同 DOI 从 OB、UR 发布数据进入统一索引后只生成一篇论文，并具有两个 channel_profiles。
- 无 DOI 论文通过 arXiv ID 或指纹正确去重。
- 冲突记录不静默覆盖。
- 同步与统一发布脚本重复运行结果不变。
- 旧数字 ID 不会直接出现在统一详情路由、收藏或已读状态中。
- 最近发表严格按 date 过滤和排序。
- 旧积压不会阻断本轮新增论文的评分。
- 三频道导出统计与各自正式输入一致。

### 8.2 前端测试

- 统一、单频道、搜索、年份、期刊、主题、AI 类型和最低相关度筛选可组合使用。
- 收藏和已读状态跨频道共用。
- 论文详情保留全部频道与各自标签。
- 桌面与手机布局均可用，键盘焦点清晰，并尊重减少动画设置。
- npm run build 通过；浏览器验证首页、最近发表、收藏、详情和空状态。

### 8.3 本地完成标准

- 新项目可从空环境安装依赖并启动；
- 两个旧项目的正式发布数据通过适配器接入，报告可审计；
- 心理健康配置、抓取、规范化、评分和导出至少完成一个受控小批量端到端验证；
- 首页与已确认草图一致，使用真实合并数据；
- Python 测试、前端构建和浏览器冒烟测试通过；
- 不修改两个旧项目，不包含 API 密钥、数据库快照或其他敏感文件。

## 9. 实施顺序

1. 定义稳定 ID、统一发布契约和跨频道去重测试；
2. 编写 OB、UR 适配器并接入正式发布数据；
3. 配置并小批量跑通心理健康独立流水线；
4. 实现统一发布、逐论文详情文件和更新报告；
5. 实现已确认的统一前端；
6. 验证更新链路、构建、浏览器交互和统一发布报告；
7. 用户本地验收后，再决定是否把 OB、UR 后端迁入新仓库，以及 GitHub、Vercel、旧站跳转和全量付费回填。

## 10. 明确不在本轮自动执行的事项

- 不删除、重写或归档 ob-ai-papers、ur-ai-papers；
- 不在首版物理合并两个旧 SQLite，也不改写它们的更新任务；
- 不自动迁移旧网站不同域名下的浏览器收藏数据；
- 不创建 GitHub 远端仓库、不推送、不部署 Vercel；
- 不在没有候选量与调用量报告的情况下执行大批量付费 LLM 回填。
