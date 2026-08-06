# Scoring (open source)

The public **`Scorecard`** is a **toy, transparent** baseline: min–max normalize objectives, optional weights, hard constraints, and a single aggregate score. It is suitable for **demos, teaching, and simple baselines**, not as a production decision engine.

You can also drive the same logic via the API: `POST /scores/rank` with `objectives`, `constraints`, and optional `weights`.

## Read this before trusting a ranking

Three behaviors change a shortlist without changing any material. `Scorecard.report(materials)` states all of them for a given pool — call it alongside `rank()`.

### Scores are pool-relative

Each objective is min–max scaled across **the candidates you passed in**. A score therefore describes standing *within this pool*: add or remove one candidate and every score changes. Scores are not comparable across runs, or across different objective sets.

Read ranks and the raw values, not the absolute score. With two surviving candidates, normalization is binary — every objective collapses to {0, 1} and raw magnitudes stop mattering entirely. `report()` flags this as `binary_normalization`.

### A missing objective is scored, not excluded

By default a candidate with no value for an objective scores at the **bottom** of the normalized range, as though it had the worst value in the pool. This is deliberate — absent data should not be rewarded — but it means a sparsely populated column ranks partly on data availability rather than on physics.

Control it with the `missing` parameter:

```python
Scorecard(objectives={...}, missing="worst")     # default: absent scores worst
Scorecard(objectives={...}, missing="neutral")   # absent scores mid-range
Scorecard(objectives={...}, missing="exclude")   # candidates missing any objective are dropped
```

Under a **hard constraint** the opposite applies: a missing value removes the candidate. Know which one you are invoking.

`report()["coverage"]` gives the per-objective count of candidates that actually had a value.

### Uninformative objectives are ignored

An objective is dropped from the weighted sum — and from its denominator — when it cannot separate candidates: either no candidate has a value, or every present value is identical. `report()` lists these under `zero_coverage_objectives` and `degenerate_objectives`, with the ones that actually counted under `effective_objectives`.

Without this, a zero-spread column would normalize to all-ones under `minimize` and all-zeros under `maximize`, letting the direction label alone move scores on identical data.

### Constraints can match metadata

Besides `min` and `max`, a constraint supports `equals`, which matches a property value **or** a key in `Material.metadata`. This is how you pin a ranking to a single level of theory:

```python
Scorecard(objectives={...}, constraints={"functional": {"equals": "PBEsol"}})
```

## What a scorecard does not know

There is no temperature, pressure, environment, time dependence, microstructure, or cost anywhere in the schema. A ranking is over 0 K, defect-free, single-phase, bulk-periodic descriptions. When a requirement depends on anything else — corrosion, fatigue, processing — the screen cannot test it, and that belongs in your write-up rather than in a caveat nobody reads. See [examples/underwater-drone-screening](https://github.com/cyrusmo/MatterGraph/tree/main/examples/underwater-drone-screening) for a worked example that states its own blind spots.
