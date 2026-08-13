import { formatNumber } from "../lib/format";
import type { GraphSummary } from "../types/material";

type Props = {
  summary: GraphSummary | null;
  loading: boolean;
  error: string | null;
};

export function GraphSummaryPanel({ summary, loading, error }: Props) {
  if (loading) return <p className="empty-note">Building deterministic crystal graph…</p>;
  if (error) {
    return (
      <div className="eval-output warn">
        <span className="eval-label">Graph excluded</span>
        <span>{error}</span>
      </div>
    );
  }
  if (!summary) return <p className="empty-note">Select a structured material.</p>;

  const visibleEdges = uniqueCellEdges(summary).slice(0, 24);
  return (
    <div className="graph-layout">
      <div className="graph-canvas" aria-label={`${summary.formula} crystal graph preview`}>
        <svg viewBox="0 0 320 240" role="img">
          <title>{summary.formula} graph topology</title>
          {visibleEdges.map((edge) => {
            const source = summary.nodes[edge.source];
            const target = summary.nodes[edge.target];
            if (!source || !target) return null;
            const a = graphPoint(source.fractional_coordinates);
            const b = graphPoint(target.fractional_coordinates);
            return (
              <line
                key={`${edge.source}-${edge.target}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                className="graph-edge"
              />
            );
          })}
          {summary.nodes.map((node) => {
            const point = graphPoint(node.fractional_coordinates);
            return (
              <g key={node.index} transform={`translate(${point.x} ${point.y})`}>
                <circle r="18" className={`graph-node element-${node.species.toLowerCase()}`} />
                <text textAnchor="middle" dominantBaseline="central">
                  {node.species}
                </text>
              </g>
            );
          })}
        </svg>
        <p>Topology preview uses the real neighbor list; periodic image edges are counted below.</p>
      </div>
      <div className="property-grid graph-metrics">
        <Metric label="Atoms" value={summary.nodes.length} />
        <Metric label="Directed edges" value={summary.edge_count} />
        <Metric label="Node features" value={summary.node_feature_shape.join(" × ")} />
        <Metric label="Edge features" value={summary.edge_feature_shape.join(" × ")} />
        <Metric label="Space group" value={summary.global_features.spacegroup_number} />
        <Metric label="Density" value={`${formatNumber(summary.global_features.density_g_cm3)} g/cm³`} />
        <Metric label="Cutoff" value={`${summary.builder.cutoff} Å`} />
        <Metric label="Neighbor cap" value={summary.builder.max_neighbors} />
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

function uniqueCellEdges(summary: GraphSummary) {
  const seen = new Set<string>();
  return summary.edges.filter((edge) => {
    if (edge.source === edge.target || edge.image.some((value) => value !== 0)) return false;
    const key = [Math.min(edge.source, edge.target), Math.max(edge.source, edge.target)].join("-");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function graphPoint(coords: number[]) {
  const [x = 0, y = 0, z = 0] = coords;
  return {
    x: 38 + (x * 0.72 + z * 0.28) * 244,
    y: 30 + (y * 0.72 + (1 - z) * 0.28) * 176,
  };
}
