import type { Metadata } from "next";
import AboutStatus from "@/components/AboutStatus";
import { RssIcon } from "@/components/Icons";
import { Spectrum } from "@/components/Spectrum";

export const metadata: Metadata = { title: "关于" };

export default function AboutPage() {
  return (
    <main id="main-content" className="about-page">
      <section className="about-hero">
        <span className="eyebrow">ABOUT THE INDEX</span>
        <h1>不是三个论文站，<br />是一张跨领域的研究地图。</h1>
        <p>AI Papers 将分散在组织、交互和心理健康领域的 AI 研究合并为规范化论文实体。同一篇论文只出现一次，但会保留每个领域自己的分数、摘要和标签。</p>
        <div className="about-hero__spectrum"><Spectrum /></div>
      </section>

      <AboutStatus />

      <section className="about-section">
        <div className="about-section__intro"><span className="eyebrow">01 / COVERAGE</span><h2>三个频道，一个发布层</h2><p>频道颜色是阅读线索，不是三座孤岛。论文卡左侧的领域轨道会显示它命中的全部频道。</p></div>
        <div className="scope-grid">
          <article className="scope-card scope-card--ob"><span>OB</span><h3>组织与商业</h3><p>组织行为、管理、营销、消费者与信息系统中的 AI 研究。</p></article>
          <article className="scope-card scope-card--ur"><span>UR</span><h3>用户与交互</h3><p>用户研究、HCI、UX、CX 与服务设计中的 AI 研究。</p></article>
          <article className="scope-card scope-card--mh"><span>MH</span><h3>心理健康</h3><p>风险筛查、数字干预、临床协作、安全、隐私与伦理。</p></article>
        </div>
      </section>

      <section className="about-section about-method">
        <div className="about-section__intro"><span className="eyebrow">02 / METHOD</span><h2>相关度是领域化的</h2><p>同一篇论文在不同频道中可能有不同的判断。筛选器的“最低相关度”要求 AI 与当前领域两项分数同时达标。</p></div>
        <div className="method-scale"><div><b>5</b><span>核心议题</span><small>AI 与该领域共同构成研究核心</small></div><div><b>4</b><span>主要变量</span><small>不是背景提及，而是主要研究对象之一</small></div><div><b>3</b><span>实质涉及</span><small>对研究问题、方法或结果有实质作用</small></div><div><b>0–2</b><span>不公开展示</span><small>词汇命中或泛化提及，默认不进入论文流</small></div></div>
      </section>

      <section className="about-section semantics">
        <div className="about-section__intro"><span className="eyebrow">03 / FRESHNESS</span><h2>“最近发表”与“最近入库”不是一回事</h2></div>
        <div className="semantics-grid"><div><span>网站 /recent</span><h3>过去 7 天真实发表</h3><p>只使用论文发表日期，旧论文后补入库不会出现在这里。</p></div><div><span>RSS</span><h3>最近进入统一索引</h3><p>按首次进入统一索引的时间排序，适合订阅数据库新增内容。</p><a href="/rss.xml"><RssIcon />订阅 RSS</a></div></div>
      </section>
    </main>
  );
}
