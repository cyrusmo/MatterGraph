from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd
from mattergraph.schema.material import Material

Direction = Literal["minimize", "maximize"]


class Scorecard:
  """
  Toy scorecard: min–max–normalize each objective, apply optional weights,
  filter by hard constraints, then return a ranked :class:`pandas.DataFrame`.
  This is a transparent baseline, not a mission-optimization engine.
  """

  def __init__(
    self,
    objectives: dict[str, Direction | dict[str, Any]],
    constraints: dict[str, dict[str, Any]] | None = None,
    weights: dict[str, float] | None = None,
  ) -> None:
    self.objectives, self.parsed_weights = self._parse_objectives(objectives, weights)
    self.constraints = constraints or {}

  @staticmethod
  def _parse_objectives(
    objectives: dict[str, Direction | dict[str, Any]],
    weights: dict[str, float] | None,
  ) -> tuple[dict[str, Direction], dict[str, float]]:
    out_dir: dict[str, Direction] = {}
    w: dict[str, float] = {}
    w_default = weights or {}
    for k, v in objectives.items():
      if isinstance(v, str):
        out_dir[k] = v  # type: ignore[assignment]
        w[k] = w_default.get(k, 1.0)
      else:
        out_dir[k] = v.get("direction", "maximize")
        w[k] = float(v.get("weight", w_default.get(k, 1.0)))
    return out_dir, w

  def _constraints_ok(self, m: Material) -> bool:
    for name, c in self.constraints.items():
      if "max" in c or "min" in c:
        v = m.get_numeric(name)
        if v is None:
          return False
        if "max" in c and v > float(c["max"]):
          return False
        if "min" in c and v < float(c["min"]):
          return False
      if "equals" in c:
        eq = c["equals"]
        p = m.get_property(name)
        if p is not None:
          val: Any = p.value
        elif name in m.metadata:
          val = m.metadata[name]
        else:
          return False
        if isinstance(eq, bool):
          if bool(val) is not eq:
            return False
        elif val != eq:
          return False
    return True

  def _row_values(
    self,
    materials: list[Material],
    keys: list[str],
  ) -> tuple[np.ndarray, list[int]]:
    rows = [[m.get_numeric(k) for k in keys] for m in materials]
    arr = np.array(rows, dtype=float)
    kept_i: list[int] = []
    for i, m in enumerate(materials):
      if not self._constraints_ok(m):
        continue
      row = arr[i, :]
      if not np.all(np.isnan(row)):
        kept_i.append(i)
    return arr, kept_i

  @staticmethod
  def _minmax_dir(col: np.ndarray, direction: Direction) -> np.ndarray:
    v = col.astype(float)
    mask = ~np.isnan(v)
    if not np.any(mask):
      return np.zeros_like(v)
    mn, mx = float(np.nanmin(v[mask])), float(np.nanmax(v[mask]))
    span = mx - mn if mx > mn else 1.0
    norm = (v - mn) / span
    if direction == "minimize":
      norm = 1.0 - norm
    norm[~mask] = np.nan
    return norm

  def rank(
    self,
    materials: list[Material],
    *,
    id_key: str = "material_id",
  ) -> pd.DataFrame:
    keys = list(self.objectives.keys())
    if not materials:
      return pd.DataFrame(columns=[id_key, "score", *keys])
    sub_all, kept_i = self._row_values(materials, keys)
    if not kept_i:
      return pd.DataFrame(columns=[id_key, "score", *keys])
    sub = sub_all[kept_i, :]
    scores = np.zeros(len(kept_i), dtype=float)
    wsum = 0.0
    for j, k in enumerate(keys):
      w = self.parsed_weights.get(k, 1.0)
      col = self._minmax_dir(sub[:, j], self.objectives[k])
      col = np.nan_to_num(col, nan=0.0)
      scores += w * col
      wsum += w
    if wsum > 0:
      scores /= wsum
    out: dict[str, Any] = {id_key: [materials[i].material_id for i in kept_i], "score": scores}
    for j, k in enumerate(keys):
      out[k] = [materials[i].get_numeric(k) for i in kept_i]
    df = pd.DataFrame(out)
    return df.sort_values("score", ascending=False).reset_index(drop=True)
