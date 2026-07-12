export type ChannelId = "ob" | "ur" | "mh";

export type ChannelProfile = {
  ai_score: number;
  domain_score: number;
  topic_tags: string[];
  tldr: string | null;
  ai_reason?: string | null;
  evidence_stage?: string | null;
  clinical_validation?: string | null;
};

export type SourceRef = {
  channel: ChannelId;
  legacy_id?: string | number;
  source?: string;
};

export type Paper = {
  id: string;
  doi?: string | null;
  title: string;
  title_zh: string | null;
  date: string | null;
  year: number | null;
  journal: string | null;
  authors: string[];
  channels: ChannelId[];
  channel_profiles: Partial<Record<ChannelId, ChannelProfile>>;
  source_refs: SourceRef[];
  ai_type_tags: string[];
  cited_by: number;
  url: string | null;
  pdf_url: string | null;
  volume?: string | null;
  issue?: string | null;
};

export type PaperDetail = Paper & {
  abstract?: string | null;
  authors_full?: Array<{
    name: string;
    affiliation?: string[];
    orcid?: string;
  }>;
};

export type Meta = {
  generated_at?: string;
  built_at?: string;
  data_version?: string | number;
  totals?: Record<string, number>;
  channels?: Partial<Record<ChannelId, number | { papers?: number; count?: number }>>;
  facets?: Record<string, Record<string, number>>;
};

export type Updates = {
  generated_at?: string;
  built_at?: string;
  status?: string;
  stale_channels?: string[];
  pending_channels?: string[];
  failures?: Array<string | { source?: string; message?: string; error?: string }>;
  [key: string]: unknown;
};

export const CHANNELS: Record<ChannelId, { short: string; label: string; description: string }> = {
  ob: {
    short: "OB",
    label: "组织与商业",
    description: "管理、组织行为、营销与消费者研究",
  },
  ur: {
    short: "UR",
    label: "用户与交互",
    description: "用户研究、HCI、UX、CX 与服务设计",
  },
  mh: {
    short: "MH",
    label: "心理健康",
    description: "筛查、干预、临床协作、安全与伦理",
  },
};

export const CHANNEL_ORDER: ChannelId[] = ["ob", "ur", "mh"];

export function isChannel(value: unknown): value is ChannelId {
  return value === "ob" || value === "ur" || value === "mh";
}
