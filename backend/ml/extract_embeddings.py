"""CLI: extract and cache CLIP embeddings for every tagged segment in your
library (or one folder), so later phases can train per-tag classifiers on
top of them.

This is a dev/validation tool, not something the app's actual user runs -
see routes/analysis.py for the in-app "Analyze library" button that does
the same thing without a terminal.

Usage:
    python -m ml.extract_embeddings              # every registered folder
    python -m ml.extract_embeddings /path/to/dir  # just one folder

Run from backend/, with requirements.txt installed (same deps as running
the app itself - this no longer needs the separate ml/requirements-dev.txt,
which is now only for convert_to_onnx.py).
"""
import argparse
import sys
from pathlib import Path

from app import clip_setup, db, store
from app.ffmpeg_locate import is_available

from ml import embeddings


def _process_folder(folder: Path) -> None:
    data = store.read_folder_data(folder)
    videos = data.get("videos", {})
    if not videos:
        print("  no ingested videos, skipping")
        return

    for video_id, video in videos.items():
        video_path = folder / video["filename"]
        segments = video.get("segments", [])
        if not segments:
            continue
        if not video_path.is_file():
            print(f"  {video['filename']}: source file missing, skipping")
            continue

        cache = embeddings.load_cache(video_id)
        added = 0
        for segment in segments:
            if segment["id"] in cache:
                continue
            vector = embeddings.embed_segment(video_path, segment["start_time"], segment["end_time"])
            if vector is None:
                print(f"  {video['filename']}: could not extract a frame for segment {segment['id']}, skipping it")
                continue
            cache[segment["id"]] = vector
            added += 1

        if added:
            embeddings.save_cache(video_id, cache)
        print(f"  {video['filename']}: {added} new segment(s) embedded, {len(cache)} cached total")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, help="Process only this folder instead of every registered one")
    args = parser.parse_args()

    if not is_available():
        print("ffmpeg not found - can't extract frames. Run the app once first so it can set up ffmpeg, or install it and put it on PATH.")
        return 1

    print("Checking CLIP model...")
    clip_setup.ensure_clip_ready()
    status = clip_setup.get_status()
    if status["state"] != "ready":
        print(f"CLIP model isn't ready ({status['state']}: {status['message']}). Can't embed segments yet.")
        return 1

    if args.folder is not None:
        folders = [args.folder]
    else:
        db.init_db()
        with db.get_db() as conn:
            folders = store.list_registered_folders(conn)
        if not folders:
            print("No folders registered yet - add one in the app first, or pass a folder path directly.")
            return 1

    for folder in folders:
        print(f"{folder}:")
        _process_folder(folder)

    return 0


if __name__ == "__main__":
    sys.exit(main())
