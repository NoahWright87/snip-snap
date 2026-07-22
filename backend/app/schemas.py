from typing import Literal, Optional

from pydantic import BaseModel

SourceType = Literal["raw", "edited", "unpaired"]
Decision = Literal["keep", "cut"]
Provenance = Literal["manual", "diff_inferred", "suggested_confirmed"]


class VideoOut(BaseModel):
    id: str
    filename: str
    path: str
    duration: Optional[float]
    source_type: SourceType
    paired_video_id: Optional[str]
    created_at: str
    segment_count: int
    status: str


class IngestRequest(BaseModel):
    folder: str


class IngestResponse(BaseModel):
    added: list[str]
    skipped_existing: int


class FolderOut(BaseModel):
    id: int
    path: str
    added_at: str
    video_count: int


class PairRequest(BaseModel):
    paired_video_id: Optional[str] = None
    source_type: SourceType


class SegmentOut(BaseModel):
    id: str
    video_id: str
    start_time: float
    end_time: float
    decision: Decision
    tags: list[str]
    provenance: Provenance
    created_at: str


class SegmentCreate(BaseModel):
    start_time: float
    end_time: float
    decision: Decision = "keep"
    tags: list[str] = []
    provenance: Provenance = "manual"


class SegmentUpdate(BaseModel):
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    decision: Optional[Decision] = None


class TagRequest(BaseModel):
    tag: str


class InitSegmentsRequest(BaseModel):
    duration: float


class SplitSegmentRequest(BaseModel):
    time: float
    duration: float


class MergeSegmentsRequest(BaseModel):
    time: float


class ReplaceSegment(BaseModel):
    start_time: float
    end_time: float
    decision: Decision = "keep"
    tags: list[str] = []


class ReplaceSegmentsRequest(BaseModel):
    segments: list[ReplaceSegment]


class OpenFileRequest(BaseModel):
    path: str


Resolution = Literal["1080p", "720p", "original"]


class ExportRequest(BaseModel):
    output_path: Optional[str] = None
    resolution: Resolution = "1080p"


class ExportJobStatus(BaseModel):
    state: Literal["idle", "running", "succeeded", "failed"]
    progress: Optional[float] = None
    output_path: Optional[str] = None
    error: Optional[str] = None


class FfmpegStatus(BaseModel):
    state: Literal["checking", "downloading", "ready", "error"]
    message: str = ""
    progress: Optional[float] = None


class AnalysisStatus(BaseModel):
    state: Literal["idle", "downloading_model", "running", "succeeded", "failed"]
    message: str = ""
    progress: Optional[float] = None
