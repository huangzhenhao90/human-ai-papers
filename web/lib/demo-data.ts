import type { Paper } from "@/lib/types";

// Development-only safety net. Production surfaces a real data-loading error instead.
export const demoPapers: Paper[] = [
  {
    id: "demo_ob",
    title: "Human–AI Collaboration and the Changing Shape of Work",
    title_zh: "人机协作如何重塑工作",
    date: "2026-07-10",
    year: 2026,
    journal: "Demonstration journal",
    authors: ["Demo Author"],
    channels: ["ob"],
    channel_profiles: {
      ob: { ai_score: 5, domain_score: 4, topic_tags: ["人机协作"], tldr: "开发模式下的示意数据：发布层数据就绪后会自动替换。" },
    },
    source_refs: [], ai_type_tags: ["LLM"], cited_by: 0, url: null, pdf_url: null,
  },
  {
    id: "demo_ur_mh",
    title: "Designing Safe Conversational Support for Mental Health",
    title_zh: "面向心理健康的安全对话支持设计",
    date: "2026-07-08",
    year: 2026,
    journal: "Demonstration journal",
    authors: ["Demo Author"],
    channels: ["ur", "mh"],
    channel_profiles: {
      ur: { ai_score: 5, domain_score: 5, topic_tags: ["对话式 AI", "安全"], tldr: "从用户与交互视角检查心理支持系统的设计。" },
      mh: { ai_score: 5, domain_score: 5, topic_tags: ["数字干预", "安全"], tldr: "从心理健康视角评估支持性对话的安全边界。" },
    },
    source_refs: [], ai_type_tags: ["对话式 AI"], cited_by: 0, url: null, pdf_url: null,
  },
];
