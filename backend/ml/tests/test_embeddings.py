import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper

from app import clip_locate
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


def _build_synthetic_onnx_model(output_path, output_dim=4):
    """A tiny, deterministic stand-in for the real CLIP export (flatten the
    224x224x3 input, then a fixed linear projection) - real CLIP weights
    need a network download this sandbox's egress policy blocks (see
    ml/convert_to_onnx.py), so this validates the real load/run/pool/cache
    wiring in embeddings.py without needing one."""
    input_size = 3 * embeddings.CLIP_INPUT_SIZE * embeddings.CLIP_INPUT_SIZE
    rng = np.random.default_rng(0)
    weight = rng.standard_normal((input_size, output_dim)).astype(np.float32)

    input_tensor = helper.make_tensor_value_info(
        "pixel_values", TensorProto.FLOAT, ["batch", 3, embeddings.CLIP_INPUT_SIZE, embeddings.CLIP_INPUT_SIZE]
    )
    output_tensor = helper.make_tensor_value_info("image_features", TensorProto.FLOAT, ["batch", output_dim])
    weight_initializer = helper.make_tensor("weight", TensorProto.FLOAT, weight.shape, weight.flatten().tolist())

    flatten_node = helper.make_node("Flatten", ["pixel_values"], ["flattened"], axis=1)
    matmul_node = helper.make_node("MatMul", ["flattened", "weight"], ["image_features"])

    graph = helper.make_graph(
        [flatten_node, matmul_node], "tiny_test_model", [input_tensor], [output_tensor], [weight_initializer]
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    onnx.checker.check_model(model)
    onnx.save(model, str(output_path))


@pytest.fixture(autouse=True)
def _stub_clip_model(tmp_path, monkeypatch):
    cache_dir = tmp_path / "clip_bin"
    cache_dir.mkdir(parents=True, exist_ok=True)
    _build_synthetic_onnx_model(cache_dir / clip_locate.MODEL_FILENAME)
    monkeypatch.setattr(clip_locate, "cache_dir", lambda: cache_dir)

    embeddings._session = None
    embeddings._input_name = None
    yield
    embeddings._session = None
    embeddings._input_name = None


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


def test_preprocess_image_produces_the_expected_shape():
    from PIL import Image

    image = Image.fromarray(np.zeros((300, 400, 3), dtype=np.uint8))
    array = embeddings._preprocess_image(image)
    assert array.shape == (3, embeddings.CLIP_INPUT_SIZE, embeddings.CLIP_INPUT_SIZE)
    assert array.dtype == np.float32


def test_embed_frames_of_no_frames_is_none():
    assert embeddings.embed_frames([]) is None


def test_embed_segment_produces_a_pooled_vector(synthetic_video):
    vector = embeddings.embed_segment(synthetic_video, 0.0, 2.0)
    assert vector is not None
    assert vector.shape == (4,)
    assert np.isfinite(vector).all()


def test_load_clip_model_raises_a_clear_error_if_not_downloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(clip_locate, "cache_dir", lambda: tmp_path / "nonexistent")
    with pytest.raises(RuntimeError, match="not downloaded"):
        embeddings.load_clip_model()


def test_load_clip_model_falls_back_to_cpu_provider(monkeypatch):
    import onnxruntime as ort

    monkeypatch.setattr(ort, "get_available_providers", lambda: ["CPUExecutionProvider"])
    captured = {}
    real_session_cls = ort.InferenceSession

    def _spy(path, providers=None):
        captured["providers"] = providers
        return real_session_cls(path, providers=providers)

    monkeypatch.setattr(ort, "InferenceSession", _spy)
    embeddings.load_clip_model()
    assert captured["providers"] == ["CPUExecutionProvider"]


def test_load_clip_model_prefers_cuda_when_available(monkeypatch):
    import onnxruntime as ort

    monkeypatch.setattr(ort, "get_available_providers", lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"])
    captured = {}
    real_session_cls = ort.InferenceSession

    def _spy(path, providers=None):
        captured["providers"] = providers
        # CUDA isn't actually installed in this sandbox - load with CPU
        # regardless, we're only checking what our own code requested.
        return real_session_cls(path, providers=["CPUExecutionProvider"])

    monkeypatch.setattr(ort, "InferenceSession", _spy)
    embeddings.load_clip_model()
    assert captured["providers"][0] == "CUDAExecutionProvider"


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
