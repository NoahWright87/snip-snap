"""CLI: extract and cache CLIP embeddings for every tagged segment in your
library (or one folder), so later phases can train per-tag classifiers on
top of them.

Usage:
    python -m ml.extract_embeddings              # every registered folder
    python -m ml.extract_embeddings /path/to/dir  # just one folder

Run from backend/, with ml/requirements.txt installed (see that file for
why it's separate from requirements.txt).
"""
import argparse
import sys
from pathlib import Path

from app import db, store
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
