"use client";

import { useEffect, useState } from "react";
import { loadMeta, loadUpdates } from "@/lib/data";
import type { Meta, Updates } from "@/lib/types";

export default function AboutStatus() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [updates, setUpdates] = useState<Updates | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([loadMeta(controller.signal), loadUpdates(controller.signal)]).then(([metaResult, updateResult]) => {
      if (controller.signal.aborted) return;
      if (metaResult.status === "fulfilled") setMeta(metaResult.value);
      if (updateResult.status === "fulfilled") setUpdates(updateResult.value);
      if (metaResult.status === "rejected" && updateResult.status === "rejected") setFailed(true);
    });
    return () => controller.abort();
  }, []);

  const total = getTotal(meta, updates);
  const failures = Array.isArray(updates?.failures) ? updates!.failures!.length : 0;
  const stale = Array.isArray(updates?.stale_channels) ? updates!.stale_channels! : [];
  const pending = Array.isArray(updates?.pending_channels) ? updates!.pending_channels!.length : 0;
  const status = pending ? `${pending} 个频道正在回填` : stale.length || failures ? "部分来源沿用快照" : "最近一轮已完成";

  return (
    <div className="about-status" role="status">
      <div><span>公开论文</span><strong>{total === null ? "—" : total.toLocaleString("zh-CN")}</strong><small>规范化去重后</small></div>
      <div><span>最近更新</span><strong className="about-status__date">{meta?.generated_at ? formatTime(meta.generated_at) : "—"}</strong><small>{failed ? "状态文件暂不可用" : status}</small></div>
      <div><span>数据版本</span><strong className="about-status__version">{meta?.data_version ? String(meta.data_version) : "LATEST"}</strong><small>{failures ? `${failures} 个来源失败` : "报告可追踪"}</small></div>
    </div>
  );
}

function getTotal(meta: Meta | null, updates: Updates | null) {
  if (meta?.totals) {
    for (const key of ["papers", "papers_published", "papers_indexed", "total_papers"]) {
      const value = meta.totals[key];
      if (typeof value === "number") return value;
    }
  }
  const counts = updates?.counts;
  if (counts && typeof counts === "object" && "papers" in counts && typeof (counts as { papers?: unknown }).papers === "number") return (counts as { papers: number }).papers;
  return null;
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}
