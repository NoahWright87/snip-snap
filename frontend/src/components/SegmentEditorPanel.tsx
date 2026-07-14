import { Card, Checkbox, Pill, Text } from "@noahwright/design";
import { Segment } from "../api";
import TagCombobox from "./TagCombobox";

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(1);
  return `${mins}:${secs.padStart(4, "0")}`;
}

interface SegmentEditorPanelProps {
  segment: Segment | null;
  existingTags: string[];
  onToggleDelete: () => void;
  onAddTag: (tag: string) => void;
  onRemoveTag: (tag: string) => void;
}

export default function SegmentEditorPanel({
  segment,
  existingTags,
  onToggleDelete,
  onAddTag,
  onRemoveTag,
}: SegmentEditorPanelProps) {
  return (
    <Card title="Selected clip" style={{ marginTop: "1rem" }}>
      {!segment && <Text>Click a clip on the timeline to edit it.</Text>}
      {segment && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <Text>
            {formatTime(segment.start_time)} – {formatTime(segment.end_time)}
          </Text>

          <Checkbox
            label="Delete this clip?"
            checked={segment.decision === "cut"}
            onChange={onToggleDelete}
          />

          <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
            {segment.tags.length === 0 && <Text tone="muted">No tags yet.</Text>}
            {segment.tags.map((tag) => (
              <Pill key={tag} onDismiss={() => onRemoveTag(tag)}>
                {tag}
              </Pill>
            ))}
          </div>

          <div style={{ maxWidth: 260 }}>
            <TagCombobox existingTags={existingTags} excludeTags={segment.tags} onAdd={onAddTag} />
          </div>
        </div>
      )}
    </Card>
  );
}
