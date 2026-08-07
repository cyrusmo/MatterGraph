from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd
from mattergraph.schema.material import Material

Direction = Literal["minimize", "maximize"]
Missing = Literal["worst", "neutral", "exclude"]

# Fill value applied to a normalized objective a candidate has no value for. "exclude" has
# no fill: those candidates are dropped before scoring.
_MISSING_FILL: dict[str, float | None] = {"worst": 0.0, "neutral": 0.5, "exclude": None}


class Scorecard:
  """
  Toy scorecard: min–max–normalize each objective, apply optional weights,
  filter by hard constraints, then return a ranked :class:`pandas.DataFrame`.
  This is a transparent baseline, not a production decision engine.

  Two behaviors matter when reading a ranking, and :meth:`report` states both for a
  given pool:

  * **Scores are pool-relative.** Each objective is min–max scaled across the candidates
    passed to :meth:`rank`, so a score describes standing *within this pool* and is not
    comparable across runs or across different objective sets. Read ranks and the raw
    values, not the absolute score.
  * **A missing objective is scored, not excluded** — see ``missing`` below. Under a hard
    constraint the opposite applies: a missing value removes the candidate.
  """

  def __init__(
    self,
    objectives: dict[str, Direction | dict[str, Any]],
    constraints: dict[str, dict[str, Any]] | None = None,
    weights: dict[str, float] | None = None,
    *,
    missing: Missing = "worst",
  ) -> None:
    """
    :param missing: policy for a candidate that has no value for an objective.
      ``"worst"`` (default) scores it at the bottom of the normalized range, which
      penalizes absent data as though it were bad data; ``"neutral"`` scores it at the
      midpoint so absence neither helps nor hurts; ``"exclude"`` drops the candidate from
      the ranking entirely. Call :meth:`report` to see how often the policy fired.
    """
    if missing not in _MISSING_FILL:
      supported = ", ".join(sorted(_MISSING_FILL))
      msg = f"unsupported missing policy {missing!r}; supported policies: {supported}"
      raise ValueError(msg)
    self.objectives, self.parsed_weights = self._parse_objectives(objectives, weights)
    self.constraints = constraints or {}
    self.missing = missing

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
  def _minmax_dir(col: np.ndarray, direction: Direction) -> np.ndarray | None:
    """Min-max normalize one objective, or return ``None`` if it carries no information.

    A column is uninformative when every value is missing, or when every present value is
    identical: in both cases it cannot separate candidates. Such a column is dropped by
    :meth:`rank` rather than normalized, because a zero-span column would otherwise map to
    all-ones under ``minimize`` and all-zeros under ``maximize`` — letting the direction
    label alone move scores.
    """
    v = col.astype(float)
    mask = ~np.isnan(v)
    if not np.any(mask):
      return None
    mn, mx = float(np.nanmin(v[mask])), float(np.nanmax(v[mask]))
    if not mx > mn:
      return None
    norm = (v - mn) / (mx - mn)
    if direction == "minimize":
      norm = 1.0 - norm
    norm[~mask] = np.nan
    return norm

  def report(self, materials: list[Material]) -> dict[str, Any]:
    """Audit a ranking before trusting it: coverage, degeneracy, and method mixing.

    Companion to :meth:`rank`, in the spirit of :meth:`CandidateSlice.report`. Every field
    here describes something that changes a shortlist without changing any material.
    """
    keys = list(self.objectives.keys())
    arr, kept_i = self._row_values(materials, keys)
    sub = arr[kept_i, :] if kept_i else np.empty((0, len(keys)), dtype=float)

    coverage: dict[str, int] = {}
    zero_coverage: list[str] = []
    degenerate: list[str] = []
    for j, k in enumerate(keys):
      col = sub[:, j] if len(kept_i) else np.array([], dtype=float)
      present = int(np.count_nonzero(~np.isnan(col)))
      coverage[k] = present
      if present == 0:
        zero_coverage.append(k)
      elif self._minmax_dir(col, self.objectives[k]) is None:
        degenerate.append(k)

    ignored = sorted(set(zero_coverage) | set(degenerate))
    return {
      "pool_size": len(materials),
      "ranked_count": len(kept_i),
      "excluded_by_constraints": len(materials) - len(kept_i),
      "objectives": keys,
      "weights": dict(self.parsed_weights),
      "missing_policy": self.missing,
      "coverage": coverage,
      "zero_coverage_objectives": zero_coverage,
      "degenerate_objectives": degenerate,
      "ignored_objectives": ignored,
      "effective_objectives": [k for k in keys if k not in ignored],
      "mixed_methods": self._mixed_methods(materials, keys),
      "mixed_averaging_schemes": self._mixed_averaging_schemes(materials, keys),
      "mixed_hull_conventions": self._mixed_hull_conventions(materials, keys),
      "binary_normalization": len(kept_i) <= 2,
      "scores_are_pool_relative": True,
    }

  @staticmethod
  def _mixed_methods(materials: list[Material], keys: list[str]) -> dict[str, list[str]]:
    """Objectives whose values come from more than one method, e.g. DFT and experiment."""
    out: dict[str, list[str]] = {}
    for k in keys:
      methods = {
        str(p.method)
        for m in materials
        if (p := m.get_property(k)) is not None and p.method is not None
      }
      if len(methods) > 1:
        out[k] = sorted(methods)
    return out

  @staticmethod
  def _mixed_conventions(
    materials: list[Material],
    keys: list[str],
    *,
    marker: str,
  ) -> dict[str, list[str]]:
    """Objectives pooling more than one convention under ``MaterialProperty.extra[marker]``.

    A property carrying no marker counts as its own convention, ``"unspecified"``, rather than
    being skipped. That distinction is the whole point: the dangerous mix is usually between a
    source that labels its convention and one that does not, and skipping the unlabelled side
    leaves exactly one distinct value and reports no mixing at all.
    """
    out: dict[str, list[str]] = {}
    for k in keys:
      conventions: set[str] = set()
      for m in materials:
        p = m.get_property(k)
        if p is None:
          continue
        value = p.extra.get(marker)
        conventions.add(str(value) if value is not None else "unspecified")
      if len(conventions) > 1:
        out[k] = sorted(conventions)
    return out

  @classmethod
  def _mixed_averaging_schemes(
    cls,
    materials: list[Material],
    keys: list[str],
  ) -> dict[str, list[str]]:
    """Objectives pooling more than one elastic averaging convention.

    Materials Project reports Voigt-Reuss-Hill averages; JARVIS reports Voigt, which is an
    upper bound. Ranking both in one column biases the Voigt-sourced candidates high.
    """
    return cls._mixed_conventions(materials, keys, marker="averaging_scheme")

  @classmethod
  def _mixed_hull_conventions(
    cls,
    materials: list[Material],
    keys: list[str],
  ) -> dict[str, list[str]]:
    """Objectives pooling more than one convention for distance from the convex hull.

    OQMD reports a hull *distance*, which is negative for a phase below the current hull;
    Materials Project reports ``energy_above_hull``, which is ``>= 0`` by construction. Ranking
    both in one column biases the OQMD-sourced candidates low, and a constraint such as
    ``energy_above_hull <= 0.05`` admits OQMD records that MP would have reported as ``0.0``.
    """
    return cls._mixed_conventions(materials, keys, marker="hull_convention")

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
    if self.missing == "exclude":
      kept_i = [i for i in kept_i if not np.any(np.isnan(sub_all[i, :]))]
      if not kept_i:
        return pd.DataFrame(columns=[id_key, "score", *keys])
    sub = sub_all[kept_i, :]
    scores = np.zeros(len(kept_i), dtype=float)
    wsum = 0.0
    fill = _MISSING_FILL[self.missing]
    for j, k in enumerate(keys):
      col = self._minmax_dir(sub[:, j], self.objectives[k])
      if col is None:
        # Uninformative column: it cannot separate candidates, so it contributes to
        # neither the weighted sum nor its denominator.
        continue
      w = self.parsed_weights.get(k, 1.0)
      scores += w * np.nan_to_num(col, nan=fill if fill is not None else 0.0)
      wsum += w
    if wsum > 0:
      scores /= wsum
    out: dict[str, Any] = {id_key: [materials[i].material_id for i in kept_i], "score": scores}
    for j, k in enumerate(keys):
      out[k] = [materials[i].get_numeric(k) for i in kept_i]
    df = pd.DataFrame(out)
    return df.sort_values("score", ascending=False).reset_index(drop=True)
