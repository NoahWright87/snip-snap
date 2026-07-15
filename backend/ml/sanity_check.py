"""CLI: sanity-check whether a tag has enough labeled data to be worth
training a suggestion classifier for, and how well a bare-bones one does.

This is deliberately the smallest possible slice of issue #4 (per-tag
classifier training) - just enough to answer "does this work at all" before
any UI or proper training/versioning system gets built on top of it. Not
wired into the app.

Usage:
    python -m ml.sanity_check "dead air"

Run from backend/, after running `python -m ml.extract_embeddings` at least
once (needs cached embeddings to exist).
"""
import argparse
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from app import db, store

from ml import embeddings

# A tag with fewer examples than this in either class can't train anything
# reliable - refuse rather than report a misleadingly confident number.
MIN_SAMPLES_PER_CLASS = 15


def _collect_examples(tag: str) -> tuple[np.ndarray, np.ndarray]:
    db.init_db()
    with db.get_db() as conn:
        folders = store.list_registered_folders(conn)

    vectors: list[np.ndarray] = []
    labels: list[int] = []
    for folder in folders:
        data = store.read_folder_data(folder)
        for video_id, video in data.get("videos", {}).items():
            cache = embeddings.load_cache(video_id)
            if not cache:
                continue
            for segment in video.get("segments", []):
                vector = cache.get(segment["id"])
                if vector is None:
                    continue
                vectors.append(vector)
                labels.append(1 if tag in segment.get("tags", []) else 0)

    if not vectors:
        return np.empty((0, 0)), np.empty((0,))
    return np.stack(vectors), np.array(labels)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="Tag to sanity-check, exactly as it appears in the editor")
    args = parser.parse_args()

    X, y = _collect_examples(args.tag)
    if len(y) == 0:
        print("No cached embeddings found - run `python -m ml.extract_embeddings` first.")
        return 1

    positive = int(y.sum())
    negative = len(y) - positive
    print(f"Tag {args.tag!r}: {positive} tagged segment(s), {negative} untagged segment(s) with embeddings")

    if positive < MIN_SAMPLES_PER_CLASS or negative < MIN_SAMPLES_PER_CLASS:
        print(
            f"Not enough data yet - need at least {MIN_SAMPLES_PER_CLASS} of each "
            f"(tagged and untagged) before a classifier for this tag means anything. "
            f"Keep tagging clips this way and re-run later."
        )
        return 1

    n_splits = min(5, positive, negative)
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=0)
    # Imbalance is expected (content-cut moments are a small fraction of
    # runtime) - class_weight="balanced" instead of trusting raw counts.
    model = LogisticRegression(class_weight="balanced", max_iter=1000)
    predictions = cross_val_predict(model, X, y, cv=cv)

    print(f"Cross-validated over {n_splits} folds:")
    print(f"  accuracy:  {accuracy_score(y, predictions):.2f}")
    print(f"  precision: {precision_score(y, predictions, zero_division=0):.2f}")
    print(f"  recall:    {recall_score(y, predictions, zero_division=0):.2f}")
    tn, fp, fn, tp = confusion_matrix(y, predictions).ravel()
    print(f"  confusion matrix: tp={tp} fp={fp} fn={fn} tn={tn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
