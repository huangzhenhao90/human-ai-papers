import type { ChannelDefinition, ChannelId } from "@/lib/types";

export function Spectrum({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`spectrum ${compact ? "spectrum--compact" : ""}`} aria-hidden="true">
      <i className="spectrum__ob" />
      <i className="spectrum__ur" />
      <i className="spectrum__mh" />
    </span>
  );
}

export function DomainTrack({ channels, definitions }: { channels: ChannelId[]; definitions: ChannelDefinition[] }) {
  const colors = new Map(definitions.map((channel) => [channel.id, channel.color]));
  return (
    <span className="domain-track" aria-hidden="true">
      {channels.map((channel) => <i style={{ background: colors.get(channel) || "#6d7a7b" }} key={channel} />)}
    </span>
  );
}
