import { Button, Card, Checkbox, Input, Modal, Pill, Text } from "@noahwright/design";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Folder, Video, VideoStatus } from "../api";
import FolderSection from "../components/FolderSection";

const STATUS_LABEL: Record<VideoStatus, string> = {
  unprocessed: "Unprocessed",
  in_progress: "In progress",
  exported: "Exported",
};

const STATUS_VARIANT: Record<VideoStatus, "default" | "primary" | "confirm"> = {
  unprocessed: "default",
  in_progress: "primary",
  exported: "confirm",
};

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "unknown length";
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function dirOf(path: string): string {
  const idx = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  return idx >= 0 ? path.slice(0, idx) : "";
}

export default function LibraryView() {
  const navigate = useNavigate();
  const [folders, setFolders] = useState<Folder[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [folderPath, setFolderPath] = useState("");
  const [hideExported, setHideExported] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const [f, v] = await Promise.all([api.listFolders(), api.listVideos()]);
      setFolders(f);
      setVideos(v);
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleIngest() {
    if (!folderPath.trim()) return;
    try {
      await api.ingest(folderPath.trim());
      setFolderPath("");
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleBrowseFolder() {
    try {
      const result = await api.pickFolder(folderPath || undefined);
      if (result.path) setFolderPath(result.path);
    } catch {
      setError("Native folder picker unavailable — type the path manually.");
    }
  }

  async function handleRemoveFolder(folder: Folder) {
    try {
      await api.removeFolder(folder.id);
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  const visibleVideos = hideExported ? videos.filter((v) => v.status !== "exported") : videos;

  const videosByFolder = useMemo(() => {
    const map = new Map<string, Video[]>();
    for (const v of visibleVideos) {
      const key = dirOf(v.path);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(v);
    }
    return map;
  }, [visibleVideos]);

  function renderVideoCard(video: Video) {
    return (
      // Intentionally not using Card's `href` (real <a> navigation): a full
      // page load fires `pagehide`, which our heartbeat script treats as
      // "the app is closing" and shuts the backend down. Client-side
      // navigation via useNavigate keeps the document alive.
      <Card
        key={video.id}
        title={video.filename}
        subtitle={formatDuration(video.duration)}
        interactive
        role="link"
        tabIndex={0}
        onClick={() => navigate(`/videos/${video.id}`)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            navigate(`/videos/${video.id}`);
          }
        }}
        style={{ cursor: "pointer" }}
      >
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <Pill variant={STATUS_VARIANT[video.status]}>{STATUS_LABEL[video.status]}</Pill>
          {video.source_type !== "unpaired" && <Pill variant="secondary">{video.source_type}</Pill>}
          {video.segment_count > 0 && (
            <Pill>
              {video.segment_count} segment{video.segment_count === 1 ? "" : "s"}
            </Pill>
          )}
        </div>
      </Card>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.75rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <Text>
            {videos.length} video{videos.length === 1 ? "" : "s"} in your library
          </Text>
          <Checkbox label="Hide exported" checked={hideExported} onChange={(e) => setHideExported(e.target.checked)} />
        </div>
        <Button onClick={() => setIngestOpen(true)}>Add folder</Button>
      </div>

      {error && <Text tone="error">{error}</Text>}
      {loading && <Text>Loading…</Text>}

      {!loading && folders.length === 0 && (
        <Text>No videos yet. Click "Add folder" to point snip-snap at a folder of videos.</Text>
      )}

      {folders.map((folder) => (
        <FolderSection
          key={folder.id}
          folder={folder}
          videos={videosByFolder.get(folder.path) ?? []}
          onRemove={() => handleRemoveFolder(folder)}
        >
          {renderVideoCard}
        </FolderSection>
      ))}

      <Modal
        open={ingestOpen}
        onClose={() => setIngestOpen(false)}
        title="Add a folder of videos"
        actions={[
          { label: "Cancel", variant: "secondary" },
          { label: "Add", variant: "primary", onClick: handleIngest },
        ]}
      >
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <Input
              label="Folder path"
              placeholder="C:\Videos\MyFootage"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
            />
          </div>
          <Button variant="outline" onClick={handleBrowseFolder}>
            Browse…
          </Button>
        </div>
      </Modal>
    </div>
  );
}
