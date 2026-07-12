import { Button } from "@noahwright/design";

// No per-video frame rate probing (approximate step, not exact) - close
// enough for scrubbing to the right spot, which is all this is for.
const FRAME_SECONDS = 1 / 30;
const SECOND = 1;
const MINUTE = 60;

interface TransportBarProps {
  playing: boolean;
  onTogglePlay: () => void;
  onStep: (deltaSeconds: number) => void;
}

export default function TransportBar({ playing, onTogglePlay, onStep }: TransportBarProps) {
  return (
    <div style={{ display: "flex", gap: "0.4rem", alignItems: "center", justifyContent: "center" }}>
      <span title="Back 1 minute">
        <Button variant="outline" size="small" onClick={() => onStep(-MINUTE)}>
          &lt;&lt;&lt;
        </Button>
      </span>
      <span title="Back 1 second">
        <Button variant="outline" size="small" onClick={() => onStep(-SECOND)}>
          &lt;&lt;
        </Button>
      </span>
      <span title="Back 1 frame">
        <Button variant="outline" size="small" onClick={() => onStep(-FRAME_SECONDS)}>
          &lt;
        </Button>
      </span>

      <span title={playing ? "Pause" : "Play"}>
        <Button onClick={onTogglePlay}>{playing ? "⏸" : "▶"}</Button>
      </span>

      <span title="Forward 1 frame">
        <Button variant="outline" size="small" onClick={() => onStep(FRAME_SECONDS)}>
          &gt;
        </Button>
      </span>
      <span title="Forward 1 second">
        <Button variant="outline" size="small" onClick={() => onStep(SECOND)}>
          &gt;&gt;
        </Button>
      </span>
      <span title="Forward 1 minute">
        <Button variant="outline" size="small" onClick={() => onStep(MINUTE)}>
          &gt;&gt;&gt;
        </Button>
      </span>
    </div>
  );
}
