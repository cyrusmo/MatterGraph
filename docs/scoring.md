# Scoring (open source)

The public **`Scorecard`** is a **toy, transparent** baseline: min–max normalize objectives, optional weights, hard constraints, and a single aggregate score. It is suitable for **demos and teaching**, not for mission-grade optimization. Treat mission-specific, proprietary scoring as a separate module outside this repository.

You can also drive the same logic via the API: `POST /scores/rank` with `objectives`, `constraints`, and optional `weights`.
