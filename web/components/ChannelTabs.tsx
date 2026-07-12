"use client";

import { CHANNELS, type ChannelId } from "@/lib/types";

export default function ChannelTabs({ active, onChange, counts }: {
  active: ChannelId | null;
  onChange: (channel: ChannelId | null) => void;
  counts: Partial<Record<ChannelId | "all", number>>;
}) {
  return (
    <div className="channel-tabs" role="group" aria-label="研究频道">
      <button type="button" className={!active ? "is-active" : ""} onClick={() => onChange(null)} aria-pressed={!active}>
        <span className="channel-tabs__signal signal-all" aria-hidden="true" />
        <span><b>全部领域</b><small>{counts.all ?? 0} 篇</small></span>
      </button>
      {(Object.keys(CHANNELS) as ChannelId[]).map((channel) => (
        <button type="button" key={channel} className={active === channel ? `is-active channel-${channel}` : `channel-${channel}`} onClick={() => onChange(channel)} aria-pressed={active === channel}>
          <span className={`channel-tabs__signal signal-${channel}`} aria-hidden="true" />
          <span><b>{CHANNELS[channel].label}</b><small>{counts[channel] ?? 0} 篇</small></span>
        </button>
      ))}
    </div>
  );
}
