import { Button, Card, Select, Text } from "@noahwright/design";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ExportJobStatus, Resolution, Segment, Video, videoStreamUrl } from "../api";
import SegmentEditorPanel from "../components/SegmentEditorPanel";
import Timeline from "../components/Timeline";
import TransportBar from "../components/TransportBar";

const UNDO_LIMIT = 25;

function dirOf(path: string): string {
  const idx = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  return idx >= 0 ? path.slice(0, idx) : "";
}

function defaultExportFilename(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot >= 0 ? `${filename.slice(0, dot)}_edited${filename.slice(dot)}` : `${filename}_edited`;
}

function flashTitle(message: string) {
  const original = document.title;
  let showingMessage = false;
  const interval = window.setInterval(() => {
    document.title = showingMessage ? original : `🎬 ${message}`;
    showingMessage = !showingMessage;
  }, 1000);
  function stop() {
    window.clearInterval(interval);
    document.title = original;
    window.removeEventListener("focus", stop);
  }
  window.addEventListener("focus", stop);
}

function notifyExportFinished(job: ExportJobStatus) {
  const title = job.state === "succeeded" ? "Export complete" : "Export failed";
  const body = job.state === "succeeded" ? `Saved to ${job.output_path}` : job.error ?? undefined;

  if (typeof Notification !== "undefined" && Notification.permission === "granted") {
    new Notification(title, { body });
  }
  if (document.hidden || !document.hasFocus()) {
    flashTitle(title);
  }
}

export default function EditorView() {
  const { id } = useParams();
  const videoId = id as string;
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const initTriggered = useRef(false);

  const [video, setVideo] = useState<Video | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [existingTags, setExistingTags] = useState<string[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [outputPath, setOutputPath] = useState("");
  const [resolution, setResolution] = useState<Resolution>("1080p");
  const [exportJob, setExportJob] = useState<ExportJobStatus | null>(null);
  const [undoStack, setUndoStack] = useState<Segment[][]>([]);
  const [redoStack, setRedoStack] = useState<Segment[][]>([]);

  const refreshSegmentsAndTags = useCallback(async () => {
    try {
      const [segs, tags] = await Promise.all([api.listSegments(videoId), api.listTags()]);
      setSegments(segs);
      setExistingTags(tags);
    } catch (err) {
      setError(String(err));
    }
  }, [videoId]);

  const refresh = useCallback(async () => {
    try {
      const v = await api.getVideo(videoId);
      setVideo(v);
      await refreshSegmentsAndTags();
      setError(null);
    } catch (err) {
      setError(String(err));
    }
  }, [videoId, refreshSegmentsAndTags]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    api.getExportStatus(videoId).then(setExportJob).catch(() => {});
  }, [videoId]);

  useEffect(() => {
    if (exportJob?.state !== "running") return;
    const timer = window.setTimeout(async () => {
      try {
        const next = await api.getExportStatus(videoId);
        setExportJob(next);
        if (next.state === "succeeded" || next.state === "failed") {
          notifyExportFinished(next);
        }
      } catch (err) {
        setError(String(err));
      }
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [exportJob, videoId]);

  // The timeline is always a full partition of the video - seed one
  // full-length "keep" segment the moment we reliably know the real
  // duration (the <video> element's own metadata, not ffprobe, which may
  // not have succeeded/finished yet).
  async function handleLoadedMetadata() {
    const el = videoRef.current;
    if (!el) return;
    setCurrentTime(el.currentTime);
    if (segments.length === 0 && !initTriggered.current && el.duration > 0) {
      initTriggered.current = true;
      try {
        setSegments(await api.initSegments(videoId, el.duration));
      } catch (err) {
        setError(String(err));
      }
    }
  }

  const duration = video?.duration ?? videoRef.current?.duration ?? 0;

  const selectedSegment = useMemo(
    () => segments.find((s) => s.id === selectedSegmentId) ?? null,
    [segments, selectedSegmentId],
  );

  function seekTo(time: number) {
    const clamped = Math.min(duration, Math.max(0, time));
    if (videoRef.current) videoRef.current.currentTime = clamped;
    setCurrentTime(clamped);
  }

  function togglePlay() {
    const el = videoRef.current;
    if (!el) return;
    if (el.paused) el.play();
    else el.pause();
  }

  function pushUndo() {
    setUndoStack((stack) => [...stack.slice(-(UNDO_LIMIT - 1)), segments]);
    setRedoStack([]);
  }

  async function restoreSnapshot(snapshot: Segment[]) {
    try {
      setSegments(
        await api.replaceSegments(
          videoId,
          snapshot.map(({ start_time, end_time, decision, tags }) => ({
            start_time,
            end_time,
            decision,
            tags,
          })),
        ),
      );
      setSelectedSegmentId(null);
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleUndo() {
    if (undoStack.length === 0) return;
    const previous = undoStack[undoStack.length - 1];
    setUndoStack((s) => s.slice(0, -1));
    setRedoStack((r) => [...r.slice(-(UNDO_LIMIT - 1)), segments]);
    await restoreSnapshot(previous);
  }

  async function handleRedo() {
    if (redoStack.length === 0) return;
    const next = redoStack[redoStack.length - 1];
    setRedoStack((r) => r.slice(0, -1));
    setUndoStack((s) => [...s.slice(-(UNDO_LIMIT - 1)), segments]);
    await restoreSnapshot(next);
  }

  async function handleSnip() {
    if (duration <= 0) return;
    pushUndo();
    try {
      setSegments(await api.splitSegment(videoId, currentTime, duration));
      setSelectedSegmentId(null);
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleRemoveBoundary(time: number) {
    pushUndo();
    try {
      setSegments(await api.mergeSegments(videoId, time));
      setSelectedSegmentId(null);
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleToggleDelete() {
    if (!selectedSegment) return;
    pushUndo();
    try {
      await api.updateSegment(selectedSegment.id, {
        decision: selectedSegment.decision === "cut" ? "keep" : "cut",
      });
      await refreshSegmentsAndTags();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleAddTag(tag: string) {
    if (!selectedSegment) return;
    pushUndo();
    try {
      await api.addTag(selectedSegment.id, tag);
      await refreshSegmentsAndTags();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleRemoveTag(tag: string) {
    if (!selectedSegment) return;
    pushUndo();
    try {
      await api.removeTag(selectedSegment.id, tag);
      await refreshSegmentsAndTags();
    } catch (err) {
      setError(String(err));
    }
  }

  // Space plays/pauses, Delete toggles the selected clip's delete state,
  // Ctrl/Cmd+Z undoes, Ctrl/Cmd+Shift+Z (or Ctrl+Y) redoes. Ignored while
  // typing in a text field (including the tag combobox).
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;
      const mod = e.ctrlKey || e.metaKey;
      if (e.key === " ") {
        e.preventDefault();
        togglePlay();
      } else if (e.key === "Delete") {
        handleToggleDelete();
      } else if (mod && !e.shiftKey && e.key.toLowerCase() === "z") {
        e.preventDefault();
        handleUndo();
      } else if (mod && (e.key.toLowerCase() === "y" || (e.shiftKey && e.key.toLowerCase() === "z"))) {
        e.preventDefault();
        handleRedo();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSegment, undoStack, redoStack, segments]);

  async function handleBrowseOutputPath() {
    try {
      const initialDir = outputPath ? dirOf(outputPath) : `${dirOf(video!.path)}/edited`;
      const initialFile = outputPath ? undefined : defaultExportFilename(video!.filename);
      const result = await api.pickSaveFile(initialDir, initialFile);
      if (result.path) setOutputPath(result.path);
    } catch {
      setError("Native file picker unavailable — type the path manually.");
    }
  }

  async function handleExport() {
    if (typeof Notification !== "undefined" && Notification.permission === "default") {
      Notification.requestPermission();
    }
    try {
      const job = await api.startExport(videoId, {
        output_path: outputPath.trim() || null,
        resolution,
      });
      setExportJob(job);
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleOpenExportedFile() {
    if (!exportJob?.output_path) return;
    try {
      await api.openFile(exportJob.output_path);
    } catch (err) {
      setError(String(err));
    }
  }

  if (!video) {
    return <Text>{error ?? "Loading…"}</Text>;
  }

  return (
    <div>
      <Button variant="text" onClick={() => navigate("/")}>
        ← Back to library
      </Button>

      <h2 style={{ margin: "0.5rem 0" }}>{video.filename}</h2>

      {error && <Text tone="error">{error}</Text>}

      {/* No native controls: the custom timeline below is the only seek UI,
          to avoid two scrubbers disagreeing with each other. */}
      <video
        ref={videoRef}
        src={videoStreamUrl(video.id)}
        style={{ width: "100%", maxHeight: 480, background: "#000", borderRadius: 8 }}
        onTimeUpdate={() => setCurrentTime(videoRef.current?.currentTime ?? 0)}
        onLoadedMetadata={handleLoadedMetadata}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
      />

      <div style={{ margin: "0.75rem 0", display: "flex", justifyContent: "center", gap: "1rem" }}>
        <TransportBar playing={playing} onTogglePlay={togglePlay} onStep={(d) => seekTo(currentTime + d)} />
        <div style={{ display: "flex", gap: "0.4rem" }}>
          <Button variant="outline" size="small" onClick={handleUndo} disabled={undoStack.length === 0}>
            ↶ Undo
          </Button>
          <Button variant="outline" size="small" onClick={handleRedo} disabled={redoStack.length === 0}>
            ↷ Redo
          </Button>
        </div>
      </div>

      <Timeline
        duration={duration}
        currentTime={currentTime}
        segments={segments}
        selectedSegmentId={selectedSegmentId}
        onSelectSegment={setSelectedSegmentId}
        onSeek={seekTo}
        onSnip={handleSnip}
        onRemoveBoundary={handleRemoveBoundary}
      />

      <SegmentEditorPanel
        segment={selectedSegment}
        existingTags={existingTags}
        onToggleDelete={handleToggleDelete}
        onAddTag={handleAddTag}
        onRemoveTag={handleRemoveTag}
      />

      <Card title="Export" style={{ marginTop: "1rem" }}>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ flex: "1 1 260px" }}>
            <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.25rem" }}>
              Output path (optional)
            </label>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <input
                placeholder="(default: an /edited subfolder next to the source)"
                value={outputPath}
                onChange={(e) => setOutputPath(e.target.value)}
                style={{
                  flex: 1,
                  padding: "0.4rem 0.6rem",
                  borderRadius: 6,
                  border: "1px solid #ccc",
                  boxSizing: "border-box",
                }}
              />
              <Button variant="outline" onClick={handleBrowseOutputPath}>
                Browse…
              </Button>
            </div>
          </div>

          <Select
            label="Resolution"
            value={resolution}
            onChange={(e) => setResolution(e.target.value as Resolution)}
          >
            <option value="1080p">1080p (recommended)</option>
            <option value="720p">720p</option>
            <option value="original">Original resolution</option>
          </Select>

          <Button onClick={handleExport} disabled={exportJob?.state === "running"}>
            {exportJob?.state === "running" ? "Exporting…" : "Export edited video"}
          </Button>
        </div>

        <div style={{ marginTop: "0.5rem" }}>
          {exportJob?.state === "running" && (
            <Text>
              Exporting{exportJob.progress != null ? ` — ${Math.round(exportJob.progress * 100)}%` : "…"}
            </Text>
          )}
          {exportJob?.state === "succeeded" && exportJob.output_path && (
            <Text>
              ✅ Exported to{" "}
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  handleOpenExportedFile();
                }}
              >
                {exportJob.output_path}
              </a>
            </Text>
          )}
          {exportJob?.state === "failed" && <Text tone="error">❌ Export failed: {exportJob.error}</Text>}
        </div>
      </Card>
    </div>
  );
}
