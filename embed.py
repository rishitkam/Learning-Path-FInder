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
    return np.load(DATA / "vectors.npy")


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
    vecs = _vectors()
    if len(vecs) != len(catalog):
        raise ValueError(f"vectors.npy has {len(vecs)} rows but the catalog has {len(catalog)}. "
                         "Rerun scripts/build_graph.py --apply, they are written together.")
    v = _model().encode([goal_text])[0]
    norm = np.linalg.norm(v)
    if not norm:
        return lambda c: 0.5                               # nothing the model recognised, so no signal
    sims = vecs @ (v / norm)
    at = {c["id"]: i for i, c in enumerate(catalog)}
    return lambda c: float(sims[at[c["id"]]] + 1) / 2      # cosine runs -1 to 1, the score wants 0 to 1
