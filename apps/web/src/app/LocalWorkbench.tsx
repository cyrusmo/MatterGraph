import { Suspense, useEffect, useMemo, useState } from "react";

import { GraphSummaryPanel } from "../components/GraphSummaryPanel";
import { MaterialCard } from "../components/MaterialCard";
import { MaterialTable } from "../components/MaterialTable";
import {
  deleteDataset,
  exportDataset,
  fetchDatasets,
  fetchGraphSummary,
  fetchMaterials,
  fetchSlicePreview,
  importDataset,
  inspectDataset,
  rankDatasetAudit,
} from "../lib/api";
import type {
  DatasetEntry,
  DatasetImportMapping,
  DatasetList,
  GraphSummary,
  ImportReport,
  Material,
  PropertyColumnMapping,
  ScoreAudit,
  SlicePreview,
} from "../types/material";

type LocalFile = { filename: string; format: "csv" | "jsonl"; content: string };
type SwapState = "idle" | "loading" | "ready" | "failed";

export function LocalWorkbench({
  onReturnDemo,
}: {
  onReturnDemo: (screen?: number) => void;
}) {
  const [localFile, setLocalFile] = useState<LocalFile | null>(null);
  const [inspection, setInspection] = useState<ImportReport | null>(null);
  const [mapping, setMapping] = useState<DatasetImportMapping | null>(null);
  const [policy, setPolicy] = useState<"reject_file" | "skip_invalid_rows">("reject_file");
  const [registry, setRegistry] = useState<DatasetList | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [rows, setRows] = useState<Material[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [swapState, setSwapState] = useState<SwapState>("idle");
  const [status, setStatus] = useState("Choose a CSV or JSONL file to begin.");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [graph, setGraph] = useState<GraphSummary | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [slice, setSlice] = useState<SlicePreview | null>(null);
  const [sliceLoading, setSliceLoading] = useState(false);
  const [includeElements, setIncludeElements] = useState("");
  const [maxSites, setMaxSites] = useState(16);
  const [target, setTarget] = useState("");
  const [rankDirection, setRankDirection] = useState<"minimize" | "maximize">("minimize");
  const [audit, setAudit] = useState<ScoreAudit | null>(null);
  const [rankLoading, setRankLoading] = useState(false);

  useEffect(() => {
    void refreshRegistry();
  }, []);

  useEffect(() => {
    let current = true;
    if (!activeId || !selectedId || swapState === "loading") {
      setGraph(null);
      setGraphError(null);
      return;
    }
    setGraphLoading(true);
    setGraphError(null);
    fetchGraphSummary(selectedId, activeId)
      .then((summary) => { if (current) setGraph(summary); })
      .catch((nextError: unknown) => {
        if (!current) return;
        setGraph(null);
        setGraphError(messageOf(nextError));
      })
      .finally(() => { if (current) setGraphLoading(false); });
    return () => { current = false; };
  }, [activeId, selectedId, swapState]);

  const activeEntry = registry?.datasets.find(
    (entry) => entry.manifest.dataset_id === activeId,
  );
  const propertyNames = useMemo(
    () => [...new Set(rows.flatMap((row) => (row.properties ?? []).map((item) => item.name)))],
    [rows],
  );

  async function refreshRegistry() {
    try {
      setRegistry(await fetchDatasets());
    } catch (nextError) {
      setError(messageOf(nextError));
    }
  }

  async function handleFile(file: File | undefined) {
    setInspection(null);
    setMapping(null);
    setError(null);
    if (!file) return;
    const suffix = file.name.toLowerCase().split(".").pop();
    if (suffix !== "csv" && suffix !== "jsonl") {
      setLocalFile(null);
      setError("Only .csv and .jsonl files are accepted.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setLocalFile(null);
      setError("This file exceeds the 5 MiB local-import limit.");
      return;
    }
    const nextFile: LocalFile = {
      filename: file.name,
      format: suffix,
      content: await file.text(),
    };
    setLocalFile(nextFile);
    setStatus(`${file.name} selected. Inspect columns before importing.`);
  }

  async function inspect() {
    if (!localFile) return;
    setBusy(true);
    setError(null);
    try {
      const report = await inspectDataset(localFile);
      setInspection(report);
      setMapping(report.inferred_mapping ?? null);
      setStatus(`Inspected ${report.row_count.toLocaleString()} rows and ${report.columns.length} columns.`);
    } catch (nextError) {
      setError(messageOf(nextError));
      setStatus("Inspection failed. Correct the file and retry.");
    } finally {
      setBusy(false);
    }
  }

  async function runImport() {
    if (!localFile || !mapping) return;
    setBusy(true);
    setError(null);
    try {
      const result = await importDataset({
        ...localFile,
        mapping,
        error_policy: policy,
      });
      setStatus(
        `${result.accepted_count.toLocaleString()} records imported${
          result.manifest.degraded ? " with invalid rows skipped" : ""
        }.` ,
      );
      await refreshRegistry();
      await selectDataset(result.dataset_id);
    } catch (nextError) {
      setError(messageOf(nextError));
      setStatus("Import was rejected; no dataset was registered.");
    } finally {
      setBusy(false);
    }
  }

  async function selectDataset(datasetId: string) {
    setPendingId(datasetId);
    setSwapState("loading");
    setError(null);
    setStatus("Loading local dataset…");
    try {
      const nextRows = await fetchMaterials(datasetId);
      setRows(nextRows);
      setActiveId(datasetId);
      setSelectedId(String(nextRows[0]?.material_id ?? "") || null);
      setGraph(null);
      setSlice(null);
      setAudit(null);
      setSwapState("ready");
      setPendingId(null);
      setStatus(`${nextRows.length.toLocaleString()} local records ready.`);
      await refreshRegistry();
    } catch (nextError) {
      setSwapState("failed");
      setError(messageOf(nextError));
      setStatus("Dataset loading failed. The previous valid screen is still shown.");
      await refreshRegistry();
    }
  }

  async function resetLocal() {
    if (activeId) {
      try {
        await deleteDataset(activeId);
      } catch (nextError) {
        setError(messageOf(nextError));
        return;
      }
    }
    onReturnDemo(0);
  }

  async function previewSlice() {
    if (!activeId) return;
    setSliceLoading(true);
    setError(null);
    try {
      setSlice(await fetchSlicePreview(activeId, {
        include_elements: splitTokens(includeElements),
        exclude_elements: [],
        max_nsites: maxSites,
        ...(target ? { target } : {}),
      }));
      setStatus("Deterministic slice preview ready.");
    } catch (nextError) {
      setError(messageOf(nextError));
    } finally {
      setSliceLoading(false);
    }
  }

  async function rank() {
    if (!activeId || !target) return;
    setRankLoading(true);
    setError(null);
    try {
      setAudit(await rankDatasetAudit(
        activeId,
        { [target]: { direction: rankDirection, weight: 1 } },
      ));
      setStatus("Pool-relative audited ranking ready.");
    } catch (nextError) {
      setError(messageOf(nextError));
    } finally {
      setRankLoading(false);
    }
  }

  async function downloadExport() {
    if (!activeId || swapState === "loading") return;
    try {
      const blob = await exportDataset(activeId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${activeId}.jsonl`;
      anchor.click();
      URL.revokeObjectURL(url);
      setStatus("Normalized JSONL export prepared locally.");
    } catch (nextError) {
      setError(messageOf(nextError));
    }
  }

  const swapping = swapState === "loading";
  return (
    <div className="shell workbench-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="dot" />
          <span className="brand">MatterGraph</span>
          <span className="mode">local contributor workbench</span>
        </div>
        <div className="topbar-actions">
          <span>offline · ephemeral · 5 MiB / 5,000 rows</span>
          <button className="text-button" type="button" onClick={() => onReturnDemo(0)}>Guided demo</button>
          <button className="text-button" type="button" onClick={() => void resetLocal()}>Reset local dataset</button>
        </div>
      </header>

      <main className="workbench-grid">
        <aside className="rail workbench-rail">
          <div className="rail-inner">
            <div className="rail-section">
              <div className="rail-title">Registry</div>
              <span className="rail-kv"><span>Entries</span><strong>{registry?.registry.entry_count ?? "—"} / 8</strong></span>
              <span className="rail-kv"><span>Serialized bytes</span><strong>{formatBytes(registry?.registry.normalized_bytes ?? 0)} / 32 MiB</strong></span>
              <span className="rail-kv"><span>Memory rule</span><strong>one active store</strong></span>
            </div>
            <nav className="rail-section rail-nav" aria-label="Local datasets">
              <div className="rail-title">Ephemeral datasets</div>
              {registry?.datasets.length ? registry.datasets.map((entry) => (
                <DatasetButton
                  entry={entry}
                  active={entry.manifest.dataset_id === activeId}
                  disabled={swapping}
                  key={entry.manifest.dataset_id}
                  onClick={() => void selectDataset(entry.manifest.dataset_id)}
                />
              )) : <p className="empty-note">No imported datasets.</p>}
            </nav>
            <div className="rail-section boundary-note">
              Files remain in this process only. MatterGraph does not upload or persist imported content.
            </div>
          </div>
        </aside>

        <section className="workspace workbench-workspace" aria-busy={swapping}>
          <div className="workspace-header">
            <p className="eyebrow">Public mode · contributor extension surface</p>
            <h1>Inspect local materials data without implying qualification.</h1>
            <p className="subhead">Map fields, preserve provenance, inspect graph readiness, audit a baseline rank, and export reproducible JSONL.</p>
          </div>

          <div className={`swap-status ${swapState}`} aria-live="polite">
            {swapping ? <span className="spinner" aria-hidden="true" /> : null}
            <span>{status}</span>
            {swapState === "failed" && pendingId ? (
              <button className="text-button" type="button" onClick={() => void selectDataset(pendingId)}>Retry</button>
            ) : null}
          </div>
          {error ? <div className="api-offline" role="alert"><div><span className="eval-label">Workbench notice</span><p>{error}</p></div></div> : null}

          <section className="panel workbench-import" aria-labelledby="import-title">
            <div className="panel-heading"><span id="import-title">1–5 · Inspect and import</span><span>local only</span></div>
            <div className="import-grid">
              <label className="file-drop">
                <span>Select CSV or JSONL</span>
                <input
                  data-testid="local-file-input"
                  type="file"
                  accept=".csv,.jsonl,text/csv,application/x-ndjson"
                  onChange={(event) => void handleFile(event.target.files?.[0])}
                />
                <small>{localFile ? `${localFile.filename} · ${formatBytes(localFile.content.length)}` : "5 MiB and 5,000 rows maximum"}</small>
              </label>
              <button className="primary-button" type="button" disabled={!localFile || busy} onClick={() => void inspect()}>
                {busy && !inspection ? "Inspecting…" : "Inspect columns"}
              </button>
            </div>

            {inspection && mapping ? (
              <div className="mapping-editor">
                <div className="status-strip compact-status">
                  <Status label="Rows" value={inspection.row_count} />
                  <Status label="Columns" value={inspection.columns.length} />
                  <Status label="Checksum" value={inspection.checksum.slice(0, 12)} />
                  <Status label="Issues shown" value={inspection.issues.length} />
                </div>
                <div className="control-grid">
                  <ColumnSelect label="Identity" value={mapping.identity_column} columns={inspection.columns} onChange={(value) => setMapping({ ...mapping, identity_column: value })} />
                  <ColumnSelect label="Formula" value={mapping.formula_column} columns={inspection.columns} onChange={(value) => setMapping({ ...mapping, formula_column: value })} />
                  <ColumnSelect label="Structure" value={mapping.structure_column ?? ""} columns={inspection.columns} optional onChange={(value) => setMapping({ ...mapping, structure_column: value || null })} />
                  <ColumnSelect label="Source ID" value={mapping.source_id_column ?? ""} columns={inspection.columns} optional onChange={(value) => setMapping({ ...mapping, source_id_column: value || null })} />
                </div>
                <PropertyMappings mappings={mapping.property_columns} onChange={(property_columns) => setMapping({ ...mapping, property_columns })} />
                <div className="import-policy">
                  <label><input type="radio" checked={policy === "reject_file"} onChange={() => setPolicy("reject_file")} /> Strict rejection</label>
                  <label><input type="radio" checked={policy === "skip_invalid_rows"} onChange={() => setPolicy("skip_invalid_rows")} /> Skip invalid rows <span className="tag warn">degraded</span></label>
                </div>
                <IssueList report={inspection} />
                <button className="primary-button" type="button" disabled={busy || inspection.status === "invalid"} onClick={() => void runImport()}>
                  {busy ? "Importing…" : "Import ephemeral dataset"}
                </button>
              </div>
            ) : null}
          </section>

          {rows.length && activeId ? (
            <div className={`active-dataset${swapping ? " is-swapping" : ""}`}>
              {swapping ? <div className="dataset-skeleton" aria-hidden="true"><span /><span /><span /></div> : null}
              <div className="status-strip">
                <Status label="Dataset" value={activeEntry?.manifest.name ?? activeId} />
                <Status label="Records" value={rows.length} />
                <Status label="Normalized" value={formatBytes(activeEntry?.normalized_bytes ?? 0)} />
                <Status label="Integrity" value={activeEntry?.manifest.normalized_sha256.slice(0, 12) ?? "—"} />
                <Status label="State" value={activeEntry?.manifest.degraded ? "degraded" : "strict"} />
                <Status label="Persistence" value="none" />
              </div>

              <div className="layout-two workbench-section">
                <div className="panel"><div className="panel-heading"><span>6 · Materials</span><span>{rows.length}</span></div><MaterialTable materials={rows} selectedId={selectedId} onSelect={setSelectedId} eahMax={Number.POSITIVE_INFINITY} forceMax={Number.POSITIVE_INFINITY} /></div>
                <div className="panel"><div className="panel-heading"><span>Provenance-aware record</span><span>selected</span></div><MaterialCard m={rows.find((row) => row.material_id === selectedId)} /></div>
              </div>

              <section className="panel workbench-section">
                <div className="panel-heading"><span>Graph readiness</span><span>periodic · bounded payload</span></div>
                <Suspense fallback={<p className="empty-note">Loading crystal viewer…</p>}>
                  <GraphSummaryPanel summary={graph} loading={graphLoading} error={graphError} />
                </Suspense>
              </section>

              <div className="layout-two workbench-section">
                <section className="panel">
                  <div className="panel-heading"><span>Slice preview</span><span>guardrailed</span></div>
                  <div className="control-grid">
                    <label>Allowed elements<input value={includeElements} placeholder="Al, N, Ti" onChange={(event) => setIncludeElements(event.target.value)} /></label>
                    <label>Maximum sites<input type="number" min="1" value={maxSites} onChange={(event) => setMaxSites(Number(event.target.value))} /></label>
                  </div>
                  <label>Optional target<select value={target} onChange={(event) => setTarget(event.target.value)}><option value="">No target</option>{propertyNames.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
                  <button className="primary-button" type="button" disabled={swapping || sliceLoading} onClick={() => void previewSlice()}>{sliceLoading ? "Slicing…" : "Create deterministic preview"}</button>
                  {slice ? <div className="audit-grid"><Summary label="Output" value={slice.material_ids.length} /><Summary label="Graph ready" value={slice.graph_readiness.included_count} /><Summary label="Graph excluded" value={slice.graph_readiness.excluded_count} /><Summary label="Slice ID" value={String(slice.slice.slice_id ?? "—")} /></div> : null}
                </section>
                <section className="panel">
                  <div className="panel-heading"><span>Audited baseline</span><span>pool-relative</span></div>
                  <label>Objective<select value={target} onChange={(event) => setTarget(event.target.value)}><option value="">Choose a property</option>{propertyNames.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
                  <label>Direction<select value={rankDirection} onChange={(event) => setRankDirection(event.target.value as typeof rankDirection)}><option value="minimize">Minimize</option><option value="maximize">Maximize</option></select></label>
                  <button className="primary-button" type="button" disabled={swapping || rankLoading || !target} onClick={() => void rank()}>{rankLoading ? "Ranking…" : "Run transparent scorecard"}</button>
                  <GenericRanking audit={audit} objective={target} onSelect={setSelectedId} />
                </section>
              </div>

              <section className="panel workbench-section fixture-boundary">
                <div><span className="tag warn">Fixture-only</span><h2>Bundled AlN reference not applicable</h2><p>The cached artifact was generated only for bundled material <code>agm003273599</code>. MatterGraph did not run a model on this imported dataset.</p></div>
                <button className="text-button" type="button" onClick={() => onReturnDemo(4)}>Return to bundled AlN evidence</button>
              </section>

              <div className="workbench-actions">
                <button className="primary-button" type="button" disabled={swapping} onClick={() => void downloadExport()}>Export normalized JSONL</button>
                <span>Checksum and manifest headers are included in the response.</span>
              </div>
            </div>
          ) : null}
        </section>
      </main>
    </div>
  );
}

function DatasetButton({
  entry,
  active,
  disabled,
  onClick,
}: {
  entry: DatasetEntry;
  active: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button className="nav-item dataset-nav" aria-current={active ? "true" : undefined} type="button" disabled={disabled} onClick={onClick}>
      <strong>{entry.manifest.name}</strong>
      <small>{entry.manifest.record_count} rows · {formatBytes(entry.normalized_bytes)}</small>
    </button>
  );
}

function ColumnSelect({
  label,
  value,
  columns,
  optional = false,
  onChange,
}: {
  label: string;
  value: string;
  columns: string[];
  optional?: boolean;
  onChange: (value: string) => void;
}) {
  return <label>{label}<select value={value} onChange={(event) => onChange(event.target.value)}>{optional ? <option value="">Not mapped</option> : null}{columns.map((column) => <option key={column} value={column}>{column}</option>)}</select></label>;
}

function PropertyMappings({
  mappings,
  onChange,
}: {
  mappings: PropertyColumnMapping[];
  onChange: (mappings: PropertyColumnMapping[]) => void;
}) {
  if (!mappings.length) return <p className="empty-note">Properties are already represented in normalized JSONL records.</p>;
  return (
    <div className="mapping-table-wrap">
      <table className="data-table compact-table">
        <thead><tr><th>Input</th><th>Property name</th><th>Unit</th><th>Source</th><th>Method</th></tr></thead>
        <tbody>{mappings.map((mapping, index) => (
          <tr key={mapping.column}>
            <td>{mapping.column}</td>
            <td><input value={mapping.name} onChange={(event) => onChange(updateMapping(mappings, index, { name: event.target.value }))} /></td>
            <td><input value={mapping.unit ?? ""} placeholder="optional" onChange={(event) => onChange(updateMapping(mappings, index, { unit: event.target.value || null }))} /></td>
            <td><input value={mapping.source} onChange={(event) => onChange(updateMapping(mappings, index, { source: event.target.value }))} /></td>
            <td><select value={mapping.method} onChange={(event) => onChange(updateMapping(mappings, index, { method: event.target.value as PropertyColumnMapping["method"] }))}><option value="unknown">Unknown</option><option value="dft">DFT</option><option value="experimental">Experimental</option><option value="model_predicted">Model predicted</option><option value="derived">Derived</option></select></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function IssueList({ report }: { report: ImportReport }) {
  if (!report.issues.length) return <div className="eval-output pass"><span className="eval-label">Inspection</span><span>No parse or mapping issues detected. Row-level validation runs on import.</span></div>;
  return <div className={`eval-output ${report.status === "invalid" ? "fail" : "warn"}`}><span className="eval-label">Inspection issues</span><ul>{report.issues.map((issue, index) => <li key={`${issue.code}-${index}`}>{issue.code}{issue.row ? ` · row ${issue.row}` : ""}: {issue.message}</li>)}</ul>{report.truncated_issue_count ? <span>+ {report.truncated_issue_count} additional issues</span> : null}</div>;
}

function GenericRanking({ audit, objective, onSelect }: { audit: ScoreAudit | null; objective: string; onSelect: (id: string) => void }) {
  if (!audit) return <p className="empty-note">Choose a numeric property to inspect a baseline rank and its coverage report.</p>;
  return (
    <div className="ranking-compact">
      <p className="boundary-note">Scores are pool-relative and are not production decision logic. {audit.report.ranked_count} of {audit.report.pool_size} records ranked.</p>
      <table className="data-table compact-table"><thead><tr><th>Rank</th><th>Material</th><th>{objective}</th><th>Score</th></tr></thead><tbody>{audit.ranked.slice(0, 20).map((row, index) => <tr key={String(row.material_id)}><td>{index + 1}</td><td><button className="row-select" type="button" onClick={() => onSelect(String(row.material_id))}>{String(row.material_id)}</button></td><td>{String(row[objective] ?? "—")}</td><td>{typeof row.score === "number" ? row.score.toFixed(3) : "—"}</td></tr>)}</tbody></table>
    </div>
  );
}

function Status({ label, value }: { label: string; value: string | number }) {
  return <div><span className="metric-label">{label}</span><strong>{value}</strong></div>;
}

function Summary({ label, value }: { label: string; value: string | number }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function updateMapping(
  mappings: PropertyColumnMapping[],
  index: number,
  update: Partial<PropertyColumnMapping>,
) {
  return mappings.map((mapping, candidate) => candidate === index ? { ...mapping, ...update } : mapping);
}

function splitTokens(value: string): string[] {
  return value.split(/[ ,]+/).map((item) => item.trim()).filter(Boolean);
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
