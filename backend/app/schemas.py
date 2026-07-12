from typing import Literal, Optional

from pydantic import BaseModel

SourceType = Literal["raw", "edited", "unpaired"]
Decision = Literal["keep", "cut"]
Provenance = Literal["manual", "diff_inferred", "suggested_confirmed"]


class VideoOut(BaseModel):
    id: int
    filename: str
    path: str
    duration: Optional[float]
    source_type: SourceType
    paired_video_id: Optional[int]
    created_at: str
    segment_count: int
    status: str


class IngestRequest(BaseModel):
    folder: str


class IngestResponse(BaseModel):
    added: list[int]
    skipped_existing: int


class PairRequest(BaseModel):
    paired_video_id: Optional[int] = None
    source_type: SourceType


class SegmentOut(BaseModel):
    id: int
    video_id: int
    start_time: float
    end_time: float
    decision: Decision
    tag: Optional[str]
    provenance: Provenance
    created_at: str


class SegmentCreate(BaseModel):
    start_time: float
    end_time: float
    decision: Decision
    tag: Optional[str] = None
    provenance: Provenance = "manual"


class SegmentUpdate(BaseModel):
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    decision: Optional[Decision] = None
    tag: Optional[str] = None


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
