"""One-time, dev-only: exports open_clip's CLIP visual encoder to ONNX, so
the shipped app can run it via onnxruntime without needing PyTorch at all
(see app/clip_setup.py for how the resulting file reaches a user's machine,
and ml/embeddings.py for the runtime that consumes it).

Not run by the app or by any end user. Run this once, wherever Hugging Face
is reachable (this sandbox's network egress policy returned a hard 403 for
huggingface.co when this was tried here - a policy block, not a transient
error), then publish the resulting .onnx file somewhere downloadable and
point config.CLIP_MODEL_DOWNLOAD_URL at it (e.g. a GitHub Release asset on
this repo, mirroring FFMPEG_DOWNLOAD_URL).

Only the visual (image) encoder is exported - the suggestion pipeline only
ever needs image embeddings, never CLIP's text encoder, since there's no
zero-shot text-matching step (classifiers are trained on your own tags
instead). That roughly halves the exported model's size versus full CLIP.

Usage:
    python -m ml.convert_to_onnx [output_path]

Requires ml/requirements-dev.txt (torch, open_clip_torch, onnx) - never
installed on an end user's machine or bundled into the packaged app.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import torch

MODEL_NAME = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"
DEFAULT_OUTPUT = Path(__file__).parent / "clip_visual.onnx"
INPUT_SIZE = 224


class _VisualEncoderWrapper(torch.nn.Module):
    """Exports the same code path ml/embeddings.py used in Phase 1
    (`model.encode_image(x)`), not the raw `.visual` submodule directly -
    some open_clip model variants apply an extra projection inside
    `encode_image` that isn't part of `.visual` alone, and this way the
    ONNX export is guaranteed to match what was already validated."""

    def __init__(self, clip_model):
        super().__init__()
        self.clip_model = clip_model

    def forward(self, pixel_values):
        return self.clip_model.encode_image(pixel_values)


def _load_model():
    import open_clip

    model, _, _ = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)
    model.eval()
    return model


def _export(model, output_path: Path) -> None:
    wrapper = _VisualEncoderWrapper(model)
    dummy_input = torch.randn(1, 3, INPUT_SIZE, INPUT_SIZE)
    torch.onnx.export(
        wrapper,
        dummy_input,
        str(output_path),
        input_names=["pixel_values"],
        output_names=["image_features"],
        dynamic_axes={"pixel_values": {0: "batch"}, "image_features": {0: "batch"}},
        opset_version=17,
        # The newer dynamo-based exporter needs the extra `onnxscript`
        # package; the older TorchScript-based one doesn't and is plenty
        # for a fixed, already-frozen model like this.
        dynamo=False,
    )


def _parity_check(model, output_path: Path) -> float:
    """Compares the exported ONNX graph's output against the original
    PyTorch model on random input. Conversion bugs (a missed op, a subtly
    wrong dynamic axis) are a real, silent-failure-prone risk here - this
    is what catches them before the file gets published."""
    import onnxruntime as ort

    session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    sample = torch.rand(2, 3, INPUT_SIZE, INPUT_SIZE)
    with torch.no_grad():
        torch_out = model.encode_image(sample).numpy()
    onnx_out = session.run(None, {input_name: sample.numpy().astype(np.float32)})[0]

    max_abs_diff = float(np.abs(torch_out - onnx_out).max())
    if not np.allclose(torch_out, onnx_out, atol=1e-4, rtol=1e-3):
        raise RuntimeError(
            f"ONNX export diverges from PyTorch output (max abs diff {max_abs_diff:.2e}) - "
            "do not publish this file"
        )
    return max_abs_diff


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    print(f"Loading {MODEL_NAME} ({PRETRAINED})...")
    model = _load_model()

    print(f"Exporting to {args.output}...")
    _export(model, args.output)

    print("Running parity check against the original PyTorch model...")
    max_abs_diff = _parity_check(model, args.output)
    print(f"OK - max abs diff {max_abs_diff:.2e}")
    print(
        f"\nNext: publish {args.output} somewhere downloadable (e.g. a GitHub Release "
        "asset) and point SNIPSNAP_CLIP_MODEL_URL / config.CLIP_MODEL_DOWNLOAD_URL at it."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
