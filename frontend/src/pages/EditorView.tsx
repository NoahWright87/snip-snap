import { Button, Card, Pill, Text } from "@noahwright/design";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, Segment, Video, videoStreamUrl } from "../api";
import Timeline from "../components/Timeline";

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(1);
  return `${mins}:${secs.padStart(4, "0")}`;
}

export default function EditorView() {
  const { id } = useParams();
  const videoId = Number(id);
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);

  const [video, setVideo] = useState<Video | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [existingTags, setExistingTags] = useState<string[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [pendingStart, setPendingStart] = useState<number | null>(null);
  const [pendingEnd, setPendingEnd] = useState<number | null>(null);
  const [tag, setTag] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [exportResult, setExportResult] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [v, segs, tags] = await Promise.all([
        api.getVideo(videoId),
        api.listSegments(videoId),
        api.listTags(),
      ]);
      setVideo(v);
      setSegments(segs);
      setExistingTags(tags);
      setError(null);
    } catch (err) {
      setError(String(err));
    }
  }, [videoId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const setIn = useCallback(() => setPendingStart(currentTime), [currentTime]);
  const setOut = useCallback(() => setPendingEnd(currentTime), [currentTime]);

  const saveSegment = useCallback(
    async (decision: "keep" | "cut", tagOverride?: string) => {
      if (pendingStart == null || pendingEnd == null) {
        setError("Mark an in and out point first.");
        return;
      }
      const [start, end] = [pendingStart, pendingEnd].sort((a, b) => a - b);
      try {
        await api.createSegment(videoId, {
          start_time: start,
          end_time: end,
          decision,
          tag: (tagOverride ?? tag).trim() || null,
        });
        setPendingStart(null);
        setPendingEnd(null);
        setTag("");
        await refresh();
      } catch (err) {
        setError(String(err));
      }
    },
    [pendingStart, pendingEnd, tag, videoId, refresh],
  );

  const deleteSegment = useCallback(
    async (segmentId: number) => {
      try {
        await api.deleteSegment(segmentId);
        await refresh();
      } catch (err) {
        setError(String(err));
      }
    },
    [refresh],
  );

  // Keyboard shortcuts for fast scrubbing: I/O mark in/out, K keeps, X cuts.
  // Ignored while typing in a text field.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;
      if (e.key === "i" || e.key === "I") setIn();
      else if (e.key === "o" || e.key === "O") setOut();
      else if (e.key === "k" || e.key === "K") saveSegment("keep");
      else if (e.key === "x" || e.key === "X") saveSegment("cut");
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setIn, setOut, saveSegment]);

  async function handleExport() {
    setExportResult(null);
    try {
      const result = await api.exportVideo(videoId);
      setExportResult(result.output_path);
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  if (!video) {
    return <Text>{error ?? "Loading…"}</Text>;
  }

  const duration = video.duration ?? videoRef.current?.duration ?? 0;

  return (
    <div>
      <Button variant="text" onClick={() => navigate("/")}>
        ← Back to library
      </Button>

      <h2 style={{ margin: "0.5rem 0" }}>{video.filename}</h2>

      {error && <Text tone="error">{error}</Text>}

      <video
        ref={videoRef}
        src={videoStreamUrl(video.id)}
        controls
        style={{ width: "100%", maxHeight: 480, background: "#000", borderRadius: 8 }}
        onTimeUpdate={() => setCurrentTime(videoRef.current?.currentTime ?? 0)}
        onLoadedMetadata={() => setCurrentTime(videoRef.current?.currentTime ?? 0)}
      />

      <div style={{ margin: "0.75rem 0" }}>
        <Timeline
          duration={duration}
          currentTime={currentTime}
          segments={segments}
          pendingStart={pendingStart}
          pendingEnd={pendingEnd}
          onSeek={(t) => {
            if (videoRef.current) videoRef.current.currentTime = t;
          }}
        />
      </div>

      <Card title="Mark a segment">
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
          <Button variant="outline" onClick={setIn}>
            Set in ({pendingStart != null ? formatTime(pendingStart) : "—"}) [I]
          </Button>
          <Button variant="outline" onClick={setOut}>
            Set out ({pendingEnd != null ? formatTime(pendingEnd) : "—"}) [O]
          </Button>

          {/* Plain input + datalist for tag autocomplete: the design system's
              Select only wraps a native fixed-option <select>, no free-text
              combobox yet (tracked in snip-snap#1 / design#15). */}
          <input
            list="tag-suggestions"
            placeholder="tag (optional)"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            style={{ padding: "0.4rem 0.6rem", borderRadius: 6, border: "1px solid #ccc" }}
          />
          <datalist id="tag-suggestions">
            {existingTags.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>

          <Button color="confirm" onClick={() => saveSegment("keep")}>
            Save as keep [K]
          </Button>
          <Button color="danger" onClick={() => saveSegment("cut")}>
            Save as cut [X]
          </Button>
          <Button variant="ghost" onClick={() => saveSegment("cut", "structural_intro")}>
            Mark as intro
          </Button>
          <Button variant="ghost" onClick={() => saveSegment("cut", "structural_outro")}>
            Mark as outro
          </Button>
        </div>
      </Card>

      <Card title={`Segments (${segments.length})`} style={{ marginTop: "1rem" }}>
        {segments.length === 0 && <Text>No segments marked yet.</Text>}
        {segments.map((seg) => (
          <div
            key={seg.id}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "0.4rem 0",
              borderBottom: "1px solid #eee",
            }}
          >
            <span>
              {formatTime(seg.start_time)} – {formatTime(seg.end_time)}
            </span>
            <Pill variant={seg.decision === "keep" ? "confirm" : "danger"}>{seg.decision}</Pill>
            {seg.tag && <Pill variant="secondary">{seg.tag}</Pill>}
            <Pill>{seg.provenance}</Pill>
            <Button variant="text" color="danger" onClick={() => deleteSegment(seg.id)}>
              Delete
            </Button>
          </div>
        ))}
      </Card>

      <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <Button onClick={handleExport}>Export edited video</Button>
        {exportResult && <Text>Exported to {exportResult}</Text>}
      </div>
    </div>
  );
}
