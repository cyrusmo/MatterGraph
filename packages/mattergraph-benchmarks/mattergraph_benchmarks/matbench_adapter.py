from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _load_matbench_task(name: str) -> Any:
  try:
    from matbench.task import MatbenchTask  # type: ignore[import-not-found, import-untyped]
  except ImportError as e:  # pragma: no cover
    msg = "Install the optional `matbench` package to use the Matbench adapter."
    raise ImportError(msg) from e
  t = MatbenchTask(name)  # type: ignore[operator]
  t.load()  # type: ignore[no-untyped-call]
  return t


def matbench_dataframe(task: str = "matbench_v0.1_log_gvrh") -> pd.DataFrame:
  """
  Load a Matbench task into a :class:`pandas.DataFrame` with a ``target`` and ``split`` column.

  The ``matbench`` package is an optional install.
  """
  t = _load_matbench_task(task)
  f = t.get_train_and_val()  # type: ignore[no-untyped-call]
  train = f[0]  # type: ignore[index]
  test = f[1]  # type: ignore[index]
  tr_x, tr_y, _ = train  # type: ignore[misc]
  te_x, te_y, _ = test  # type: ignore[misc]

  def _as_df(x: object, y: object, s: str) -> pd.DataFrame:
    d = x.to_pandas() if hasattr(x, "to_pandas") else pd.DataFrame(x)  # type: ignore[attr-defined, arg-type, call-overload]  # noqa: E501
    d = d.copy()
    d["target"] = np.asarray(y).ravel()
    d["split"] = s
    return d

  tr = _as_df(tr_x, tr_y, "train")
  te = _as_df(te_x, te_y, "test")
  return pd.concat([tr, te], ignore_index=True)


def matbench_regression(task: str = "matbench_v0.1_log_gvrh") -> dict[str, Any]:
  """Return simple numpy arrays for train/test splits of a Matbench regression task."""
  df = matbench_dataframe(task=task)
  train = df[df["split"] == "train"]
  test = df[df["split"] == "test"]
  y_tr = train["target"].to_numpy()
  y_te = test["target"].to_numpy()
  x_tr = train.drop(columns=["target", "split"], errors="ignore")
  x_te = test.drop(columns=["target", "split"], errors="ignore")
  return {
    "train_X": x_tr,
    "train_y": y_tr,
    "test_X": x_te,
    "test_y": y_te,
  }
