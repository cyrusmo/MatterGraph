import { formatUnknown } from "../lib/format";
import type { LeMaterialWorkflowSummary } from "../types/material";

type Props = {
  workflow: LeMaterialWorkflowSummary | null;
  loading: boolean;
  error: string | null;
};

const pipelineSteps = [
  "Ingest + normalize",
  "Slice + guardrails",
  "Graph export",
  "Benchmark frame",
  "Audited rank",
];

export function WorkflowSummaryPanel({ workflow, loading, error }: Props) {
  if (loading) {
    return (
      <div className="panel">
        <p className="empty-note">Loading LeMaterial demo workflow...</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="eval-output fail">
        <span className="eval-label">Workflow failed</span>
        <span>{error}</span>
      </div>
    );
  }
  if (!workflow) {
    return (
      <div className="panel">
        <p className="empty-note">Workflow summary unavailable.</p>
      </div>
    );
  }

  return (
    <>
      <div className="panel">
        <div className="panel-heading">
          <span>Pipeline</span>
          <span>A1</span>
        </div>
        <div className="pipeline">
          {pipelineSteps.map((step, index) => (
            <div className="pipeline-step" key={step}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{step}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="layout-two">
        <div className="panel">
          <div className="panel-heading">
            <span>Candidate slice</span>
            <span>B1</span>
          </div>
          <div className="property-grid">
            <div className="property-box wide">
              <span>Name</span>
              <strong>{workflow.candidate_slice.slice_name}</strong>
            </div>
            <div className="property-box">
              <span>Target</span>
              <strong>{workflow.candidate_slice.target}</strong>
            </div>
            <div className="property-box">
              <span>Rows kept</span>
              <strong>
                {workflow.candidate_slice.output_count} / {workflow.candidate_slice.input_count}
              </strong>
            </div>
          </div>
          <h3 className="subheading">Filter steps</h3>
          <div className="stack-list">
            {workflow.candidate_slice.filter_steps.map((step, index) => (
              <div className="stack-item" key={`${String(step.name)}-${index}`}>
                <strong>{String(step.name)}</strong>
                <p>
                  {String(step.input_count)} in, {String(step.output_count)} kept
                </p>
              </div>
            ))}
          </div>
          <h3 className="subheading">Guardrail report</h3>
          <div className="audit-grid">
            <div>
              <span>Deduplication</span>
              <strong>{String(workflow.candidate_slice.report.deduplication_basis)}</strong>
            </div>
            <div>
              <span>Mixed functionals</span>
              <strong>{workflow.candidate_slice.report.mixed_functionals ? "detected" : "none"}</strong>
            </div>
            <div>
              <span>Missing structures</span>
              <strong>{String(workflow.candidate_slice.report.missing_structure_count)}</strong>
            </div>
            <div>
              <span>Duplicate policy</span>
              <strong>{String(workflow.candidate_slice.report.duplicate_policy)}</strong>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <span>Provenance</span>
            <span>C1</span>
          </div>
          {/* kv-grid rather than property boxes: fixture_path and run_id are long
              free-text values that wrap badly in a fixed two-column grid. */}
          <div className="kv-grid">
            <span>Slice ID</span>
            <strong>{workflow.candidate_slice.slice_id}</strong>
            <span>Fixture</span>
            <strong>{workflow.provenance.fixture_path}</strong>
            <span>Loader</span>
            <strong>{workflow.provenance.loader}</strong>
            <span>Version</span>
            <strong>{workflow.provenance.workflow_version}</strong>
            <span>Run ID</span>
            <strong>{workflow.provenance.run_id}</strong>
            <span>License</span>
            <strong>{workflow.provenance.license}</strong>
            <span>Citation DOI</span>
            <strong>{workflow.provenance.citation_doi}</strong>
            <span>Dataset revision</span>
            <strong>{workflow.provenance.upstream_revision}</strong>
            <span>Hull revision</span>
            <strong>{workflow.provenance.hull_revision}</strong>
            <span>Snapshot SHA-256</span>
            <strong>{workflow.provenance.snapshot_sha256}</strong>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <span>Benchmark preview</span>
          <span>D1</span>
        </div>
        <table className="data-table compact-table">
          <thead>
            <tr>
              <th>Material</th>
              <th>Formula</th>
              <th>Target</th>
              <th>Density</th>
              <th>Energy above hull</th>
              <th>Max force</th>
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
                <td>{formatUnknown(row.max_force)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="boundary-note">
          {workflow.benchmark.row_count} rows are available in a benchmark-ready frame targeting{" "}
          {workflow.benchmark.target}. This table is a bounded preview, not a model result.
        </p>
      </div>
    </>
  );
}
