import { demoPapers } from "@/lib/demo-data";
import { type ChannelProfile, type Meta, type Paper, type PaperDetail, type Updates } from "@/lib/types";

export class DataLoadError extends Error {
  constructor(public readonly path: string, message?: string) {
    super(message || `Unable to load ${path}`);
    this.name = "DataLoadError";
  }
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { cache: "no-store", signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new DataLoadError(path, `无法连接 ${path}`);
  }
  if (!response.ok) throw new DataLoadError(path, `${path} 返回 ${response.status}`);
  try {
    return (await response.json()) as T;
  } catch {
    throw new DataLoadError(path, `${path} 不是有效的 JSON`);
  }
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function normalizeProfile(value: unknown): ChannelProfile | null {
  if (!value || typeof value !== "object") return null;
  const profile = value as Record<string, unknown>;
  return {
    ai_score: Number(profile.ai_score ?? 0),
    domain_score: Number(profile.domain_score ?? 0),
    topic_tags: asStringArray(profile.topic_tags),
    tldr: typeof profile.tldr === "string" ? profile.tldr : null,
    ai_reason: typeof profile.ai_reason === "string" ? profile.ai_reason : null,
    evidence_stage: typeof profile.evidence_stage === "string" ? profile.evidence_stage : null,
    clinical_validation: typeof profile.clinical_validation === "string" ? profile.clinical_validation : null,
  };
}

export function normalizePaper(value: unknown): Paper {
  const raw = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
  const rawProfiles = (raw.channel_profiles && typeof raw.channel_profiles === "object"
    ? raw.channel_profiles
    : {}) as Record<string, unknown>;
  const channel_profiles: Paper["channel_profiles"] = {};
  for (const channel of Object.keys(rawProfiles)) {
    const normalized = normalizeProfile(rawProfiles[channel]);
    if (normalized) channel_profiles[channel] = normalized;
  }
  const channels = asStringArray(raw.channels);
  const legacyChannel = channels[0] || (typeof raw.channel === "string" ? raw.channel : null);
  if (!Object.keys(channel_profiles).length && legacyChannel) {
    channel_profiles[legacyChannel] = {
      ai_score: Number(raw.ai_score ?? 0),
      domain_score: Number(raw.domain_score ?? 0),
      topic_tags: asStringArray(raw.topic_tags),
      tldr: typeof raw.tldr === "string" ? raw.tldr : null,
      ai_reason: typeof raw.ai_reason === "string" ? raw.ai_reason : null,
    };
  }
  const normalizedChannels = channels.length
    ? channels
    : Object.keys(channel_profiles);
  return {
    id: String(raw.id ?? ""),
    doi: typeof raw.doi === "string" ? raw.doi : null,
    title: typeof raw.title === "string" ? raw.title : "Untitled",
    title_zh: typeof raw.title_zh === "string" ? raw.title_zh : null,
    date: typeof raw.date === "string" ? raw.date : null,
    year: Number.isFinite(Number(raw.year)) ? Number(raw.year) : null,
    journal: typeof raw.journal === "string" ? raw.journal : null,
    authors: asStringArray(raw.authors),
    channels: normalizedChannels,
    channel_profiles,
    source_refs: Array.isArray(raw.source_refs) ? raw.source_refs as Paper["source_refs"] : [],
    ai_type_tags: asStringArray(raw.ai_type_tags),
    cited_by: Number(raw.cited_by ?? 0),
    url: typeof raw.url === "string" ? raw.url : null,
    pdf_url: typeof raw.pdf_url === "string" ? raw.pdf_url : null,
    volume: typeof raw.volume === "string" ? raw.volume : null,
    issue: typeof raw.issue === "string" ? raw.issue : null,
  };
}

export async function loadPapers(signal?: AbortSignal): Promise<{ papers: Paper[]; demo: boolean }> {
  try {
    const raw = await fetchJson<unknown[]>("/data/papers.json", signal);
    if (!Array.isArray(raw)) throw new DataLoadError("/data/papers.json", "数据格式应为论文数组");
    return { papers: raw.map(normalizePaper).filter((paper) => paper.id), demo: false };
  } catch (error) {
    if (process.env.NODE_ENV === "development" && !(error instanceof DOMException && error.name === "AbortError")) {
      return { papers: demoPapers, demo: true };
    }
    throw error;
  }
}

export async function loadMeta(signal?: AbortSignal) {
  const meta = await fetchJson<Meta>("/data/meta.json", signal);
  return { ...meta, generated_at: meta.generated_at || meta.built_at };
}

export async function loadUpdates(signal?: AbortSignal) {
  return fetchJson<Updates>("/data/updates.json", signal);
}

export async function loadPaperDetail(id: string, signal?: AbortSignal): Promise<PaperDetail> {
  const raw = await fetchJson<Record<string, unknown>>(`/data/papers/${encodeURIComponent(id)}.json`, signal);
  const base = normalizePaper(raw);
  return {
    ...base,
    abstract: typeof raw.abstract === "string" ? raw.abstract : null,
    authors_full: Array.isArray(raw.authors_full) ? raw.authors_full as PaperDetail["authors_full"] : undefined,
  };
}
