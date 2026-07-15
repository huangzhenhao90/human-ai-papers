"use client";

import Link from "next/link";
import type { ChannelId, Paper } from "@/lib/types";
import { formatDate, getPaperProfile } from "@/lib/papers";
import { markRead } from "@/lib/storage";

export default function PaperCard({ paper, activeDomain, favorite, read, onToggleFavorite }: {
  paper: Paper;
  activeDomain: ChannelId | null;
  favorite: boolean;
  read: boolean;
  onToggleFavorite: (id: string) => void;
}) {
  const selected = getPaperProfile(paper, activeDomain);
  const profile = selected?.profile;
  const authorText = paper.authors.length > 3
    ? `${paper.authors.slice(0, 3).join("、")} 等`
    : paper.authors.join("、");

  return (
    <article className={`paper-card ${read ? "paper-card--read" : ""}`} onClick={() => markRead(paper.id)}>
      <div className="paper-card__body">
        <div className="paper-card__topline">
          <Link href={`/papers/${encodeURIComponent(paper.id)}`} prefetch={false} className="paper-card__title-link" onClick={() => markRead(paper.id)}>
            <h2>{read ? <span className="read-dot" title="已读">●</span> : null}{paper.title}</h2>
            {paper.title_zh ? <p className="paper-card__chinese">{paper.title_zh}</p> : null}
          </Link>
          <button type="button" className={`favorite-button ${favorite ? "is-active" : ""}`} onClick={() => onToggleFavorite(paper.id)} aria-label={favorite ? `取消收藏 ${paper.title_zh || paper.title}` : `收藏 ${paper.title_zh || paper.title}`} aria-pressed={favorite}>
            {favorite ? "★" : "☆"}
          </button>
        </div>
        <div className="paper-card__meta">
          {paper.journal ? <span className="paper-card__journal">{paper.journal}</span> : null}
          <span className="paper-card__date">{formatDate(paper.date, paper.year)}</span>
          {authorText ? <span>{authorText}</span> : null}
          {paper.cited_by > 0 ? <span>引用 {paper.cited_by}</span> : null}
        </div>
        {profile?.tldr ? <p className="paper-card__tldr">{profile.tldr}</p> : null}
        {(profile?.topic_tags.length || paper.ai_type_tags.length) ? (
          <div className="paper-card__tags">
            {profile?.topic_tags.slice(0, 5).map((tag) => <span key={tag}>{tag}</span>)}
            {paper.ai_type_tags.slice(0, 3).map((tag) => <span key={`ai-${tag}`} className="ai-tag">{tag}</span>)}
          </div>
        ) : null}
        {(paper.url || paper.pdf_url || paper.doi) ? (
          <div className="paper-card__sources">
            {paper.url ? <a href={paper.url} target="_blank" rel="noopener noreferrer">原文 ↗</a> : null}
            {paper.pdf_url ? <a href={paper.pdf_url} target="_blank" rel="noopener noreferrer">PDF ↗</a> : null}
            {paper.doi ? <span>{paper.doi}</span> : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}
