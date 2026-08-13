import { useEffect, useState } from "react";

import { ServiceUnavailableError, runAseRelax } from "../lib/api";
import { formatNumber } from "../lib/format";
import type { SimulationJob, SimulationReadiness } from "../types/material";

export function SimulationQueue({
  materialId,
  formula,
  readiness,
}: {
  materialId: string;
  formula?: string;
  readiness?: SimulationReadiness;
}) {
  const [job, setJob] = useState<SimulationJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setJob(null);
    setError(null);
    setUnavailable(false);
    setLoading(false);
  }, [materialId]);

  if (!materialId) {
    return <p className="empty-note">Select a material first.</p>;
  }

  async function handleRun() {
    setLoading(true);
    setError(null);
    setUnavailable(false);
    setJob(null);
    try {
      setJob(await runAseRelax(materialId));
    } catch (e) {
      setUnavailable(e instanceof ServiceUnavailableError);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const result = job?.status === "completed" ? job.result : null;

  return (
    <div>
      <div className="panel-row">
        <div>
          <span className="metric-label">Target</span>
          <strong>{formula ? `${materialId} / ${formula}` : materialId}</strong>
        </div>
        <button
          className="ghost-button"
          type="button"
          onClick={handleRun}
          disabled={loading || !readiness?.ready}
          aria-busy={loading}
        >
          {loading ? "Running..." : "Run relax"}
        </button>
      </div>

      <div className={`eval-output ${readiness?.ready ? "pass" : "warn"}`}>
        <span className="eval-label">Calculator check</span>
        <span>{readiness?.reason ?? "Checking ASE/EMT compatibility…"}</span>
      </div>

      {error && (
        <div className={`eval-output ${unavailable ? "warn" : "fail"}`}>
          <span className="eval-label">{unavailable ? "Unavailable" : "ASE failed"}</span>
          <span>{error}</span>
        </div>
      )}

      {job?.status === "failed" && (
        <div className="eval-output fail">
          <span className="eval-label">ASE failed</span>
          <span>{job.error ?? "Simulation failed."}</span>
        </div>
      )}

      {result && (
        <div className="property-grid">
          <div className="property-box">
            <span>Calculator</span>
            <strong>{result.calculator ?? "unknown"}</strong>
          </div>
          <div className="property-box">
            <span>Energy</span>
            <strong>{formatNumber(result.energy, 5)}</strong>
          </div>
          <div className="property-box">
            <span>Max force</span>
            <strong>{formatNumber(result.max_force, 5)}</strong>
          </div>
          <div className="property-box">
            <span>Steps</span>
            <strong>{result.steps ?? "n/a"}</strong>
          </div>
          <div className="property-box">
            <span>Converged</span>
            <strong>
              {result.converged === null || result.converged === undefined ? (
                "n/a"
              ) : (
                <span className={`tag ${result.converged ? "pass" : "fail"}`}>
                  {result.converged ? "yes" : "no"}
                </span>
              )}
            </strong>
          </div>
        </div>
      )}

      <p className="boundary-note">
        Toy EMT relaxation, wired to demonstrate the simulation hook. It is not a production DFT
        workflow and its energies carry no physical claim.
      </p>
    </div>
  );
}
