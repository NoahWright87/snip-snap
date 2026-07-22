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
  id: string;
  filename: string;
  path: string;
  duration: number | null;
  source_type: SourceType;
  paired_video_id: string | null;
  created_at: string;
  segment_count: number;
  status: VideoStatus;
}

export interface Segment {
  id: string;
  video_id: string;
  start_time: number;
  end_time: number;
  decision: Decision;
  tags: string[];
  provenance: Provenance;
  created_at: string;
}

export type Resolution = "1080p" | "720p" | "original";

export interface ExportJobStatus {
  state: "idle" | "running" | "succeeded" | "failed";
  progress: number | null;
  output_path: string | null;
  error: string | null;
}

export interface FfmpegStatus {
  state: "checking" | "downloading" | "ready" | "error";
  message: string;
  progress: number | null;
}

export interface Folder {
  id: number;
  path: string;
  added_at: string;
  video_count: number;
}

export interface AnalysisStatus {
  state: "idle" | "downloading_model" | "running" | "succeeded" | "failed";
  message: string;
  progress: number | null;
}

export const api = {
  listVideos: () => request<Video[]>("/videos"),

  ingest: (folder: string) =>
    request<{ added: string[]; skipped_existing: number }>("/videos/ingest", {
      method: "POST",
      body: JSON.stringify({ folder }),
    }),

  getVideo: (id: string) => request<Video>(`/videos/${id}`),

  pairVideos: (id: string, pairedVideoId: string | null, sourceType: SourceType) =>
    request<Video>(`/videos/${id}/pair`, {
      method: "POST",
      body: JSON.stringify({ paired_video_id: pairedVideoId, source_type: sourceType }),
    }),

  listSegments: (videoId: string) => request<Segment[]>(`/videos/${videoId}/segments`),

  initSegments: (videoId: string, duration: number) =>
    request<Segment[]>(`/videos/${videoId}/segments/init`, {
      method: "POST",
      body: JSON.stringify({ duration }),
    }),

  splitSegment: (videoId: string, time: number, duration: number) =>
    request<Segment[]>(`/videos/${videoId}/segments/split`, {
      method: "POST",
      body: JSON.stringify({ time, duration }),
    }),

  mergeSegments: (videoId: string, time: number) =>
    request<Segment[]>(`/videos/${videoId}/segments/merge`, {
      method: "POST",
      body: JSON.stringify({ time }),
    }),

  replaceSegments: (
    videoId: string,
    segments: Pick<Segment, "start_time" | "end_time" | "decision" | "tags">[],
  ) =>
    request<Segment[]>(`/videos/${videoId}/segments`, {
      method: "PUT",
      body: JSON.stringify({ segments }),
    }),

  updateSegment: (id: string, patch: Partial<Pick<Segment, "start_time" | "end_time" | "decision">>) =>
    request<Segment>(`/segments/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),

  deleteSegment: (id: string) => request<void>(`/segments/${id}`, { method: "DELETE" }),

  addTag: (segmentId: string, tag: string) =>
    request<Segment>(`/segments/${segmentId}/tags`, { method: "POST", body: JSON.stringify({ tag }) }),

  removeTag: (segmentId: string, tag: string) =>
    request<Segment>(`/segments/${segmentId}/tags/${encodeURIComponent(tag)}`, { method: "DELETE" }),

  listTags: () => request<string[]>("/tags"),

  startExport: (videoId: string, options: { output_path?: string | null; resolution: Resolution }) =>
    request<ExportJobStatus>(`/videos/${videoId}/export`, {
      method: "POST",
      body: JSON.stringify(options),
    }),

  getExportStatus: (videoId: string) => request<ExportJobStatus>(`/videos/${videoId}/export/status`),

  getFfmpegStatus: () => request<FfmpegStatus>("/ffmpeg/status"),

  pickFolder: (initialDir?: string) =>
    request<{ path: string | null }>("/dialogs/pick-folder", {
      method: "POST",
      body: JSON.stringify({ initial_dir: initialDir ?? null }),
    }),

  pickSaveFile: (initialDir?: string, initialFile?: string) =>
    request<{ path: string | null }>("/dialogs/pick-save-file", {
      method: "POST",
      body: JSON.stringify({ initial_dir: initialDir ?? null, initial_file: initialFile ?? null }),
    }),

  openFile: (path: string) =>
    request<{ ok: boolean }>("/open-file", { method: "POST", body: JSON.stringify({ path }) }),

  listFolders: () => request<Folder[]>("/folders"),

  removeFolder: (id: number) => request<void>(`/folders/${id}`, { method: "DELETE" }),

  runAnalysis: () => request<AnalysisStatus>("/analysis/run", { method: "POST" }),

  getAnalysisStatus: () => request<AnalysisStatus>("/analysis/status"),
};

export function videoStreamUrl(videoId: string): string {
  return `${BASE}/videos/${videoId}/stream`;
}
