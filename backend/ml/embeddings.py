"""CLIP embedding extraction for tagged segments.

Phase 1 of the auto-detection roadmap (GitHub issue #3): turn each manually
tagged segment into a fingerprint vector that a classifier can later learn
from (issue #4+). Standalone - not imported by the running app.
"""
import io
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from app import config
from app.ffmpeg_locate import ffmpeg_path
from app.proc import run_hidden

CACHE_DIR = config.DATA_DIR / "embeddings_cache"

FRAME_SAMPLE_FPS = 1.5
MODEL_NAME = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"

_model = None
_preprocess = None
_device = None


def sample_frame_times(start_time: float, end_time: float, fps: float = FRAME_SAMPLE_FPS) -> list[float]:
    """Evenly-spaced timestamps within [start_time, end_time), at roughly
    `fps` samples per second. Always returns at least one timestamp (the
    segment's midpoint), even for segments shorter than one sample interval.
    """
    duration = end_time - start_time
    if duration <= 0:
        return [start_time]
    count = max(1, round(duration * fps))
    interval = duration / count
    return [start_time + (i + 0.5) * interval for i in range(count)]


def extract_frame(video_path: Path, time: float) -> Optional[Image.Image]:
    """Extracts a single frame at `time` seconds via ffmpeg. Returns None if
    ffmpeg isn't available or extraction fails (e.g. `time` past EOF)."""
    ffmpeg = ffmpeg_path()
    if ffmpeg is None:
        return None
    try:
        result = run_hidden(
            [
                ffmpeg,
                "-ss", str(time),
                "-i", str(video_path),
                "-frames:v", "1",
                "-f", "image2pipe",
                "-vcodec", "mjpeg",
                "-loglevel", "error",
                "-",
            ],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        return Image.open(io.BytesIO(result.stdout)).convert("RGB")
    except OSError:
        return None


def extract_frames(video_path: Path, times: list[float]) -> list[Image.Image]:
    frames = []
    for time in times:
        frame = extract_frame(video_path, time)
        if frame is not None:
            frames.append(frame)
    return frames


def load_clip_model():
    """Loads the CLIP model once as a module-level singleton. Uses CUDA if
    available, otherwise falls back to CPU (issue #3: don't hard-require a
    GPU)."""
    global _model, _preprocess, _device
    if _model is not None:
        return _model, _preprocess, _device

    import open_clip
    import torch

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)
    model.to(_device)
    model.eval()
    _model, _preprocess = model, preprocess
    return _model, _preprocess, _device


def embed_frames(frames: list[Image.Image]) -> Optional[np.ndarray]:
    """Embeds frames with CLIP and mean-pools them into a single vector.
    Returns None if given no frames."""
    if not frames:
        return None

    import torch

    model, preprocess, device = load_clip_model()
    batch = torch.stack([preprocess(frame) for frame in frames]).to(device)
    with torch.no_grad():
        features = model.encode_image(batch)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.mean(dim=0).cpu().numpy()


def embed_segment(video_path: Path, start_time: float, end_time: float) -> Optional[np.ndarray]:
    """Samples frames across a segment's time range and returns a single
    mean-pooled CLIP embedding, or None if no frames could be extracted."""
    times = sample_frame_times(start_time, end_time)
    frames = extract_frames(video_path, times)
    return embed_frames(frames)


def cache_path(video_id: str) -> Path:
    return CACHE_DIR / f"{video_id}.npz"


def load_cache(video_id: str) -> dict[str, np.ndarray]:
    """Loads cached segment embeddings for a video, keyed by segment id.
    Returns {} if no cache exists yet."""
    path = cache_path(video_id)
    if not path.is_file():
        return {}
    with np.load(path) as data:
        return {key: data[key] for key in data.files}


def save_cache(video_id: str, embeddings: dict[str, np.ndarray]) -> None:
    """Writes the full set of cached segment embeddings for a video,
    overwriting any existing cache file. Atomic, matching app/store.py's
    write pattern."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(video_id)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "wb") as f:
        np.savez(f, **embeddings)
    tmp_path.replace(path)
