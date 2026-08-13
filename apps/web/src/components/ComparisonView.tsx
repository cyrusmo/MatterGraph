import { formatNumber } from "../lib/format";
import type { ScoreAudit } from "../types/material";

type Props = {
  audit: ScoreAudit | null;
  loading: boolean;
  error: string | null;
  eahMax: number;
  densityMax: number;
  onSelect: (materialId: string) => void;
};

export function ComparisonView({
  audit,
  loading,
  error,
  eahMax,
  densityMax,
  onSelect,
}: Props) {
  if (loading) return <p className="empty-note">Computing rank and audit report…</p>;
  if (error) {
    return (
      <div className="eval-output fail">
        <span className="eval-label">Rank failed</span>
        <span>{error}</span>
      </div>
    );
  }
  if (!audit) {
    return <p className="empty-note">Run the transparent baseline to rank this fixture.</p>;
  }

  const report = audit.report;
  return (
    <div>
      <div className={`eval-output ${report.excluded_by_constraints ? "warn" : "pass"}`}>
        <span className="eval-label">Audit result</span>
        <span>
          {report.ranked_count} of {report.pool_size} candidates ranked; {report.excluded_by_constraints}{" "}
          removed by hard constraints.
        </span>
      </div>
      <div className="status-pill-row">
        <span className="chip">hull ≤ {eahMax}</span>
        <span className="chip">density ≤ {densityMax}</span>
        <span className="chip">missing: {report.missing_policy}</span>
        <span className={`tag ${report.binary_normalization ? "warn" : "pass"}`}>
          {report.binary_normalization ? "binary normalization" : "multi-point normalization"}
        </span>
      </div>

      {audit.ranked.length ? (
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
            {audit.ranked.map((row, index) => (
              <tr key={String(row.material_id)} className="selectable-row">
                <td>{index + 1}</td>
                <td>
                  <button
                    className="row-select"
                    type="button"
                    onClick={() => onSelect(String(row.material_id))}
                  >
                    {String(row.material_id)}
                  </button>
                </td>
                <td>{formatNumber(row.score)}</td>
                <td>{formatNumber(row.density)}</td>
                <td>{formatNumber(row.bulk_modulus)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      <div className="audit-grid">
        <div>
          <span>Coverage</span>
          <strong>
            {Object.entries(report.coverage)
              .map(([key, count]) => `${key} ${count}/${report.ranked_count}`)
              .join(" · ")}
          </strong>
        </div>
        <div>
          <span>Effective objectives</span>
          <strong>{report.effective_objectives.join(" · ") || "none"}</strong>
        </div>
        <div>
          <span>Mixed methods</span>
          <strong>{Object.keys(report.mixed_methods).join(" · ") || "none detected"}</strong>
        </div>
        <div>
          <span>Ignored objectives</span>
          <strong>{report.ignored_objectives.join(" · ") || "none"}</strong>
        </div>
      </div>
      <p className="boundary-note">
        Scores are pool-relative min–max baselines. Read the rank, raw values, coverage, and
        method checks together; the absolute score is not portable to another pool.
      </p>
    </div>
  );
}
