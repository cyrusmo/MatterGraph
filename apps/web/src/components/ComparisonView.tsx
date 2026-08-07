import { formatNumber } from "../lib/format";
import type { RankedRow } from "../types/material";

type Props = {
  rows: RankedRow[] | null;
  loading: boolean;
  error: string | null;
  eahMax: number;
  densityMax: number;
  poolSize: number;
};

export function ComparisonView({ rows, loading, error, eahMax, densityMax, poolSize }: Props) {
  if (loading) {
    return <p className="empty-note">Computing toy scorecard rank...</p>;
  }
  if (error) {
    return (
      <div className="eval-output fail">
        <span className="eval-label">Rank failed</span>
        <span>{error}</span>
      </div>
    );
  }
  if (rows === null) {
    return <p className="empty-note">Run the toy scorecard to rank demo candidates.</p>;
  }

  const verdict = rankVerdict(rows.length, poolSize);

  return (
    <div>
      <div className={`eval-output ${verdict.state}`}>
        <span className="eval-label">{verdict.label}</span>
        <span>{verdict.detail}</span>
      </div>

      <div className="status-pill-row">
        <span className="chip">energy_above_hull &lt;= {eahMax}</span>
        <span className="chip">density &lt;= {densityMax}</span>
      </div>

      {rows.length ? (
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
      ) : null}

      {rows.length > 0 && rows.length < 3 ? (
        <p className="boundary-note">
          Scores are pool-relative. With {rows.length} surviving candidate
          {rows.length === 1 ? "" : "s"}, min-max normalization is close to binary and the raw
          magnitudes stop separating them.
        </p>
      ) : null}
    </div>
  );
}

/**
 * The API applies the hard constraints before returning, so every row that arrives has
 * already passed. The honest signal is therefore how much of the pool survived, not a
 * per-row tag that would always read green.
 */
function rankVerdict(
  survivors: number,
  poolSize: number,
): { state: "pass" | "warn" | "fail"; label: string; detail: string } {
  if (survivors === 0) {
    return {
      state: "fail",
      label: "No candidates",
      detail: "Every demo candidate was removed by the active constraints. Loosen a limit to see a ranking.",
    };
  }
  if (poolSize > 0 && survivors < poolSize) {
    return {
      state: "warn",
      label: "Partial pool",
      detail: `${survivors} of ${poolSize} demo candidates satisfy the active constraints.`,
    };
  }
  return {
    state: "pass",
    label: "Full pool",
    detail: `All ${survivors} demo candidates satisfy the active constraints.`,
  };
}
