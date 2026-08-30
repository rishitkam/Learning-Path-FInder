"""Semantic relevance between a learner's goal and a course. Course vectors are frozen at build time."""

import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
from model2vec import StaticModel

DATA = Path(__file__).resolve().parent / "data"


# lru_cache remembers the result, it does not stop two threads running the function at once. Two
# concurrent first requests both entered the loader and tqdm's progress bar raised inside it, which
# reached the browser as a 500 and looked like a CORS failure. Cheap after the first call.
_loading = threading.Lock()


@lru_cache(maxsize=1)
def _load_model():
    return StaticModel.from_pretrained("minishlab/potion-base-8M")


@lru_cache(maxsize=1)
def _load_vectors():
    import json
    ids = json.loads((DATA / "vector_ids.json").read_text())
    return np.load(DATA / "vectors.npy"), {course: row for row, course in enumerate(ids)}


def _model():
    with _loading:
        return _load_model()


def _vectors():
    with _loading:
        return _load_vectors()


def warm():
    """Pay the load once at startup rather than on whoever arrives first."""
    _model(), _vectors()


def relevance(goal_text, catalog):
    """Returns the scoring function build() takes. Flat if we have no goal text to compare against."""
    if not goal_text or not goal_text.strip():
        return lambda c: 0.5
    vecs, row = _vectors()
    missing = [c["id"] for c in catalog if c["id"] not in row]
    if missing:
        raise ValueError(f"{len(missing)} catalog items have no vector, first is {missing[0]}. "
                         "Rerun scripts/build_graph.py --apply, they are written together.")
    v = _model().encode([goal_text])[0]
    norm = np.linalg.norm(v)
    if not norm:
        return lambda c: 0.5                               # nothing the model recognised, so no signal
    sims = vecs @ (v / norm)
    # Looked up by id, not by position, so catalog order never has to match the vector file.
    return lambda c: float(sims[row[c["id"]]] + 1) / 2     # cosine runs -1 to 1, the score wants 0 to 1
