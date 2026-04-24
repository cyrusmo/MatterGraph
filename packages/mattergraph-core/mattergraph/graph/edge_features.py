from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def bond_distance_feature(distances: NDArray[np.float64]) -> NDArray[np.float64]:
  return distances[:, None] if distances.ndim == 1 else distances
