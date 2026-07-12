import { Button, Card, CardGrid, Input, Modal, Pill, Text } from "@noahwright/design";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Video, VideoStatus } from "../api";

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

export default function LibraryView() {
  const navigate = useNavigate();
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [folderPath, setFolderPath] = useState("");

  async function refresh() {
    setLoading(true);
    try {
      setVideos(await api.listVideos());
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

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <Text>{videos.length} video{videos.length === 1 ? "" : "s"} in your library</Text>
        <Button onClick={() => setIngestOpen(true)}>Add folder</Button>
      </div>

      {error && <Text tone="error">{error}</Text>}
      {loading && <Text>Loading…</Text>}

      {!loading && videos.length === 0 && (
        <Text>No videos yet. Click "Add folder" to point snip-snap at a folder of videos.</Text>
      )}

      <CardGrid minCardWidth="260px">
        {videos.map((video) => (
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
              {video.source_type !== "unpaired" && (
                <Pill variant="secondary">{video.source_type}</Pill>
              )}
              {video.segment_count > 0 && (
                <Pill>{video.segment_count} segment{video.segment_count === 1 ? "" : "s"}</Pill>
              )}
            </div>
          </Card>
        ))}
      </CardGrid>

      <Modal
        open={ingestOpen}
        onClose={() => setIngestOpen(false)}
        title="Add a folder of videos"
        actions={[
          { label: "Cancel", variant: "secondary" },
          { label: "Add", variant: "primary", onClick: handleIngest },
        ]}
      >
        <Input
          label="Folder path"
          placeholder="C:\Videos\MyFootage"
          value={folderPath}
          onChange={(e) => setFolderPath(e.target.value)}
        />
      </Modal>
    </div>
  );
}
