import { useMemo, useRef, useState } from "react";

// Not in @noahwright/design yet (its Select only wraps a native fixed-option
// <select>) - built here first against real usage, tracked for upstreaming
// in snip-snap#1 / design#15.
interface TagComboboxProps {
  existingTags: string[];
  excludeTags: string[];
  onAdd: (tag: string) => void;
}

export default function TagCombobox({ existingTags, excludeTags, onAdd }: TagComboboxProps) {
  const [value, setValue] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const suggestions = useMemo(() => {
    const query = value.trim().toLowerCase();
    return existingTags
      .filter((t) => !excludeTags.includes(t))
      .filter((t) => !query || t.toLowerCase().includes(query))
      .slice(0, 8);
  }, [existingTags, excludeTags, value]);

  function commit(tag: string) {
    const trimmed = tag.trim();
    if (!trimmed) return;
    onAdd(trimmed);
    setValue("");
    setOpen(false);
  }

  return (
    <div style={{ position: "relative", display: "inline-block", width: "100%" }}>
      <input
        ref={inputRef}
        value={value}
        placeholder="Add a tag…"
        onChange={(e) => {
          setValue(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit(value);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        style={{
          padding: "0.4rem 0.6rem",
          borderRadius: 6,
          border: "1px solid #ccc",
          width: "100%",
          boxSizing: "border-box",
        }}
      />
      {open && suggestions.length > 0 && (
        <ul
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            margin: "2px 0 0",
            padding: "0.25rem 0",
            listStyle: "none",
            background: "#fff",
            border: "1px solid #ccc",
            borderRadius: 6,
            boxShadow: "0 4px 10px rgba(0,0,0,0.15)",
            zIndex: 10,
            maxHeight: 160,
            overflowY: "auto",
          }}
        >
          {suggestions.map((tag) => (
            <li
              key={tag}
              onMouseDown={(e) => {
                e.preventDefault();
                commit(tag);
              }}
              style={{ padding: "0.4rem 0.6rem", cursor: "pointer" }}
            >
              {tag}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
