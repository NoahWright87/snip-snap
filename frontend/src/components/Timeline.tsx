import { useRef } from "react";
import { Segment } from "../api";

interface TimelineProps {
  duration: number;
  currentTime: number;
  segments: Segment[];
  pendingStart: number | null;
  pendingEnd: number | null;
  onSeek: (time: number) => void;
}

const DECISION_COLOR: Record<Segment["decision"], string> = {
  keep: "var(--confirm, #16a34a)",
  cut: "var(--danger, #dc2626)",
};

export default function Timeline({
  duration,
  currentTime,
  segments,
  pendingStart,
  pendingEnd,
  onSeek,
}: TimelineProps) {
  const trackRef = useRef<HTMLDivElement>(null);

  function handleClick(e: React.MouseEvent<HTMLDivElement>) {
    const track = trackRef.current;
    if (!track || duration <= 0) return;
    const rect = track.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    onSeek(ratio * duration);
  }

  const pct = (t: number) => (duration > 0 ? `${(t / duration) * 100}%` : "0%");

  return (
    <div
      ref={trackRef}
      onClick={handleClick}
      style={{
        position: "relative",
        height: 40,
        borderRadius: 6,
        background: "var(--secondary-background, #e5e7eb)",
        cursor: "pointer",
        overflow: "hidden",
      }}
    >
      {segments.map((seg) => (
        <div
          key={seg.id}
          title={`${seg.decision}${seg.tag ? ` (${seg.tag})` : ""}`}
          style={{
            position: "absolute",
            left: pct(seg.start_time),
            width: pct(seg.end_time - seg.start_time),
            top: 0,
            bottom: 0,
            background: DECISION_COLOR[seg.decision],
            opacity: 0.75,
          }}
        />
      ))}

      {pendingStart != null && pendingEnd != null && pendingEnd > pendingStart && (
        <div
          style={{
            position: "absolute",
            left: pct(pendingStart),
            width: pct(pendingEnd - pendingStart),
            top: 0,
            bottom: 0,
            background: "var(--primary, #2563eb)",
            opacity: 0.4,
            border: "2px dashed var(--primary, #2563eb)",
            boxSizing: "border-box",
          }}
        />
      )}

      <div
        style={{
          position: "absolute",
          left: pct(currentTime),
          top: 0,
          bottom: 0,
          width: 2,
          background: "var(--foreground, #111)",
        }}
      />
    </div>
  );
}
