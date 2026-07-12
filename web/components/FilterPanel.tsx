"use client";

import { CHANNELS, type ChannelId } from "@/lib/types";

export type FilterValues = {
  year: string;
  journal: string;
  topic: string;
  aiType: string;
  minScore: number;
};

export type Facets = {
  years: Array<[string, number]>;
  journals: Array<[string, number]>;
  topics: Array<[string, number]>;
  aiTypes: Array<[string, number]>;
};

export default function FilterPanel({
  idPrefix,
  activeDomain,
  values,
  facets,
  resultCount,
  totalCount,
  activeCount,
  generatedAt,
  afterSummary,
  onChange,
  onClear,
}: {
  idPrefix: string;
  activeDomain: ChannelId | null;
  values: FilterValues;
  facets: Facets;
  resultCount: number;
  totalCount: number;
  activeCount: number;
  generatedAt?: string;
  afterSummary?: React.ReactNode;
  onChange: (key: keyof FilterValues, value: string | number) => void;
  onClear: () => void;
}) {
  const topTopics = includeActive(facets.topics, values.topic, 12);
  const topAiTypes = includeActive(facets.aiTypes, values.aiType, 10);
  const domainLabel = activeDomain ? CHANNELS[activeDomain].label : "全部领域";
  return (
    <div className="filter-panel">
      <div className="filter-summary">
        <span className={`filter-summary__signal ${activeDomain ? `signal-${activeDomain}` : "signal-all"}`} aria-hidden="true" />
        <span className="filter-summary__eyebrow">{domainLabel}</span>
        <strong>{resultCount.toLocaleString("zh-CN")}</strong>
        <span className="filter-summary__caption">当前结果 · 共 {totalCount.toLocaleString("zh-CN")} 篇</span>
      </div>

      {afterSummary}

      <FilterGroup title="发表年份" htmlFor={`${idPrefix}-year`}>
        <select id={`${idPrefix}-year`} value={values.year} onChange={(event) => onChange("year", event.target.value)}>
          <option value="">全部年份</option>
          {[...facets.years].sort((a, b) => Number(b[0]) - Number(a[0])).map(([value, count]) => (
            <option value={value} key={value}>{value}（{count}）</option>
          ))}
        </select>
      </FilterGroup>

      <FilterGroup title="期刊 / 会议" htmlFor={`${idPrefix}-journal`}>
        <select id={`${idPrefix}-journal`} value={values.journal} onChange={(event) => onChange("journal", event.target.value)}>
          <option value="">全部来源</option>
          {facets.journals.map(([value, count]) => (
            <option value={value} key={value}>{value}（{count}）</option>
          ))}
        </select>
      </FilterGroup>

      <FilterGroup title="主题">
        <ChipList entries={topTopics} active={values.topic} onChange={(value) => onChange("topic", value)} />
      </FilterGroup>

      <FilterGroup title="AI 类型">
        <ChipList entries={topAiTypes} active={values.aiType} onChange={(value) => onChange("aiType", value)} />
      </FilterGroup>

      <FilterGroup title="最低相关度">
        <div className="score-picker" role="group" aria-label="AI 与领域最低分">
          {[3, 4, 5].map((score) => (
            <button key={score} type="button" className={values.minScore === score ? "is-active" : ""} onClick={() => onChange("minScore", score)} aria-pressed={values.minScore === score}>
              ≥ {score}
            </button>
          ))}
        </div>
        <p className="filter-help">AI 与当前领域两项分数均需达标。</p>
      </FilterGroup>

      {activeCount > 0 ? (
        <button type="button" className="clear-filters" onClick={onClear}>
          清空全部筛选 <span>{activeCount}</span>
        </button>
      ) : null}

      {generatedAt ? <p className="data-stamp">数据更新：{formatGeneratedAt(generatedAt)}</p> : null}
    </div>
  );
}

function FilterGroup({ title, htmlFor, children }: { title: string; htmlFor?: string; children: React.ReactNode }) {
  const heading = htmlFor ? <label htmlFor={htmlFor}>{title}</label> : <span>{title}</span>;
  return <section className="filter-group"><h3>{heading}</h3>{children}</section>;
}

function ChipList({ entries, active, onChange }: { entries: Array<[string, number]>; active: string; onChange: (value: string) => void }) {
  if (!entries.length) return <span className="filter-none">当前无可用选项</span>;
  return (
    <div className="filter-chips">
      {entries.map(([value, count]) => (
        <button type="button" key={value} className={active === value ? "is-active" : ""} onClick={() => onChange(active === value ? "" : value)} aria-pressed={active === value}>
          <span>{value}</span><small>{count}</small>
        </button>
      ))}
    </div>
  );
}

function includeActive(entries: Array<[string, number]>, active: string, limit: number) {
  const result = entries.slice(0, limit);
  if (active && !result.some(([value]) => value === active)) {
    const found = entries.find(([value]) => value === active);
    if (found) result.push(found);
  }
  return result;
}

function formatGeneratedAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}
