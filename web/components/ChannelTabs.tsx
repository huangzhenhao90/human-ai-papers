"use client";

import type { CSSProperties } from "react";
import type { ChannelDefinition, ChannelId } from "@/lib/types";

export default function ChannelTabs({ active, onChange, counts, channels }: {
  active: ChannelId | null;
  onChange: (channel: ChannelId | null) => void;
  counts: Partial<Record<ChannelId | "all", number>>;
  channels: ChannelDefinition[];
}) {
  return (
    <div className="channel-tabs" role="group" aria-label="研究频道">
      <button type="button" className={!active ? "is-active" : ""} onClick={() => onChange(null)} aria-pressed={!active}>
        <span className="channel-tabs__signal signal-all" aria-hidden="true" />
        <span><b>全部领域</b><small>{counts.all ?? 0} 篇</small></span>
      </button>
      {channels.map((channel) => (
        <button type="button" key={channel.id} className={active === channel.id ? "is-active channel-tab" : "channel-tab"} style={{ "--channel-color": channel.color, "--channel-soft": channel.soft_color } as CSSProperties} onClick={() => onChange(channel.id)} aria-pressed={active === channel.id}>
          <span className="channel-tabs__signal" style={{ background: channel.color }} aria-hidden="true" />
          <span><b>{channel.label}</b><small>{counts[channel.id] ?? 0} 篇</small></span>
        </button>
      ))}
    </div>
  );
}
