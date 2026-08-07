import { useEffect, useState } from "react";

import { ComparisonView } from "../components/ComparisonView";
import { ConstraintPanel } from "../components/ConstraintPanel";
import { MaterialCard } from "../components/MaterialCard";
import { MaterialTable } from "../components/MaterialTable";
import { SimulationQueue } from "../components/SimulationQueue";
import { WorkflowSummaryPanel } from "../components/WorkflowSummaryPanel";
import { fetchLeMaterialWorkflow, fetchMaterials, rankMaterials } from "../lib/api";
import { formatUnknown } from "../lib/format";
import type { LeMaterialWorkflowSummary, Material, RankedRow } from "../types/material";
import { useSectionSpy } from "./useSectionSpy";

const SECTIONS = [
  { id: "workflow", index: "01", label: "Workflow" },
  { id: "records", index: "02", label: "Records" },
  { id: "scorecard", index: "03", label: "Scorecard" },
  { id: "simulation", index: "04", label: "Simulation" },
] as const;

const SECTION_IDS = SECTIONS.map((section) => section.id);

export function App() {
  const [rows, setRows] = useState<Material[]>([]);
  const [materialsErr, setMaterialsErr] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [workflow, setWorkflow] = useState<LeMaterialWorkflowSummary | null>(null);
  const [workflowErr, setWorkflowErr] = useState<string | null>(null);
  const [workflowLoading, setWorkflowLoading] = useState(true);
  const [eaMax, setEaMax] = useState(0.05);
  const [dMax, setDMax] = useState(6.0);
  const [ranked, setRanked] = useState<RankedRow[] | null>(null);
  const [rankLoading, setRankLoading] = useState(false);
  const [rankErr, setRankErr] = useState<string | null>(null);

  const activeSection = useSectionSpy(SECTION_IDS);

  useEffect(() => {
    (async () => {
      try {
        const materials = await fetchMaterials();
        setRows(materials);
        setSelectedId((current) => current ?? preferredMaterialId(materials));
      } catch (e) {
        setMaterialsErr(String(e));
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setWorkflowLoading(true);
      try {
        setWorkflow(await fetchLeMaterialWorkflow());
      } catch (e) {
        setWorkflowErr(String(e));
      } finally {
        setWorkflowLoading(false);
      }
    })();
  }, []);

  const selectedMaterial = rows.find((row) => row.material_id === selectedId) ?? rows[0];
  const schema = workflow?.schema_report;
  const apiFailed = Boolean(materialsErr || workflowErr);
  const apiPending = workflowLoading && !apiFailed;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="dot"></span>
          <span className="brand">MatterGraph</span>
          <span className="mode">public demo workbench</span>
        </div>
        <span>v0.1 local fixture mode</span>
      </header>

      <main className="os-grid">
        <aside className="rail">
          <div className="rail-inner">
            <div className="rail-section">
              <div className="rail-title">Demo source</div>
              {workflow ? (
                <>
                  <span className="rail-kv">
                    <span>Fixture</span>
                    <strong>{workflow.provenance.fixture_path}</strong>
                  </span>
                  <span className="rail-kv">
                    <span>Loader</span>
                    <strong>{workflow.provenance.loader}</strong>
                  </span>
                  <span className="rail-kv">
                    <span>Version</span>
                    <strong>{workflow.provenance.workflow_version}</strong>
                  </span>
                  <span className="rail-kv">
                    <span>Run ID</span>
                    <strong>{workflow.provenance.run_id}</strong>
                  </span>
                </>
              ) : (
                <p className="empty-note">
                  {apiFailed ? "Source unavailable." : "Loading fixture provenance..."}
                </p>
              )}
            </div>

            <div className="rail-section">
              <div className="rail-title">Sections</div>
              <div className="rail-nav">
                {SECTIONS.map((section) => (
                  <button
                    key={section.id}
                    className="nav-item"
                    type="button"
                    aria-current={activeSection === section.id ? "true" : undefined}
                    onClick={() =>
                      document.getElementById(section.id)?.scrollIntoView({ block: "start" })
                    }
                  >
                    {section.index} {section.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="rail-section">
              <div className="rail-title">API status</div>
              <span className={`tag ${apiFailed ? "fail" : apiPending ? "warn" : "pass"}`}>
                {apiFailed ? "unreachable" : apiPending ? "checking" : "reachable"}
              </span>
            </div>
          </div>
        </aside>

        <section className="workspace">
          <div className="workspace-header">
            <p className="eyebrow">transparent materials workflow</p>
            <h1>Demo workbench</h1>
            <p className="subhead">
              Inspect demo records, run a toy scorecard, review a LeMaterial demo workflow summary,
              and trigger an ASE demo relaxation.
            </p>
          </div>

          <div className="status-strip">
            <div>
              <span className="metric-label">Demo records</span>
              <strong>{rows.length}</strong>
            </div>
            <div>
              <span className="metric-label">LeMat rows</span>
              <strong>{formatUnknown(schema?.row_count)}</strong>
            </div>
            <div>
              <span className="metric-label">Missing structures</span>
              <strong>{formatUnknown(schema?.missing_structure_count)}</strong>
            </div>
            <div>
              <span className="metric-label">Graph included</span>
              <strong>{formatUnknown(workflow?.graph_export.included_count)}</strong>
            </div>
            <div>
              <span className="metric-label">Graph excluded</span>
              <strong>{formatUnknown(workflow?.graph_export.excluded_count)}</strong>
            </div>
            <div>
              <span className="metric-label">Ranked</span>
              <strong>{ranked === null ? "not run" : `${ranked.length} rows`}</strong>
            </div>
          </div>

          <section className="section-block" id="workflow">
            <div className="sheet-header">
              <span>01 — Workflow</span>
              <span>Section 01 / 04</span>
            </div>
            <WorkflowSummaryPanel
              workflow={workflow}
              loading={workflowLoading}
              error={workflowErr}
            />
          </section>

          <section className="section-block" id="records">
            <div className="sheet-header">
              <span>02 — Records</span>
              <span>Section 02 / 04</span>
            </div>
            <div className="layout-two">
              <div className="panel">
                <div className="panel-heading">
                  <span>Demo records</span>
                  <span>E2</span>
                </div>
                {materialsErr && (
                  <div className="eval-output fail">
                    <span className="eval-label">Load failed</span>
                    <span>{materialsErr}</span>
                  </div>
                )}
                <MaterialTable
                  materials={rows}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  eahMax={eaMax}
                  densityMax={dMax}
                />
              </div>
              <div className="panel">
                <div className="panel-heading">
                  <span>Material inspector</span>
                  <span>F2</span>
                </div>
                <MaterialCard m={selectedMaterial} />
              </div>
            </div>
          </section>

          <section className="section-block" id="scorecard">
            <div className="sheet-header">
              <span>03 — Scorecard</span>
              <span>Section 03 / 04</span>
            </div>
            <div className="layout-two">
              <div className="panel">
                <div className="panel-heading">
                  <span>Objectives + constraints</span>
                  <span>G3</span>
                </div>
                <ConstraintPanel
                  eahMax={eaMax}
                  onEah={setEaMax}
                  dMax={dMax}
                  onD={setDMax}
                  loading={rankLoading}
                  onRank={async (objectives) => {
                    setRankLoading(true);
                    setRankErr(null);
                    setRanked(null);
                    try {
                      setRanked(await rankMaterials(objectives, eaMax, dMax));
                    } catch (e) {
                      setRankErr(String(e));
                    } finally {
                      setRankLoading(false);
                    }
                  }}
                />
              </div>
              <div className="panel">
                <div className="panel-heading">
                  <span>Ranked candidates</span>
                  <span>H3</span>
                </div>
                <ComparisonView
                  rows={ranked}
                  loading={rankLoading}
                  error={rankErr}
                  eahMax={eaMax}
                  densityMax={dMax}
                  poolSize={rows.length}
                />
              </div>
            </div>
          </section>

          <section className="section-block" id="simulation">
            <div className="sheet-header">
              <span>04 — Simulation</span>
              <span>Section 04 / 04</span>
            </div>
            <div className="panel">
              <div className="panel-heading">
                <span>ASE demo relaxation</span>
                <span>I4</span>
              </div>
              <SimulationQueue
                materialId={String(selectedMaterial?.material_id ?? "")}
                formula={selectedMaterial?.formula}
              />
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}

function preferredMaterialId(materials: Material[]): string | null {
  const preferred = materials.find((material) => material.material_id === "demo-al-fcc-1");
  return String(preferred?.material_id ?? materials[0]?.material_id ?? "") || null;
}
