import type { LeMaterialWorkflowSummary } from "../types/material";

type Props = {
  workflow: LeMaterialWorkflowSummary | null;
  loading: boolean;
  error: string | null;
};

const pipelineSteps = [
  "Fixture",
  "LeMatBulk loader",
  "Candidate slice",
  "Graph export",
  "Benchmark preview",
];

export function WorkflowSummaryPanel({ workflow, loading, error }: Props) {
  if (loading) {
    return <div className="empty-note">Loading LeMaterial demo workflow...</div>;
  }
  if (error) {
    return <div className="error-note">{error}</div>;
  }
  if (!workflow) {
    return <div className="empty-note">Workflow summary unavailable.</div>;
  }

  const schema = workflow.schema_report;

  return (
    <div className="workflow-summary">
      <div className="pipeline">
        {pipelineSteps.map((step, index) => (
          <div className="pipeline-step" key={step}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{step}</strong>
          </div>
        ))}
      </div>

      <div className="summary-grid">
        <Metric label="Rows" value={schema.row_count} />
        <Metric label="Missing structures" value={schema.missing_structure_count} />
        <Metric label="Graph included" value={workflow.graph_export.included_count} />
        <Metric label="Graph excluded" value={workflow.graph_export.excluded_count} />
      </div>

      <div className="layout-two">
        <section>
          <h3>Candidate slice</h3>
          <div className="kv-grid">
            <span>Slice ID</span>
            <strong>{workflow.candidate_slice.slice_id}</strong>
            <span>Name</span>
            <strong>{workflow.candidate_slice.slice_name}</strong>
            <span>Target</span>
            <strong>{workflow.candidate_slice.target}</strong>
            <span>Rows</span>
            <strong>
              {workflow.candidate_slice.output_count} / {workflow.candidate_slice.input_count}
            </strong>
          </div>
          <ol className="step-list">
            {workflow.candidate_slice.filter_steps.map((step, index) => (
              <li key={`${String(step.name)}-${index}`}>
                <strong>{String(step.name)}</strong>{" "}
                <span>
                  {String(step.input_count)} -&gt; {String(step.output_count)}
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section>
          <h3>Provenance</h3>
          <div className="kv-grid">
            <span>Fixture</span>
            <strong>{workflow.provenance.fixture_path}</strong>
            <span>Loader</span>
            <strong>{workflow.provenance.loader}</strong>
            <span>Version</span>
            <strong>{workflow.provenance.workflow_version}</strong>
            <span>Run ID</span>
            <strong>{workflow.provenance.run_id}</strong>
          </div>
        </section>
      </div>

      <h3>Benchmark preview</h3>
      <table className="data-table compact-table">
        <thead>
          <tr>
            <th>Material</th>
            <th>Formula</th>
            <th>Target</th>
            <th>Density</th>
            <th>Energy above hull</th>
          </tr>
        </thead>
        <tbody>
          {workflow.benchmark_preview.map((row) => (
            <tr key={row.material_id}>
              <td>{row.material_id}</td>
              <td>{row.formula}</td>
              <td>{formatUnknown(row.target)}</td>
              <td>{formatUnknown(row.density)}</td>
              <td>{formatUnknown(row.energy_above_hull)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <span className="metric-label">{label}</span>
      <strong>{formatUnknown(value)}</strong>
    </div>
  );
}

function formatUnknown(value: unknown): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  }
  return String(value);
}
