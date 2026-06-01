import { useEffect, useState } from "react";

import { runAseRelax } from "../lib/api";
import type { SimulationJob } from "../types/material";

export function SimulationQueue({ materialId, formula }: { materialId: string; formula?: string }) {
  const [job, setJob] = useState<SimulationJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setJob(null);
    setError(null);
    setLoading(false);
  }, [materialId]);

  if (!materialId) {
    return <div className="empty-note">Select a material first.</div>;
  }

  async function handleRun() {
    setLoading(true);
    setError(null);
    setJob(null);
    try {
      setJob(await runAseRelax(materialId));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="simulation-panel">
      <div className="panel-row">
        <div>
          <span className="metric-label">ASE demo relaxation</span>
          <strong>{formula ? `${materialId} / ${formula}` : materialId}</strong>
        </div>
        <button type="button" onClick={handleRun} disabled={loading}>
          {loading ? "Running..." : "Run relax"}
        </button>
      </div>
      {error && <div className="error-note">{error}</div>}
      {job?.status === "failed" && <div className="error-note">{job.error ?? "Simulation failed."}</div>}
      {job?.status === "completed" && job.result && (
        <div className="kv-grid">
          <span>Calculator</span>
          <strong>{job.result.calculator ?? "unknown"}</strong>
          <span>Energy</span>
          <strong>{formatNumber(job.result.energy)}</strong>
          <span>Max force</span>
          <strong>{formatNumber(job.result.max_force)}</strong>
          <span>Steps</span>
          <strong>{job.result.steps ?? "n/a"}</strong>
          <span>Converged</span>
          <strong>{job.result.converged === null ? "n/a" : String(Boolean(job.result.converged))}</strong>
        </div>
      )}
    </div>
  );
}

function formatNumber(value: unknown): string {
  return typeof value === "number" ? value.toFixed(5).replace(/0+$/, "").replace(/\.$/, "") : "n/a";
}
