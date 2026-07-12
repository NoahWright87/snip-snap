import { useCallback, useRef } from "react";
import { Segment } from "../api";

interface TimelineProps {
  duration: number;
  currentTime: number;
  segments: Segment[];
  selectedSegmentId: number | null;
  onSelectSegment: (segmentId: number) => void;
  onSeek: (time: number) => void;
  onSnip: () => void;
}

const KEEP_COLOR = "var(--secondary-background, #dbe2ea)";
const CUT_COLOR = "var(--danger, #dc2626)";
const HANDLE_SIZE = 16;

export default function Timeline({
  duration,
  currentTime,
  segments,
  selectedSegmentId,
  onSelectSegment,
  onSeek,
  onSnip,
}: TimelineProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const timeFromClientX = useCallback(
    (clientX: number): number => {
      const track = trackRef.current;
      if (!track || duration <= 0) return 0;
      const rect = track.getBoundingClientRect();
      const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
      return ratio * duration;
    },
    [duration],
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      dragging.current = true;
      onSeek(timeFromClientX(e.clientX));

      function handleMove(ev: PointerEvent) {
        if (!dragging.current) return;
        onSeek(timeFromClientX(ev.clientX));
      }
      function handleUp() {
        dragging.current = false;
        window.removeEventListener("pointermove", handleMove);
        window.removeEventListener("pointerup", handleUp);
      }
      window.addEventListener("pointermove", handleMove);
      window.addEventListener("pointerup", handleUp);
    },
    [onSeek, timeFromClientX],
  );

  const pct = (t: number) => (duration > 0 ? `${(t / duration) * 100}%` : "0%");

  return (
    <div style={{ position: "relative", paddingTop: HANDLE_SIZE + 4, paddingBottom: 36 }}>
      <div
        ref={trackRef}
        style={{
          position: "relative",
          height: 40,
          borderRadius: 6,
          background: KEEP_COLOR,
          overflow: "hidden",
        }}
      >
        {segments.map((seg) => (
          <div
            key={seg.id}
            onClick={() => onSelectSegment(seg.id)}
            title={seg.tags.length ? seg.tags.join(", ") : undefined}
            style={{
              position: "absolute",
              left: pct(seg.start_time),
              width: pct(seg.end_time - seg.start_time),
              top: 0,
              bottom: 0,
              background: seg.decision === "cut" ? CUT_COLOR : KEEP_COLOR,
              opacity: seg.decision === "cut" ? 0.85 : 1,
              cursor: "pointer",
              boxSizing: "border-box",
              border: seg.id === selectedSegmentId ? "2px solid var(--primary, #2563eb)" : "none",
            }}
          />
        ))}

        {/* Dashed line at each split boundary - needed even when adjacent
            segments share the same color, since that's the only visual cue
            a split happened there. */}
        {segments.slice(0, -1).map((seg) => (
          <div
            key={`boundary-${seg.id}`}
            style={{
              position: "absolute",
              left: pct(seg.end_time),
              top: 0,
              bottom: 0,
              width: 0,
              borderLeft: "2px dashed rgba(0,0,0,0.4)",
              pointerEvents: "none",
            }}
          />
        ))}
      </div>

      {/* Playhead: line through the track plus a draggable handle above it. */}
      <div
        style={{
          position: "absolute",
          left: pct(currentTime),
          top: 0,
          bottom: 0,
          width: 2,
          background: "var(--foreground, #111)",
          pointerEvents: "none",
        }}
      />
      <div
        onPointerDown={handlePointerDown}
        role="slider"
        aria-label="Playhead"
        aria-valuemin={0}
        aria-valuemax={duration}
        aria-valuenow={currentTime}
        style={{
          position: "absolute",
          left: pct(currentTime),
          top: 0,
          width: HANDLE_SIZE,
          height: HANDLE_SIZE,
          transform: "translateX(-50%)",
          borderRadius: 4,
          background: "var(--foreground, #111)",
          cursor: "grab",
          touchAction: "none",
        }}
      />

      <button
        type="button"
        onClick={onSnip}
        title="Snip here"
        aria-label="Snip at current position"
        style={{
          position: "absolute",
          left: pct(currentTime),
          top: HANDLE_SIZE + 4 + 40 + 4,
          transform: "translateX(-50%)",
          width: 28,
          height: 28,
          borderRadius: "50%",
          border: "1px solid #ccc",
          background: "#fff",
          cursor: "pointer",
          fontSize: "0.9rem",
          lineHeight: 1,
          padding: 0,
        }}
      >
        ✂️
      </button>
    </div>
  );
}
