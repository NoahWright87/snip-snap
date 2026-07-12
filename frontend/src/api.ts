const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export type SourceType = "raw" | "edited" | "unpaired";
export type Decision = "keep" | "cut";
export type Provenance = "manual" | "diff_inferred" | "suggested_confirmed";
export type VideoStatus = "unprocessed" | "in_progress" | "exported";

export interface Video {
  id: number;
  filename: string;
  path: string;
  duration: number | null;
  source_type: SourceType;
  paired_video_id: number | null;
  created_at: string;
  segment_count: number;
  status: VideoStatus;
}

export interface Segment {
  id: number;
  video_id: number;
  start_time: number;
  end_time: number;
  decision: Decision;
  tag: string | null;
  provenance: Provenance;
  created_at: string;
}

export const api = {
  listVideos: () => request<Video[]>("/videos"),

  ingest: (folder: string) =>
    request<{ added: number[]; skipped_existing: number }>("/videos/ingest", {
      method: "POST",
      body: JSON.stringify({ folder }),
    }),

  getVideo: (id: number) => request<Video>(`/videos/${id}`),

  pairVideos: (id: number, pairedVideoId: number | null, sourceType: SourceType) =>
    request<Video>(`/videos/${id}/pair`, {
      method: "POST",
      body: JSON.stringify({ paired_video_id: pairedVideoId, source_type: sourceType }),
    }),

  listSegments: (videoId: number) => request<Segment[]>(`/videos/${videoId}/segments`),

  createSegment: (
    videoId: number,
    segment: { start_time: number; end_time: number; decision: Decision; tag?: string | null },
  ) =>
    request<Segment>(`/videos/${videoId}/segments`, {
      method: "POST",
      body: JSON.stringify(segment),
    }),

  updateSegment: (
    id: number,
    patch: Partial<Pick<Segment, "start_time" | "end_time" | "decision" | "tag">>,
  ) => request<Segment>(`/segments/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),

  deleteSegment: (id: number) => request<void>(`/segments/${id}`, { method: "DELETE" }),

  listTags: () => request<string[]>("/tags"),

  exportVideo: (videoId: number) =>
    request<{ output_path: string }>(`/videos/${videoId}/export`, { method: "POST" }),
};

export function videoStreamUrl(videoId: number): string {
  return `${BASE}/videos/${videoId}/stream`;
}
