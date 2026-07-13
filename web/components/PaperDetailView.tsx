"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { ArrowIcon, BookmarkIcon, RefreshIcon } from "@/components/Icons";
import { DomainTrack, Spectrum } from "@/components/Spectrum";
import { DataLoadError, loadMeta, loadPaperDetail, loadPapers } from "@/lib/data";
import { formatDate } from "@/lib/papers";
import { markRead, readFavorites, storageEvents, toggleFavorite } from "@/lib/storage";
import { DEFAULT_CHANNELS, channelDefinitions as getChannelDefinitions, channelMap, type ChannelDefinition, type PaperDetail } from "@/lib/types";

export default function PaperDetailView() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [detailMissing, setDetailMissing] = useState(false);
  const [favorite, setFavorite] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [channels, setChannels] = useState<ChannelDefinition[]>(DEFAULT_CHANNELS);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setDetailMissing(false);
    loadPaperDetail(id, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setPaper(value);
        markRead(value.id);
      })
      .catch(async (detailError) => {
        if (controller.signal.aborted) return;
        try {
          const { papers } = await loadPapers(controller.signal);
          const summary = papers.find((item) => item.id === id);
          if (!summary) throw detailError;
          setPaper(summary);
          setDetailMissing(true);
          markRead(summary.id);
        } catch (fallbackError) {
          if (!controller.signal.aborted) setError(fallbackError instanceof Error ? fallbackError : detailError);
        }
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [id, reloadKey]);

  useEffect(() => {
    const controller = new AbortController();
    loadMeta(controller.signal).then((value) => setChannels(getChannelDefinitions(value))).catch(() => undefined);
    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    const sync = () => setFavorite(readFavorites().has(id));
    sync();
    window.addEventListener(storageEvents.favorites, sync);
    return () => window.removeEventListener(storageEvents.favorites, sync);
  }, [id]);

  const authorText = useMemo(() => {
    if (!paper) return "";
    if (paper.authors_full?.length) return paper.authors_full.map((author) => author.name).join("、");
    return paper.authors.join("、");
  }, [paper]);
  const definitions = useMemo(() => channelMap(channels), [channels]);
  const profileChannels = useMemo(() => {
    if (!paper) return channels.map((channel) => channel.id);
    return [...channels.map((channel) => channel.id), ...Object.keys(paper.channel_profiles).filter((id) => !definitions[id])];
  }, [channels, definitions, paper]);

  if (loading) return <main id="main-content" className="detail-shell" aria-busy="true"><div className="skeleton skeleton--detail" /><span className="sr-only">正在加载论文详情</span></main>;
  if (error || !paper) {
    const path = error instanceof DataLoadError ? error.path : `/data/papers/${id}.json`;
    return <main id="main-content" className="state-page"><span className="state-page__code">PAPER / NOT FOUND</span><h1>这篇论文的详情暂时不可用</h1><p>未能从 <code>{path}</code> 读取详情，且统一索引中没有可回退的列表信息。</p><div className="state-page__actions"><button type="button" onClick={() => setReloadKey((key) => key + 1)}><RefreshIcon />重试</button><Link href="/">返回论文流</Link></div></main>;
  }

  return (
    <main id="main-content" className="detail-shell">
      <Link href="/" className="back-link"><ArrowIcon />返回论文流</Link>
      {detailMissing ? <div className="notice notice--warning"><b>详情文件待补</b><span>列表页仍可正常使用，当前先展示索引中的摘要信息。</span></div> : null}

      <article className="paper-detail">
        <DomainTrack channels={paper.channels} definitions={channels} />
        <header className="paper-detail__header">
          <div className="paper-detail__channels">
            {paper.channels.map((channel) => <span className="domain-label" style={definitions[channel] ? { background: definitions[channel].soft_color, color: definitions[channel].color } : undefined} key={channel}>{definitions[channel]?.label || channel}</span>)}
          </div>
          <button type="button" className={`bookmark-button bookmark-button--detail ${favorite ? "is-active" : ""}`} onClick={() => { setFavorite(toggleFavorite(paper.id)); }} aria-label={favorite ? "取消收藏" : "收藏论文"} aria-pressed={favorite}><BookmarkIcon filled={favorite} />{favorite ? "已收藏" : "收藏"}</button>
          <p className="paper-detail__date">{formatDate(paper.date, paper.year)} {paper.journal ? `· ${paper.journal}` : ""}</p>
          <h1>{paper.title_zh || paper.title}</h1>
          {paper.title_zh ? <h2>{paper.title}</h2> : null}
          {authorText ? <p className="paper-detail__authors">{authorText}</p> : null}
          <div className="paper-detail__actions">
            {paper.url ? <a href={paper.url} target="_blank" rel="noreferrer">查看原文 <ArrowIcon /></a> : null}
            {paper.pdf_url ? <a href={paper.pdf_url} target="_blank" rel="noreferrer">PDF <ArrowIcon /></a> : null}
            {paper.doi ? <span>DOI {paper.doi}</span> : null}
          </div>
        </header>

        <div className="paper-detail__spectrum"><Spectrum /></div>

        <div className="profile-stack">
          {profileChannels.map((channel) => {
            const profile = paper.channel_profiles[channel];
            if (!profile) return null;
            const definition = definitions[channel];
            return (
              <section className="channel-profile channel-profile--dynamic" style={{ "--channel-color": definition?.color || "#6d7a7b", "--channel-soft": definition?.soft_color || "#eef3f1" } as CSSProperties} key={channel}>
                <div className="channel-profile__heading"><span>{definition?.short || channel.toUpperCase()}</span><div><p>{definition?.label || channel}</p><h2>领域摘要</h2></div><dl><div><dt>AI</dt><dd>{profile.ai_score}</dd></div><div><dt>领域</dt><dd>{profile.domain_score}</dd></div></dl></div>
                {profile.tldr ? <p className="channel-profile__tldr">{profile.tldr}</p> : <p className="channel-profile__empty">该领域摘要待补。</p>}
                {profile.topic_tags.length ? <div className="channel-profile__tags">{profile.topic_tags.map((tag) => <span key={tag}>#{tag}</span>)}</div> : null}
                {profile.evidence_stage || profile.clinical_validation ? <div className="channel-profile__evidence">{profile.evidence_stage ? <span>证据阶段：{profile.evidence_stage}</span> : null}{profile.clinical_validation ? <span>临床验证：{profile.clinical_validation}</span> : null}</div> : null}
                {profile.ai_reason ? <details><summary>查看评分理由</summary><p>{profile.ai_reason}</p></details> : null}
              </section>
            );
          })}
        </div>

        {paper.ai_type_tags.length ? <section className="detail-section"><span className="eyebrow">AI TYPE</span><h2>AI 类型</h2><div className="detail-tags">{paper.ai_type_tags.map((tag) => <span key={tag}>{tag}</span>)}</div></section> : null}
        {paper.abstract ? <section className="detail-section abstract"><span className="eyebrow">ORIGINAL ABSTRACT</span><h2>原始摘要</h2><p>{paper.abstract}</p></section> : null}
        {paper.authors_full?.some((author) => author.affiliation?.length) ? <section className="detail-section affiliations"><span className="eyebrow">AUTHORS</span><h2>作者与机构</h2>{paper.authors_full.map((author) => <div key={`${author.name}-${author.orcid || ""}`}><b>{author.name}</b><span>{author.affiliation?.join("；")}</span>{author.orcid ? <small>ORCID {author.orcid}</small> : null}</div>)}</section> : null}
      </article>
    </main>
  );
}
