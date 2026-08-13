import { formatNumber } from "../lib/format";
import type { GraphSummary } from "../types/material";
import { CrystalViewer } from "./CrystalViewer";

type Props = {
  summary: GraphSummary | null;
  loading: boolean;
  error: string | null;
};

export function GraphSummaryPanel({ summary, loading, error }: Props) {
  if (loading) return <p className="empty-note">Building reciprocal periodic graph…</p>;
  if (error) {
    return (
      <div className="eval-output warn">
        <span className="eval-label">Graph excluded</span>
        <span>{error}</span>
      </div>
    );
  }
  if (!summary) return <p className="empty-note">Select a reconstructed structure.</p>;

  return (
    <div className="graph-layout">
      <CrystalViewer summary={summary} />
      <div className="graph-evidence">
        <div className={`eval-output ${summary.validation.state === "valid" ? "pass" : "fail"}`}>
          <span className="eval-label">Graph validation</span>
          <strong>{summary.validation.state}</strong>
          <span>
            reciprocal · no zero-distance edges · Cartesian displacement checked
          </span>
        </div>
        <div className="property-grid graph-metrics">
          <Metric label="Atoms" value={summary.nodes.length} />
          <Metric label="Directed edges" value={summary.edge_count} />
          <Metric label="First-shell CN" value={coordinationLabel(summary.coordination_numbers)} />
          <Metric label="Distance shells" value={summary.distance_shells.length} />
          <Metric label="Node shape" value={summary.node_feature_shape.join(" × ")} />
          <Metric label="Edge shape" value={summary.edge_feature_shape.join(" × ")} />
          <Metric label="Space group" value={summary.global_features.spacegroup_number} />
          <Metric label="Density" value={`${formatNumber(summary.global_features.density_g_cm3)} g/cm³`} />
          <Metric label="Cutoff" value={`${summary.builder.cutoff} Å`} />
          <Metric label="Soft target" value={summary.builder.max_neighbors} />
        </div>
        <p className="boundary-note">
          Exact periodic offsets and Cartesian endpoints drive the rendering. The 12-neighbor
          target expands to keep tied distance shells complete; reverse edges are guaranteed.
        </p>
        {summary.validation.warnings.length ? (
          <ul className="warning-list">
            {summary.validation.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="property-box">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function coordinationLabel(values: number[]) {
  const unique = [...new Set(values)].sort((a, b) => a - b);
  return unique.join(" / ") || "0";
}
