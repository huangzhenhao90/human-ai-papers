import { CHANNEL_ORDER, type ChannelId, type ChannelProfile, type Paper } from "@/lib/types";

export function getPaperProfile(paper: Paper, active?: ChannelId | null): { channel: ChannelId; profile: ChannelProfile } | null {
  if (active && paper.channel_profiles[active]) {
    return { channel: active, profile: paper.channel_profiles[active]! };
  }
  let best: { channel: ChannelId; profile: ChannelProfile } | null = null;
  for (const channel of CHANNEL_ORDER) {
    const profile = paper.channel_profiles[channel];
    if (profile && (!best || Math.min(profile.ai_score, profile.domain_score) > Math.min(best.profile.ai_score, best.profile.domain_score))) {
      best = { channel, profile };
    }
  }
  return best;
}

export function paperScore(paper: Paper, active?: ChannelId | null) {
  const selected = getPaperProfile(paper, active);
  if (selected) return Math.min(selected.profile.ai_score, selected.profile.domain_score);
  return 0;
}

export function allTopicTags(paper: Paper, active?: ChannelId | null) {
  if (active) return paper.channel_profiles[active]?.topic_tags || [];
  return Array.from(new Set(CHANNEL_ORDER.flatMap((channel) => paper.channel_profiles[channel]?.topic_tags || [])));
}

export function matchesSearch(paper: Paper, query: string) {
  const q = query.trim().toLocaleLowerCase();
  if (!q) return true;
  const text = [
    paper.title,
    paper.title_zh,
    paper.journal,
    ...paper.authors,
    ...paper.ai_type_tags,
    ...allTopicTags(paper),
    ...CHANNEL_ORDER.flatMap((channel) => {
      const profile = paper.channel_profiles[channel];
      return profile ? [profile.tldr, profile.ai_reason] : [];
    }),
  ].filter(Boolean).join(" ").toLocaleLowerCase();
  return text.includes(q);
}

export function compareRecent(a: Paper, b: Paper) {
  const dateA = sortableDate(a);
  const dateB = sortableDate(b);
  return dateB.localeCompare(dateA) || a.id.localeCompare(b.id);
}

function sortableDate(paper: Paper) {
  const date = paper.date || String(paper.year || "0000");
  if (/^\d{4}$/.test(date)) return `${date}-00-00`;
  if (/^\d{4}-\d{2}$/.test(date)) return `${date}-00`;
  return date;
}

export function isPublishedInLastSevenDays(paper: Paper, now = new Date()) {
  if (!paper.date || !/^\d{4}-\d{2}-\d{2}$/.test(paper.date)) return false;
  const published = new Date(`${paper.date}T00:00:00`);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const elapsed = today.getTime() - published.getTime();
  return elapsed >= 0 && elapsed < 7 * 24 * 60 * 60 * 1000;
}

export function formatDate(date: string | null, year: number | null) {
  if (!date) return year ? String(year) : "日期待补";
  const full = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (full) return `${full[1]}.${full[2]}.${full[3]}`;
  return date.replaceAll("-", ".");
}

export function countValues(values: Array<string | number | null | undefined>) {
  const counts = new Map<string, number>();
  for (const value of values) {
    if (value === null || value === undefined || value === "") continue;
    const key = String(value);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-CN"));
}
