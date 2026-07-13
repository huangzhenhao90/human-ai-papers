"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import ChannelTabs from "@/components/ChannelTabs";
import FilterPanel, { type Facets, type FilterValues } from "@/components/FilterPanel";
import { CloseIcon, FilterIcon, RefreshIcon, SearchIcon } from "@/components/Icons";
import PaperCard from "@/components/PaperCard";
import { Spectrum } from "@/components/Spectrum";
import { DataLoadError, loadMeta, loadPapers, loadUpdates } from "@/lib/data";
import { allTopicTags, compareRecent, countValues, isPublishedInLastSevenDays, matchesSearch, paperScore } from "@/lib/papers";
import { readFavorites, readReadIds, storageEvents, toggleFavorite } from "@/lib/storage";
import { CHANNELS, CHANNEL_ORDER, isChannel, type ChannelId, type Meta, type Paper, type Updates } from "@/lib/types";

export type ExplorerMode = "all" | "recent" | "favorites";

const PAGE_SIZE = 24;

const heroCopy: Record<ExplorerMode, { eyebrow: string; title: string; description: string }> = {
  all: {
    eyebrow: "HUMAN × AI RESEARCH INDEX",
    title: "追踪 AI 如何改变人、组织与心理健康",
    description: "一个跨领域的中文论文索引。将组织与商业、用户与交互、心理健康研究放进同一条论文流，保留每个领域自己的判断。",
  },
  recent: {
    eyebrow: "PUBLISHED IN THE LAST 7 DAYS",
    title: "过去 7 天，哪些研究刚刚出现？",
    description: "严格按论文发表日期计算，而不是进入数据库的时间。不会把旧论文伪装成新发表。",
  },
  favorites: {
    eyebrow: "YOUR RESEARCH SHELF",
    title: "把值得回来的研究，放在一个地方",
    description: "收藏以稳定论文 ID 保存在当前浏览器中，跨三个研究频道共用。",
  },
};

export default function PaperExplorer({ mode }: { mode: ExplorerMode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [updates, setUpdates] = useState<Updates | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [demo, setDemo] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [mobileFilters, setMobileFilters] = useState(false);
  const filterTriggerRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.allSettled([
      loadPapers(controller.signal),
      loadMeta(controller.signal),
      loadUpdates(controller.signal),
    ]).then(([papersResult, metaResult, updatesResult]) => {
      if (controller.signal.aborted) return;
      if (papersResult.status === "rejected") {
        setError(papersResult.reason instanceof Error ? papersResult.reason : new Error(String(papersResult.reason)));
      } else {
        setPapers(papersResult.value.papers);
        setDemo(papersResult.value.demo);
      }
      if (metaResult.status === "fulfilled") setMeta(metaResult.value);
      if (updatesResult.status === "fulfilled") setUpdates(updatesResult.value);
      setLoading(false);
    });
    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    const syncFavorites = () => setFavorites(readFavorites());
    const syncRead = () => setReadIds(readReadIds());
    syncFavorites();
    syncRead();
    window.addEventListener(storageEvents.favorites, syncFavorites);
    window.addEventListener(storageEvents.read, syncRead);
    window.addEventListener("storage", syncFavorites);
    window.addEventListener("storage", syncRead);
    return () => {
      window.removeEventListener(storageEvents.favorites, syncFavorites);
      window.removeEventListener(storageEvents.read, syncRead);
      window.removeEventListener("storage", syncFavorites);
      window.removeEventListener("storage", syncRead);
    };
  }, []);

  useEffect(() => {
    if (!mobileFilters) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeMobileFilters();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [mobileFilters]);

  const domainValue = searchParams.get("domain");
  const activeDomain: ChannelId | null = isChannel(domainValue) ? domainValue : null;
  const query = searchParams.get("q") || "";
  const year = searchParams.get("year") || "";
  const journal = searchParams.get("journal") || "";
  const topic = searchParams.get("topic") || "";
  const aiType = searchParams.get("aitype") || "";
  const requestedMin = Number(searchParams.get("minscore") || 3);
  const minScore = requestedMin === 4 || requestedMin === 5 ? requestedMin : 3;
  const requestedSort = searchParams.get("sort");
  const sort = requestedSort === "score" || requestedSort === "cited" ? requestedSort : "recent";

  const updateParam = useCallback((key: string, value: string | number | null) => {
    const next = new URLSearchParams(searchParams.toString());
    const isDefault = (key === "minscore" && value === 3) || (key === "sort" && value === "recent");
    if (value === null || value === "" || isDefault) next.delete(key);
    else next.set(key, String(value));
    const queryString = next.toString();
    router.replace(queryString ? `${pathname}?${queryString}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  const modePapers = useMemo(() => {
    if (mode === "recent") return papers.filter((paper) => isPublishedInLastSevenDays(paper));
    if (mode === "favorites") return papers.filter((paper) => favorites.has(paper.id));
    return papers;
  }, [favorites, mode, papers]);

  const channelCounts = useMemo(() => {
    const counts: Partial<Record<ChannelId | "all", number>> = { all: modePapers.length };
    for (const channel of CHANNEL_ORDER) counts[channel] = modePapers.filter((paper) => paper.channels.includes(channel)).length;
    return counts;
  }, [modePapers]);

  const scopedPapers = useMemo(
    () => activeDomain ? modePapers.filter((paper) => paper.channels.includes(activeDomain)) : modePapers,
    [activeDomain, modePapers],
  );

  const facets: Facets = useMemo(() => ({
    years: countValues(scopedPapers.map((paper) => paper.year)),
    journals: countValues(scopedPapers.map((paper) => paper.journal)),
    topics: countValues(scopedPapers.flatMap((paper) => allTopicTags(paper, activeDomain))),
    aiTypes: countValues(scopedPapers.flatMap((paper) => paper.ai_type_tags)),
  }), [activeDomain, scopedPapers]);

  const filtered = useMemo(() => {
    const result = scopedPapers.filter((paper) => {
      if (year && String(paper.year) !== year) return false;
      if (journal && paper.journal !== journal) return false;
      if (topic && !allTopicTags(paper, activeDomain).includes(topic)) return false;
      if (aiType && !paper.ai_type_tags.includes(aiType)) return false;
      if (paperScore(paper, activeDomain) < minScore) return false;
      return matchesSearch(paper, query);
    });
    result.sort((a, b) => {
      if (sort === "score") return paperScore(b, activeDomain) - paperScore(a, activeDomain) || compareRecent(a, b);
      if (sort === "cited") return b.cited_by - a.cited_by || compareRecent(a, b);
      return compareRecent(a, b);
    });
    return result;
  }, [activeDomain, aiType, journal, minScore, query, scopedPapers, sort, topic, year]);

  useEffect(() => setVisibleCount(PAGE_SIZE), [activeDomain, aiType, journal, minScore, mode, query, sort, topic, year]);

  const activeFilterCount = [activeDomain, query, year, journal, topic, aiType].filter(Boolean).length + (minScore > 3 ? 1 : 0) + (sort !== "recent" ? 1 : 0);
  const filterValues: FilterValues = { year, journal, topic, aiType, minScore };
  const visiblePapers = filtered.slice(0, visibleCount);
  const staleChannels = Array.isArray(updates?.stale_channels) ? updates!.stale_channels! : [];
  const pendingChannels = Array.isArray(updates?.pending_channels) ? updates!.pending_channels! : [];
  const failures = Array.isArray(updates?.failures) ? updates!.failures! : [];
  const hero = heroCopy[mode];

  function changeFilter(key: keyof FilterValues, value: string | number) {
    const queryKey = key === "aiType" ? "aitype" : key === "minScore" ? "minscore" : key;
    updateParam(queryKey, value);
  }

  function clearFilters() {
    router.replace(pathname, { scroll: false });
  }

  function handleToggleFavorite(id: string) {
    toggleFavorite(id);
    setFavorites(readFavorites());
  }

  function closeMobileFilters() {
    setMobileFilters(false);
    window.setTimeout(() => filterTriggerRef.current?.focus(), 0);
  }

  if (loading) return <ExplorerSkeleton />;
  if (error) return <ExplorerError error={error} onRetry={() => setReloadKey((key) => key + 1)} />;

  return (
    <main id="main-content">
      <section className="hero">
        <div className="hero__copy">
          <span className="eyebrow">{hero.eyebrow}</span>
          <h1>{hero.title}</h1>
          <p>{hero.description}</p>
        </div>
        <div className="hero__spectrum"><Spectrum /><span>ORGANIZATION</span><span>INTERACTION</span><span>MENTAL HEALTH</span></div>
      </section>

      {demo ? <div className="notice notice--demo"><b>开发预览</b><span>尚未读到发布数据，当前展示小型示意样本。</span></div> : null}
      {staleChannels.length || pendingChannels.length || failures.length ? (
        <div className="notice notice--warning" role="status"><b>数据更新提示</b><span>{pendingChannels.length ? `${pendingChannels.map((channel) => isChannel(channel) ? CHANNELS[channel].label : channel).join("、")} 频道正在回填。` : ""}{staleChannels.length ? ` ${staleChannels.join("、")} 频道沿用上一版成功快照。` : ""}{failures.length ? ` 本轮有 ${failures.length} 个来源失败。` : ""}</span></div>
      ) : null}

      <div className="explorer-layout">
        <aside className="filters-desktop" aria-label="论文筛选">
          <FilterPanel idPrefix="desktop" activeDomain={activeDomain} values={filterValues} facets={facets} resultCount={filtered.length} totalCount={modePapers.length} activeCount={activeFilterCount} generatedAt={meta?.generated_at} afterSummary={<div className="filter-search"><PaperSearch query={query} onChange={(value) => updateParam("q", value)} /></div>} onChange={changeFilter} onClear={clearFilters} />
        </aside>

        <section className="results" aria-labelledby="result-heading">
          <ChannelTabs active={activeDomain} onChange={(channel) => updateParam("domain", channel)} counts={channelCounts} />

          <div className="result-tools">
            <PaperSearch className="search-field--results" query={query} onChange={(value) => updateParam("q", value)} />
            <button ref={filterTriggerRef} type="button" className="mobile-filter-trigger" onClick={() => setMobileFilters(true)} aria-haspopup="dialog" aria-expanded={mobileFilters}>
              <FilterIcon />筛选{activeFilterCount ? <span>{activeFilterCount}</span> : null}
            </button>
          </div>

          <div className="result-heading">
            <div><span className="eyebrow">PAPER STREAM</span><h2 id="result-heading">{activeDomain ? CHANNELS[activeDomain].label : mode === "favorites" ? "我的收藏" : mode === "recent" ? "最近发表" : "统一论文流"}</h2></div>
            <label className="sort-field">
              <span>排序</span>
              <select value={sort} onChange={(event) => updateParam("sort", event.target.value)}>
                <option value="recent">最新发表</option>
                <option value="score">相关度</option>
                <option value="cited">引用数</option>
              </select>
            </label>
          </div>

          {!filtered.length ? (
            <EmptyState mode={mode} activeDomain={activeDomain} pending={Boolean(activeDomain && pendingChannels.includes(activeDomain))} hasFilters={activeFilterCount > 0} onClear={clearFilters} />
          ) : (
            <>
              <div className="paper-list">
                {visiblePapers.map((paper) => <PaperCard key={paper.id} paper={paper} activeDomain={activeDomain} favorite={favorites.has(paper.id)} read={readIds.has(paper.id)} onToggleFavorite={handleToggleFavorite} />)}
              </div>
              {visibleCount < filtered.length ? (
                <button type="button" className="load-more" onClick={() => setVisibleCount((count) => count + PAGE_SIZE)}>
                  继续加载 <span>{Math.min(PAGE_SIZE, filtered.length - visibleCount)} 篇</span>
                </button>
              ) : <p className="result-end">已到达当前结果末尾 · {filtered.length} 篇</p>}
            </>
          )}
        </section>
      </div>

      {mobileFilters ? (
        <div className="filter-drawer" role="dialog" aria-modal="true" aria-labelledby="mobile-filter-title">
          <button type="button" className="filter-drawer__backdrop" onClick={closeMobileFilters} tabIndex={-1} aria-label="关闭筛选" />
          <div className="filter-drawer__panel">
            <div className="filter-drawer__header"><h2 id="mobile-filter-title">筛选论文</h2><button ref={closeButtonRef} type="button" onClick={closeMobileFilters} aria-label="关闭筛选"><CloseIcon /></button></div>
            <FilterPanel idPrefix="mobile" activeDomain={activeDomain} values={filterValues} facets={facets} resultCount={filtered.length} totalCount={modePapers.length} activeCount={activeFilterCount} generatedAt={meta?.generated_at} onChange={changeFilter} onClear={clearFilters} />
            <button type="button" className="filter-drawer__done" onClick={closeMobileFilters}>查看 {filtered.length} 篇论文</button>
          </div>
        </div>
      ) : null}
    </main>
  );
}

function PaperSearch({ query, onChange, className = "" }: { query: string; onChange: (value: string) => void; className?: string }) {
  return (
    <label className={`search-field ${className}`.trim()}>
      <SearchIcon />
      <span className="sr-only">搜索论文</span>
      <input value={query} onChange={(event) => onChange(event.target.value)} placeholder="搜索标题、摘要、作者或标签" type="search" />
      {query ? <button type="button" onClick={() => onChange("")} aria-label="清空搜索"><CloseIcon /></button> : null}
    </label>
  );
}

function ExplorerSkeleton() {
  return <main id="main-content" className="loading-state" aria-busy="true"><div className="skeleton skeleton--hero" /><div className="skeleton-grid"><div className="skeleton skeleton--aside" /><div className="skeleton-results"><div className="skeleton skeleton--tabs" />{[1, 2, 3].map((item) => <div className="skeleton skeleton--card" key={item} />)}</div></div><span className="sr-only">正在加载论文数据</span></main>;
}

function ExplorerError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const path = error instanceof DataLoadError ? error.path : "/data/papers.json";
  return <main id="main-content" className="state-page"><span className="state-page__code">DATA / UNAVAILABLE</span><h1>论文索引暂时无法读取</h1><p>加载 <code>{path}</code> 失败。请确认发布数据已生成，或稍后重试。</p><pre>{error.message}</pre><button type="button" onClick={onRetry}><RefreshIcon />重新加载</button></main>;
}

function EmptyState({ mode, activeDomain, pending, hasFilters, onClear }: { mode: ExplorerMode; activeDomain: ChannelId | null; pending: boolean; hasFilters: boolean; onClear: () => void }) {
  const copy = activeDomain && pending
    ? { title: `${CHANNELS[activeDomain].label}频道正在回填`, body: "频道入口已保留，首批论文通过范围与质量核验后会出现在这里。" }
    : mode === "favorites" && !hasFilters
    ? { title: "还没有收藏的论文", body: "在论文卡上点击书签图标，它们会出现在这里。" }
    : mode === "recent" && !hasFilters
      ? { title: "过去 7 天没有新发表论文", body: "这个页面只按真实发表日期统计，可前往全部论文继续浏览。" }
      : { title: "没有符合这组条件的论文", body: "试试减少一个筛选条件，或者换一个搜索词。" };
  return <div className="empty-state"><span className="empty-state__rings" aria-hidden="true"><i /><i /><i /></span><h3>{copy.title}</h3><p>{copy.body}</p>{hasFilters && !pending ? <button type="button" onClick={onClear}>清空全部筛选</button> : null}</div>;
}
