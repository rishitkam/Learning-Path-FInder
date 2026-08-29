"""Semantic relevance between a learner's goal and a course. Course vectors are frozen at build time."""

from functools import lru_cache
from pathlib import Path

import numpy as np
from model2vec import StaticModel

DATA = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def _model():
    return StaticModel.from_pretrained("minishlab/potion-base-8M")


@lru_cache(maxsize=1)
def _vectors():
    return np.load(DATA / "vectors.npy")


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
