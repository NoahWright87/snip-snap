"""CLIP embedding extraction for tagged segments.

Runs on ONNX Runtime against a pre-converted CLIP visual encoder (see
convert_to_onnx.py for how that .onnx file is produced, and
app/clip_setup.py for how it's downloaded onto the user's machine) rather
than PyTorch/open_clip directly - keeps the packaged app's runtime deps
small. Turns each manually tagged segment into a fingerprint vector that a
classifier can later learn from (issue #4+). Standalone - not imported by
the running app's request-handling code, only by routes/analysis.py's
background job.
"""
import io
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from app import clip_locate, config
from app.ffmpeg_locate import ffmpeg_path
from app.proc import run_hidden

CACHE_DIR = config.DATA_DIR / "embeddings_cache"

FRAME_SAMPLE_FPS = 1.5

# CLIP's standard preprocessing: resize the shorter edge to 224, center-crop
# to 224x224, normalize with these fixed mean/std constants. These are a
# property of the model checkpoint (see convert_to_onnx.py), not something
# to tune here.
CLIP_INPUT_SIZE = 224
CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

_session = None
_input_name = None


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


def _preprocess_image(image: Image.Image) -> np.ndarray:
    """Resize-shorter-side-then-center-crop-then-normalize, matching what
    open_clip's `preprocess` transform did for this checkpoint - reimplemented
    directly since that convenience function isn't available without
    open_clip/torch. Returns a (3, 224, 224) float32 array."""
    width, height = image.size
    scale = CLIP_INPUT_SIZE / min(width, height)
    new_size = (round(width * scale), round(height * scale))
    image = image.resize(new_size, Image.BICUBIC)

    left = (new_size[0] - CLIP_INPUT_SIZE) // 2
    top = (new_size[1] - CLIP_INPUT_SIZE) // 2
    image = image.crop((left, top, left + CLIP_INPUT_SIZE, top + CLIP_INPUT_SIZE))

    array = np.asarray(image, dtype=np.float32) / 255.0
    array = (array - CLIP_MEAN) / CLIP_STD
    return array.transpose(2, 0, 1)  # HWC -> CHW


def load_clip_model():
    """Loads the ONNX CLIP visual encoder once as a module-level singleton.
    Uses a CUDA execution provider if onnxruntime/the machine supports one,
    otherwise falls back to CPU (issue #3: don't hard-require a GPU) - the
    ONNX Runtime equivalent of the old `torch.cuda.is_available()` check."""
    global _session, _input_name
    if _session is not None:
        return _session, _input_name

    import onnxruntime as ort

    model_path = clip_locate.model_path()
    if model_path is None:
        raise RuntimeError("CLIP model not downloaded yet - call clip_setup.ensure_clip_ready() first")

    providers = ["CPUExecutionProvider"]
    if "CUDAExecutionProvider" in ort.get_available_providers():
        providers.insert(0, "CUDAExecutionProvider")

    session = ort.InferenceSession(str(model_path), providers=providers)
    _session, _input_name = session, session.get_inputs()[0].name
    return _session, _input_name


def embed_frames(frames: list[Image.Image]) -> Optional[np.ndarray]:
    """Embeds frames with CLIP and mean-pools them into a single vector.
    Returns None if given no frames."""
    if not frames:
        return None

    session, input_name = load_clip_model()
    batch = np.stack([_preprocess_image(frame) for frame in frames])
    features = session.run(None, {input_name: batch})[0]
    features = features / np.linalg.norm(features, axis=-1, keepdims=True)
    return features.mean(axis=0)


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
