# Scoring (open source)

The public **`Scorecard`** is a **toy, transparent** baseline: min–max normalize objectives, optional weights, hard constraints, and a single aggregate score. It is suitable for **demos, teaching, and simple baselines**, not as a production decision engine.

You can also drive the same logic via the API: `POST /scores/rank` with `objectives`, `constraints`, and optional `weights`.
