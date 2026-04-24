from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray
from sklearn.model_selection import (
  train_test_split,  # type: ignore[import-not-found, import-untyped]  # noqa: I001, E501
)


def stratified_regression_split(
  y: ArrayLike,
  n_bins: int = 8,
  test_size: float = 0.2,
  random_state: int = 0,
) -> tuple[NDArray[np.int_], NDArray[np.int_]]:
  """Bin continuous ``y`` and return train/test index arrays (stratified by bin)."""
  yv = np.asarray(y, dtype=float).ravel()
  yq, _ = pd.qcut(yv, n_bins, labels=False, retbins=True, duplicates="drop")
  yq = np.nan_to_num(yq, nan=0.0)
  i = np.arange(len(yv))
  i_train, i_test = train_test_split(
    i, test_size=test_size, random_state=random_state, stratify=yq
  )
  return i_train, i_test
