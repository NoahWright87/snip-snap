import { useEffect, useState } from "react";
import { api, FfmpegStatus } from "../api";

const POLL_INTERVAL_MS = 2000;

export function useFfmpegStatus(): FfmpegStatus | null {
  const [status, setStatus] = useState<FfmpegStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function poll() {
      try {
        const next = await api.getFfmpegStatus();
        if (cancelled) return;
        setStatus(next);
        if (next.state === "checking" || next.state === "downloading") {
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
  }, []);

  return status;
}
