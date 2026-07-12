const HEARTBEAT_INTERVAL_MS = 30_000;

/**
 * Keeps the local backend alive while this tab is open, and asks it to shut
 * down as soon as the tab closes - so closing the window doesn't leave an
 * orphaned backend process (and GPU memory, if ML is running) behind.
 */
export function startHeartbeat(): void {
  const ping = () => fetch("/api/heartbeat", { method: "POST" }).catch(() => {});
  ping();
  setInterval(ping, HEARTBEAT_INTERVAL_MS);

  window.addEventListener("pagehide", () => {
    navigator.sendBeacon("/api/shutdown");
  });
}
