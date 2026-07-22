import { useAnalysisStatus } from "../hooks/useAnalysisStatus";

// Mirrors FfmpegBanner.tsx's visual pattern. Self-contained (polls its own
// status) so it can render globally in App.tsx and stay visible even if the
// user navigates away from the Library view mid-analysis.
export default function AnalysisBanner() {
  const [status] = useAnalysisStatus();
  if (!status || status.state === "idle") return null;

  const isError = status.state === "failed";
  const isDone = status.state === "succeeded";
  const pct = status.progress != null ? ` (${Math.round(status.progress * 100)}%)` : "";

  return (
    <div
      role="status"
      style={{
        padding: "0.6rem 1rem",
        background: isError ? "var(--danger, #dc2626)" : isDone ? "var(--confirm, #16a34a)" : "var(--primary, #2563eb)",
        color: "#fff",
        fontSize: "0.9rem",
      }}
    >
      {isError ? (
        <>⚠️ Library analysis failed: {status.message}</>
      ) : isDone ? (
        <>✅ {status.message || "Library analysis complete."}</>
      ) : (
        <>
          🔍 Analyzing your library{pct} — {status.message || "this may take a while"}. You can keep
          editing.
        </>
      )}
    </div>
  );
}
