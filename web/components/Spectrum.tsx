import type { ChannelId } from "@/lib/types";

export function Spectrum({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`spectrum ${compact ? "spectrum--compact" : ""}`} aria-hidden="true">
      <i className="spectrum__ob" />
      <i className="spectrum__ur" />
      <i className="spectrum__mh" />
    </span>
  );
}

export function DomainTrack({ channels }: { channels: ChannelId[] }) {
  return (
    <span className="domain-track" aria-hidden="true">
      {channels.map((channel) => <i className={`domain-track__${channel}`} key={channel} />)}
    </span>
  );
}
