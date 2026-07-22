import { useEffect, useState } from "react";
import { api, AnalysisStatus } from "../api";

const POLL_INTERVAL_MS = 2000;

// Always polls once on mount (not just after the button is clicked), so a
// job already in progress - e.g. the user reloaded the page mid-analysis -
// is picked back up; it stops polling on its own once the state settles.
// The returned `refresh` function restarts the poll loop immediately -
// call it right after triggering a run instead of waiting up to
// POLL_INTERVAL_MS for the next scheduled check.
export function useAnalysisStatus(): [AnalysisStatus | null, () => void] {
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [trigger, setTrigger] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function poll() {
      try {
        const next = await api.getAnalysisStatus();
        if (cancelled) return;
        setStatus(next);
        if (next.state === "downloading_model" || next.state === "running") {
          timer = window.setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch {
        if (!cancelled) timer = window.setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [trigger]);

  return [status, () => setTrigger((t) => t + 1)];
}
