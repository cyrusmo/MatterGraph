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

### Mixed sources are reported, not blocked

`report()` lists any objective whose values come from more than one `method` (DFT vs
experiment) under `mixed_methods`, any that mixes elastic averaging conventions under
`mixed_averaging_schemes`, and any that mixes hull conventions under `mixed_hull_conventions`.

These matter when pooling sources:

- **Averaging schemes.** Materials Project reports Voigt–Reuss–Hill averages while JARVIS
  reports Voigt, an upper bound, so a mixed column ranks JARVIS candidates high for a reason
  that has nothing to do with the material.
- **Hull conventions.** OQMD reports a hull *distance*, which is negative for a phase below the
  current hull; Materials Project's `energy_above_hull` is `>= 0` by construction. A mixed
  column ranks OQMD candidates low, and a constraint like `energy_above_hull <= 0.05` admits
  OQMD records that MP would have reported as `0.0`.

**A property carrying no convention marker counts as its own convention, `"unspecified"`.**
That is deliberate: the dangerous mix is usually between a source that labels its convention
and one that does not — Materials Project attaches no hull marker at all — and skipping the
unlabelled side would leave one distinct value and report no mixing. A pool where nothing is
marked is not flagged, so this never becomes constant noise.

## Derived elastic quantities

`mattergraph.derived.elastic` computes Young's modulus, Poisson's ratio, Pugh's ratio, and
specific stiffness from bulk and shear moduli — transparent arithmetic on properties already
present, with nothing fitted and nothing imputed.

```python
from mattergraph import MaterialStore, Scorecard
from mattergraph.derived import elastic_frame, with_derived_properties

store = MaterialStore.from_demo()
print(elastic_frame(store.materials))          # inspect, with warnings per row

pool = [with_derived_properties(m) for m in store.materials]
Scorecard(objectives={"specific_stiffness": "maximize"}).rank(pool)
```

`with_derived_properties` returns a copy carrying `youngs_modulus`, `poisson_ratio`, and
`specific_stiffness` as canonical properties, so a `Scorecard` can rank on them. Materials
missing either modulus come back unchanged rather than gaining imputed values.

Three things to know before screening on these:

- **They are stiffness, not strength.** Yield strength, hardness, and fracture toughness are
  governed by microstructure, which this schema does not hold. Two heat treatments of one alloy
  differ fivefold in yield strength while E, K, and G barely move.
- **Pugh's ratio and Poisson's ratio are the same information.** They are an exact 1:1 monotone
  map of each other when computed from one K and G pair, so they cannot disagree and are not
  independent confirmation.
- **Specific stiffness barely separates metals.** E/ρ is ~26 MN·m/kg for aluminium, titanium,
  and steel alike. If a shortlist is ranking on it, it is close to ranking on noise.

Nonphysical input is rejected rather than returned: a non-positive modulus violates Born
stability, and the negative Young's modulus it produces would enter a `maximize` objective as
the worst candidate and look like a real result.

### Constraints can match metadata

Besides `min` and `max`, a constraint supports `equals`, which matches a property value **or** a key in `Material.metadata`. This is how you pin a ranking to a single level of theory:

```python
Scorecard(objectives={...}, constraints={"functional": {"equals": "PBEsol"}})
```

## What a scorecard does not know

There is no temperature, pressure, environment, time dependence, microstructure, or cost anywhere in the schema. A ranking is over 0 K, defect-free, single-phase, bulk-periodic descriptions. When a requirement depends on anything else — corrosion, fatigue, processing — the screen cannot test it, and that belongs in your write-up rather than in a caveat nobody reads. See [examples/underwater-drone-screening](https://github.com/cyrusmo/MatterGraph/tree/main/examples/underwater-drone-screening) for a worked example that states its own blind spots.
