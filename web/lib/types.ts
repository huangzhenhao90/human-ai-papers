export type ChannelId = string;

export type ChannelDefinition = {
  id: ChannelId;
  short: string;
  label: string;
  description: string;
  color: string;
  soft_color: string;
  order: number;
  required: boolean;
  papers?: number;
  status?: string;
};

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
  channels?: Record<ChannelId, number | Partial<ChannelDefinition> & { papers?: number; count?: number }>;
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

export const DEFAULT_CHANNELS: ChannelDefinition[] = [
  {
    id: "ob",
    short: "OB",
    label: "组织与商业",
    description: "管理、组织行为、营销与消费者研究",
    color: "#3f6b59",
    soft_color: "#e8f0ec",
    order: 10,
    required: true,
  },
  {
    id: "ur",
    short: "UR",
    label: "用户与交互",
    description: "用户研究、HCI、UX、CX 与服务设计",
    color: "#476e8f",
    soft_color: "#e9f0f5",
    order: 20,
    required: true,
  },
  {
    id: "mh",
    short: "MH",
    label: "心理健康",
    description: "筛查、干预、临床协作、安全与伦理",
    color: "#79506e",
    soft_color: "#f2eaf0",
    order: 30,
    required: false,
  },
];

export const CHANNELS: Record<ChannelId, ChannelDefinition> = Object.fromEntries(
  DEFAULT_CHANNELS.map((channel) => [channel.id, channel]),
) as Record<ChannelId, ChannelDefinition>;

export const CHANNEL_ORDER: ChannelId[] = DEFAULT_CHANNELS.map((channel) => channel.id);

export function channelDefinitions(meta?: Meta | null): ChannelDefinition[] {
  if (!meta?.channels || typeof meta.channels !== "object") return DEFAULT_CHANNELS;
  const definitions = Object.entries(meta.channels).flatMap(([id, raw]) => {
    if (!raw || typeof raw !== "object") return [];
    const fallback = CHANNELS[id];
    const value = raw as Partial<ChannelDefinition> & { count?: number };
    if (!value.label || !value.short || !value.color || !value.soft_color) return fallback ? [fallback] : [];
    return [{
      id,
      short: value.short,
      label: value.label,
      description: value.description || "",
      color: value.color,
      soft_color: value.soft_color,
      order: Number(value.order ?? 999),
      required: Boolean(value.required),
      papers: Number(value.papers ?? value.count ?? 0),
      status: value.status,
    }];
  });
  return definitions.length ? definitions.sort((a, b) => a.order - b.order || a.id.localeCompare(b.id)) : DEFAULT_CHANNELS;
}

export function channelMap(definitions: ChannelDefinition[]): Record<ChannelId, ChannelDefinition> {
  return Object.fromEntries(definitions.map((channel) => [channel.id, channel]));
}

export function isChannel(value: unknown, definitions: ChannelDefinition[] = DEFAULT_CHANNELS): value is ChannelId {
  return typeof value === "string" && definitions.some((channel) => channel.id === value);
}
