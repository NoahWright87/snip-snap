import { useEffect, useState } from "react";
import { AppUpdateStatus, api } from "../api";

export default function UpdateBanner() {
  const [status, setStatus] = useState<AppUpdateStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getAppUpdateStatus()
      .then((next) => {
        if (!cancelled) setStatus(next);
      })
      .catch(() => {
        // Update checks are best-effort; failures should not disrupt editing.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status || !status.update_available || !status.latest_version) return null;

  return (
    <div
      role="status"
      style={{
        padding: "0.6rem 1rem",
        background: "var(--success, #15803d)",
        color: "#fff",
        fontSize: "0.9rem",
      }}
    >
      ⬆️ Update available: {status.latest_version} (you have {status.current_version}).{" "}
      <a
        href={status.release_url}
        target="_blank"
        rel="noreferrer"
        style={{ color: "#fff", fontWeight: 700, textDecoration: "underline" }}
      >
        Download latest installer
      </a>
      .
    </div>
  );
}

