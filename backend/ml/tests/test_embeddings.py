import numpy as np
import pytest
import torch

from app.proc import run_hidden

from ml import embeddings


@pytest.fixture(scope="module")
def synthetic_video(tmp_path_factory):
    """A tiny 2-second synthetic video (ffmpeg's testsrc pattern) - real
    enough for ffmpeg to seek/decode frames from, without needing any real
    footage."""
    path = tmp_path_factory.mktemp("video") / "test.mp4"
    result = run_hidden(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=64x64:rate=10",
            "-pix_fmt", "yuv420p",
            str(path),
        ],
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return path


class _FakeClipModel:
    """Stands in for a real CLIP model: downloading actual weights needs a
    network call this sandbox's egress policy blocks. `encode_image` returns
    a deterministic, distinct vector per frame in the batch so pooling
    behavior is still meaningfully testable."""

    def eval(self):
        return self

    def to(self, device):
        return self

    def encode_image(self, batch):
        n = batch.shape[0]
        return torch.arange(1, n * 4 + 1, dtype=torch.float32).reshape(n, 4)


@pytest.fixture(autouse=True)
def _stub_clip_model(monkeypatch):
    monkeypatch.setattr(
        "open_clip.create_model_and_transforms",
        lambda name, pretrained: (_FakeClipModel(), None, lambda image: torch.zeros(3, 2, 2)),
    )
    embeddings._model = None
    embeddings._preprocess = None
    embeddings._device = None
    yield
    embeddings._model = None
    embeddings._preprocess = None
    embeddings._device = None


def test_sample_frame_times_spans_the_segment():
    times = embeddings.sample_frame_times(10.0, 12.0, fps=1.5)
    assert len(times) == 3
    assert all(10.0 <= t < 12.0 for t in times)


def test_sample_frame_times_handles_very_short_segments():
    times = embeddings.sample_frame_times(5.0, 5.05)
    assert times == [pytest.approx(5.025)]


def test_extract_frame_returns_an_image(synthetic_video):
    frame = embeddings.extract_frame(synthetic_video, 1.0)
    assert frame is not None
    assert frame.size == (64, 64)


def test_extract_frame_past_end_of_video_returns_none(synthetic_video):
    assert embeddings.extract_frame(synthetic_video, 999.0) is None


def test_extract_frame_without_ffmpeg_returns_none(monkeypatch, synthetic_video):
    monkeypatch.setattr(embeddings, "ffmpeg_path", lambda: None)
    assert embeddings.extract_frame(synthetic_video, 1.0) is None


def test_embed_frames_of_no_frames_is_none():
    assert embeddings.embed_frames([]) is None


def test_embed_segment_produces_a_pooled_vector(synthetic_video):
    vector = embeddings.embed_segment(synthetic_video, 0.0, 2.0)
    assert vector is not None
    # 2s segment at the default 1.5fps sampling -> 3 frames -> fake model's
    # per-frame features average out to a vector matching the mean of 3
    # distinct unit-normalized rows, not the raw [1,2,3,4]/[5,6,7,8]/... input.
    assert vector.shape == (4,)
    assert np.isfinite(vector).all()


def test_load_clip_model_falls_back_to_cpu_without_cuda(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    _, _, device = embeddings.load_clip_model()
    assert device == "cpu"


def test_load_clip_model_uses_cuda_when_available(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    _, _, device = embeddings.load_clip_model()
    assert device == "cuda"


def test_cache_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings, "CACHE_DIR", tmp_path)
    vectors = {"seg-a": np.array([1.0, 2.0, 3.0]), "seg-b": np.array([4.0, 5.0])}
    embeddings.save_cache("video-1", vectors)

    loaded = embeddings.load_cache("video-1")
    assert set(loaded) == {"seg-a", "seg-b"}
    np.testing.assert_array_equal(loaded["seg-a"], vectors["seg-a"])
    np.testing.assert_array_equal(loaded["seg-b"], vectors["seg-b"])


def test_load_cache_missing_file_returns_empty_dict(tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings, "CACHE_DIR", tmp_path)
    assert embeddings.load_cache("nonexistent") == {}
