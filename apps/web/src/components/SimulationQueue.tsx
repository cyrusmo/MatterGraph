import { useEffect, useState } from "react";

import { fetchChgnetReference } from "../lib/api";
import { formatNumber } from "../lib/format";
import type { ChgnetReference, ChgnetState } from "../types/material";

export function SimulationQueue({
  materialId,
  formula,
  chgnet,
}: {
  materialId: string;
  formula?: string;
  chgnet?: ChgnetState;
}) {
  const [reference, setReference] = useState<ChgnetReference | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setReference(null);
    setError(null);
  }, [materialId]);

  const referenceMatches = chgnet?.reference_material_id === materialId;

  async function showReference() {
    setLoading(true);
    setError(null);
    try {
      setReference(await fetchChgnetReference(materialId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="panel-row">
        <div>
          <span className="metric-label">Selected leader</span>
          <strong>{formula ? `${materialId} / ${formula}` : materialId}</strong>
        </div>
        <button
          className="primary-button"
          type="button"
          onClick={showReference}
          disabled={loading || !referenceMatches || !chgnet?.reference_available}
          aria-busy={loading}
        >
          {loading ? "Loading evidence…" : "Open cached reference"}
        </button>
      </div>

      <div className={`eval-output ${chgnet?.state === "cached_only" ? "warn" : chgnet?.state === "live" ? "pass" : "fail"}`}>
        <span className="eval-label">CHGNet state · {chgnet?.state ?? "checking"}</span>
        <span>{chgnet?.detail ?? "Checking local model evidence…"}</span>
      </div>

      {!referenceMatches && chgnet?.reference_available ? (
        <p className="boundary-note">The bundled result belongs to {chgnet.reference_material_id}. Run the scorecard to select that leader.</p>
      ) : null}
      {error ? <div className="eval-output fail"><span className="eval-label">Reference unavailable</span><span>{error}</span></div> : null}

      {reference ? (
        <div className="reference-result">
          <div className="status-pill-row">
            <span className="tag warn">cached reference</span>
            <span className="chip">{reference.model.name} {reference.model.version}</span>
            <span className="chip">{reference.result.steps} steps</span>
          </div>
          <div className="property-grid">
            <Metric label="Converged" value={reference.result.converged ? "yes" : "no"} />
            <Metric label="Energy / atom" value={`${formatNumber(reference.result.energy_per_atom, 5)} eV`} />
            <Metric label="Max force" value={`${formatNumber(reference.result.max_force, 4)} eV/Å`} />
            <Metric label="Volume Δ" value={`${formatNumber(reference.result.volume_change_percent, 3)}%`} />
            <Metric label="Lattice Δ" value={`${formatNumber(reference.result.lattice_change_percent, 3)}%`} />
            <Metric label="Weight checksum" value={reference.model.weight_checksum.slice(0, 16)} />
            <Metric label="Input checksum" value={reference.input_checksum.slice(0, 16)} />
          </div>
          <details className="artifact-details">
            <summary>Run parameters and compact trajectory</summary>
            <pre>{JSON.stringify({ run: reference.run, trajectory: reference.result.trajectory }, null, 2)}</pre>
          </details>
        </div>
      ) : null}

      <p className="ml-boundary">
        {chgnet?.scientific_boundary ?? "CHGNet relaxation is ML-based proposal support, not a DFT or experimental measurement."}
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="property-box"><span>{label}</span><strong>{value}</strong></div>;
}
