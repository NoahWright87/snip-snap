import { useCallback, useRef, useState } from "react";
import { Segment } from "../api";

interface TimelineProps {
  duration: number;
  currentTime: number;
  segments: Segment[];
  selectedSegmentId: string | null;
  onSelectSegment: (segmentId: string) => void;
  onSeek: (time: number) => void;
  onSnip: () => void;
  onRemoveBoundary: (time: number) => void;
}

const KEEP_COLOR = "var(--secondary-background, #dbe2ea)";
const CUT_COLOR = "var(--danger, #dc2626)";
const HANDLE_SIZE = 16;
const TRACK_HEIGHT = 40;
const BOUNDARY_HIT_WIDTH = 14;

export default function Timeline({
  duration,
  currentTime,
  segments,
  selectedSegmentId,
  onSelectSegment,
  onSeek,
  onSnip,
  onRemoveBoundary,
}: TimelineProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const [hoveredBoundary, setHoveredBoundary] = useState<string | null>(null);
  const [armedBoundary, setArmedBoundary] = useState<string | null>(null);

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
  const boundaries = segments.slice(0, -1);

  return (
    <div style={{ position: "relative", paddingTop: HANDLE_SIZE + 4, paddingBottom: 36 }}>
      <div
        ref={trackRef}
        style={{
          position: "relative",
          height: TRACK_HEIGHT,
          borderRadius: 6,
          background: KEEP_COLOR,
          overflow: "hidden",
        }}
      >
        {segments.map((seg) => (
          <div
            key={seg.id}
            onClick={() => {
              setArmedBoundary(null);
              onSelectSegment(seg.id);
            }}
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
      </div>

      {/* Split boundaries live outside the (overflow: hidden) track so their
          "click again to remove" tooltip isn't clipped. Needed even when
          adjacent segments share a color, since that's the only visual cue
          a split happened there. */}
      {boundaries.map((seg) => {
        const isHot = hoveredBoundary === seg.id || armedBoundary === seg.id;
        return (
          <div
            key={`boundary-${seg.id}`}
            onMouseEnter={() => setHoveredBoundary(seg.id)}
            onMouseLeave={() => setHoveredBoundary((h) => (h === seg.id ? null : h))}
            onClick={(e) => {
              e.stopPropagation();
              if (armedBoundary === seg.id) {
                onRemoveBoundary(seg.end_time);
                setArmedBoundary(null);
              } else {
                setArmedBoundary(seg.id);
              }
            }}
            style={{
              position: "absolute",
              left: pct(seg.end_time),
              top: HANDLE_SIZE + 4,
              height: TRACK_HEIGHT,
              width: BOUNDARY_HIT_WIDTH,
              transform: "translateX(-50%)",
              cursor: "pointer",
              zIndex: 2,
            }}
          >
            <div
              style={{
                position: "absolute",
                left: "50%",
                top: 0,
                bottom: 0,
                width: 0,
                borderLeft: `2px ${isHot ? "solid" : "dashed"} ${isHot ? "#eab308" : "rgba(0,0,0,0.4)"}`,
                boxShadow: isHot ? "0 0 0 3px rgba(234,179,8,0.35)" : "none",
              }}
            />
            {armedBoundary === seg.id && (
              <div
                style={{
                  position: "absolute",
                  bottom: "100%",
                  left: "50%",
                  transform: "translateX(-50%)",
                  marginBottom: 4,
                  padding: "0.25rem 0.5rem",
                  background: "#111",
                  color: "#fff",
                  fontSize: "0.75rem",
                  borderRadius: 4,
                  whiteSpace: "nowrap",
                }}
              >
                click again to remove
              </div>
            )}
          </div>
        );
      })}

      {/* Playhead: line through the track plus a draggable handle above it. */}
      <div
        style={{
          position: "absolute",
          left: pct(currentTime),
          top: HANDLE_SIZE + 4,
          height: TRACK_HEIGHT,
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
          top: HANDLE_SIZE + 4 + TRACK_HEIGHT + 4,
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
