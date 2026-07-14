"use client";

import Link from "next/link";
import { ArrowIcon, BookmarkIcon } from "@/components/Icons";
import { DomainTrack } from "@/components/Spectrum";
import type { ChannelDefinition, ChannelId, Paper } from "@/lib/types";
import { formatDate, getPaperProfile } from "@/lib/papers";
import { markRead } from "@/lib/storage";

export default function PaperCard({ paper, activeDomain, favorite, read, channels, onToggleFavorite }: {
  paper: Paper;
  activeDomain: ChannelId | null;
  favorite: boolean;
  read: boolean;
  channels: ChannelDefinition[];
  onToggleFavorite: (id: string) => void;
}) {
  const selected = getPaperProfile(paper, activeDomain);
  const definitions = new Map(channels.map((channel) => [channel.id, channel]));
  const profile = selected?.profile;
  const authorText = paper.authors.length > 3
    ? `${paper.authors.slice(0, 3).join("、")} 等`
    : paper.authors.join("、");

  return (
    <article className={`paper-card ${read ? "paper-card--read" : ""}`}>
      <DomainTrack channels={paper.channels} definitions={channels} />
      <div className="paper-card__body">
        <div className="paper-card__topline">
          <div className="paper-card__channels">
            {paper.channels.map((channel) => {
              const definition = definitions.get(channel);
              return <span key={channel} className="domain-label" style={definition ? { background: definition.soft_color, color: definition.color } : undefined}>{definition?.label || channel}</span>;
            })}
            {read ? <span className="read-label">已读</span> : null}
          </div>
          <button type="button" className={`bookmark-button ${favorite ? "is-active" : ""}`} onClick={() => onToggleFavorite(paper.id)} aria-label={favorite ? `取消收藏 ${paper.title_zh || paper.title}` : `收藏 ${paper.title_zh || paper.title}`} aria-pressed={favorite}>
            <BookmarkIcon filled={favorite} />
          </button>
        </div>
        <Link href={`/papers/${encodeURIComponent(paper.id)}`} prefetch={false} className="paper-card__title-link" onClick={() => markRead(paper.id)}>
          <h2>{paper.title_zh || paper.title}</h2>
          {paper.title_zh ? <p className="paper-card__english">{paper.title}</p> : null}
        </Link>
        <div className="paper-card__meta">
          <span className="paper-card__date">{formatDate(paper.date, paper.year)}</span>
          {paper.journal ? <span>{paper.journal}</span> : null}
          {authorText ? <span>{authorText}</span> : null}
        </div>
        {profile?.tldr ? <p className="paper-card__tldr">{profile.tldr}</p> : null}
        <div className="paper-card__footer">
          <div className="paper-card__tags">
            {profile?.topic_tags.slice(0, 3).map((tag) => <span key={tag}>#{tag}</span>)}
            {paper.ai_type_tags.slice(0, 2).map((tag) => <span key={`ai-${tag}`} className="ai-tag">{tag}</span>)}
          </div>
          <div className="paper-card__metrics">
            {profile ? <><span>AI <b>{profile.ai_score}</b></span><span>领域 <b>{profile.domain_score}</b></span></> : null}
            {paper.cited_by > 0 ? <span>引用 {paper.cited_by}</span> : null}
            <Link href={`/papers/${encodeURIComponent(paper.id)}`} prefetch={false} aria-label={`查看 ${paper.title_zh || paper.title} 详情`} onClick={() => markRead(paper.id)}><ArrowIcon /></Link>
          </div>
        </div>
      </div>
    </article>
  );
}
