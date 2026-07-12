import { useFfmpegStatus } from "../hooks/useFfmpegStatus";

// A plain styled div rather than a design-system component: there's no
// banner/alert primitive in @noahwright/design yet. Worth adding there
// alongside the other upstream candidates (snip-snap#1) since this kind of
// dismissible status banner is generic, not snip-snap-specific.
export default function FfmpegBanner() {
  const status = useFfmpegStatus();
  if (!status || status.state === "ready") return null;

  const isError = status.state === "error";
  const pct = status.progress != null ? ` (${Math.round(status.progress * 100)}%)` : "";

  return (
    <div
      role="status"
      style={{
        padding: "0.6rem 1rem",
        background: isError ? "var(--danger, #dc2626)" : "var(--primary, #2563eb)",
        color: "#fff",
        fontSize: "0.9rem",
      }}
    >
      {isError ? (
        <>⚠️ {status.message}</>
      ) : (
        <>
          ⬇️ Setting up ffmpeg in the background{pct} — {status.message || "this may take a minute"}.
          You can keep editing; export will wait until it's ready.
        </>
      )}
    </div>
  );
}
