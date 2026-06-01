import type { RankedRow } from "../types/material";

type Props = {
  rows: RankedRow[] | null;
  loading: boolean;
  error: string | null;
  eahMax: number;
  densityMax: number;
};

export function ComparisonView({ rows, loading, error, eahMax, densityMax }: Props) {
  if (loading) {
    return <div className="empty-note">Computing toy scorecard rank...</div>;
  }
  if (error) {
    return <div className="error-note">{error}</div>;
  }
  if (rows === null) {
    return <div className="empty-note">Run the toy scorecard to rank demo candidates.</div>;
  }
  if (!rows.length) {
    return <div className="empty-note">No ranked candidates matched the active constraints.</div>;
  }

  return (
    <div className="rank-results">
      <div className="constraint-strip">
        <span>energy_above_hull {"<="} {eahMax}</span>
        <span>density {"<="} {densityMax}</span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Material</th>
            <th>Score</th>
            <th>Density</th>
            <th>Bulk modulus</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={String(row.material_id)}>
              <td>{index + 1}</td>
              <td>{String(row.material_id)}</td>
              <td>{formatNumber(row.score)}</td>
              <td>{formatNumber(row.density)}</td>
              <td>{formatNumber(row.bulk_modulus)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatNumber(value: unknown): string {
  return typeof value === "number" ? value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "") : "n/a";
}
