import { Card, CardGrid, Pill, Text, ToggleIcon } from "@noahwright/design";
import { useState } from "react";
import { Folder, Video } from "../api";

interface FolderSectionProps {
  folder: Folder;
  videos: Video[];
  children: (video: Video) => React.ReactNode;
  onRemove: () => void;
}

export default function FolderSection({ folder, videos, children, onRemove }: FolderSectionProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <Card
      style={{ marginBottom: "1rem" }}
      title={
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <ToggleIcon preset="arrow" isToggled={expanded} onChange={setExpanded} size="sm" />
          <span style={{ fontWeight: 600, flex: 1, minWidth: 0, overflowWrap: "break-word" }}>
            {folder.path}
          </span>
          <Pill>
            {videos.length} video{videos.length === 1 ? "" : "s"}
          </Pill>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            aria-label={`Remove ${folder.path} from library`}
            title="Remove folder from library (files and edits are left alone)"
            style={{
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "1rem",
              color: "var(--danger, #dc2626)",
              padding: "0.15rem 0.4rem",
            }}
          >
            ✕
          </button>
        </div>
      }
    >
      {expanded &&
        (videos.length === 0 ? (
          <Text tone="muted">No videos in this folder yet.</Text>
        ) : (
          <CardGrid minCardWidth="240px">{videos.map(children)}</CardGrid>
        ))}
    </Card>
  );
}
