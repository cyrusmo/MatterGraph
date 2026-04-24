from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


def dcg(relevances: ArrayLike) -> float:
  r = np.asarray(relevances, dtype=float)
  if r.size == 0:
    return 0.0
  g = 2.0**r - 1.0
  i = np.arange(1, len(r) + 1, dtype=float)
  return float(np.sum(g / np.log2(i + 1)))


def ndcg_at_k(relevances: ArrayLike, k: int = 10) -> float:
  r = np.asarray(relevances, dtype=float)[:k]
  if r.size == 0:
    return 0.0
  ideal = np.sort(r)[::-1]
  d = dcg(r)
  i = dcg(ideal)
  return d / i if i > 0 else 0.0
