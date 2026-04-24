from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


def coverage_at_target(
  y_true: ArrayLike,
  y_lo: ArrayLike,
  y_hi: ArrayLike,
) -> float:
  """Fraction of points where the interval ``[y_lo, y_hi]`` contains ``y_true``."""
  yt = np.asarray(y_true, dtype=float).ravel()
  lo = np.asarray(y_lo, dtype=float).ravel()
  hi = np.asarray(y_hi, dtype=float).ravel()
  m = (yt >= lo) & (yt <= hi)
  return float(np.mean(m)) if m.size else 0.0
