import { useEffect, useState } from "react";

import { CapabilityLedger } from "../components/CapabilityLedger";
import { ComparisonView } from "../components/ComparisonView";
import { ConstraintPanel } from "../components/ConstraintPanel";
import { GraphSummaryPanel } from "../components/GraphSummaryPanel";
import { MaterialCard } from "../components/MaterialCard";
import { MaterialTable } from "../components/MaterialTable";
import { SimulationQueue } from "../components/SimulationQueue";
import { WorkflowSummaryPanel } from "../components/WorkflowSummaryPanel";
import {
  fetchCapabilities,
  fetchGraphSummary,
  fetchLeMaterialWorkflow,
  fetchMaterials,
  fetchPreflight,
  rankMaterialsAudit,
} from "../lib/api";
import type {
  Capability,
  DemoPreflight,
  GraphSummary,
  LeMaterialWorkflowSummary,
  Material,
  ScoreAudit,
} from "../types/material";
import { useSectionSpy } from "./useSectionSpy";

const SECTIONS = [
  { id: "source", index: "01", label: "Source" },
  { id: "slice", index: "02", label: "Slice" },
  { id: "graph", index: "03", label: "Graph" },
  { id: "rank", index: "04", label: "Rank" },
  { id: "simulation", index: "05", label: "Simulate" },
] as const;

const SECTION_IDS = SECTIONS.map((section) => section.id);
const DEFAULT_EAH_MAX = 0.025;
const DEFAULT_DENSITY_MAX = 6;
const DEFAULT_DENSITY_WEIGHT = 0.6;
const DEFAULT_BULK_WEIGHT = 0.4;

type ApiState = "loading" | "ready" | "degraded" | "offline";

export function App() {
  const [rows, setRows] = useState<Material[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [workflow, setWorkflow] = useState<LeMaterialWorkflowSummary | null>(null);
  const [preflight, setPreflight] = useState<DemoPreflight | null>(null);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [apiState, setApiState] = useState<ApiState>("loading");
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [graph, setGraph] = useState<GraphSummary | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [eaMax, setEaMax] = useState(DEFAULT_EAH_MAX);
  const [dMax, setDMax] = useState(DEFAULT_DENSITY_MAX);
  const [densityWeight, setDensityWeight] = useState(DEFAULT_DENSITY_WEIGHT);
  const [bulkWeight, setBulkWeight] = useState(DEFAULT_BULK_WEIGHT);
  const [missing, setMissing] = useState<"worst" | "neutral" | "exclude">("worst");
  const [audit, setAudit] = useState<ScoreAudit | null>(null);
  const [rankLoading, setRankLoading] = useState(false);
  const [rankError, setRankError] = useState<string | null>(null);

  const activeSection = useSectionSpy(SECTION_IDS);

  useEffect(() => {
    let active = true;
    setApiState("loading");
    setBootstrapError(null);
    Promise.all([
      fetchPreflight(),
      fetchCapabilities(),
      fetchMaterials(),
      fetchLeMaterialWorkflow(),
    ])
      .then(([nextPreflight, nextCapabilities, nextRows, nextWorkflow]) => {
        if (!active) return;
        setPreflight(nextPreflight);
        setCapabilities(nextCapabilities);
        setRows(nextRows);
        setWorkflow(nextWorkflow);
        setSelectedId(nextPreflight.default_material_id);
        setApiState(nextPreflight.status === "ready" ? "ready" : "degraded");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setApiState("offline");
        setBootstrapError(error instanceof Error ? error.message : String(error));
      });
    return () => {
      active = false;
    };
  }, [loadAttempt]);

  useEffect(() => {
    let active = true;
    if (!selectedId || apiState === "offline") {
      setGraph(null);
      setGraphError(null);
      return () => {
        active = false;
      };
    }
    setGraphLoading(true);
    setGraphError(null);
    fetchGraphSummary(selectedId)
      .then((summary) => {
        if (active) setGraph(summary);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setGraph(null);
        setGraphError(error instanceof Error ? error.message : String(error));
      })
      .finally(() => {
        if (active) setGraphLoading(false);
      });
    return () => {
      active = false;
    };
  }, [apiState, selectedId]);

  const selectedMaterial = rows.find((row) => row.material_id === selectedId) ?? rows[0];
  const selectedReadiness = selectedId
    ? preflight?.simulation_targets[selectedId]
    : undefined;

  function resetDemo() {
    setEaMax(DEFAULT_EAH_MAX);
    setDMax(DEFAULT_DENSITY_MAX);
    setDensityWeight(DEFAULT_DENSITY_WEIGHT);
    setBulkWeight(DEFAULT_BULK_WEIGHT);
    setMissing("worst");
    setAudit(null);
    setRankError(null);
    setSelectedId(preflight?.default_material_id ?? null);
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="dot"></span>
          <span className="brand">MatterGraph</span>
          <span className="mode">open-source capability walkthrough</span>
        </div>
        <div className="topbar-actions">
          <span>deterministic fixture · v0.2</span>
          <button className="text-button" type="button" onClick={resetDemo}>
            Reset demo
          </button>
        </div>
      </header>

      <main className="os-grid">
        <aside className="rail">
          <div className="rail-inner">
            <div className="rail-section">
              <div className="rail-title">Demo preflight</div>
              <span className={`tag ${apiStateClass(apiState)}`}>{apiState}</span>
              {preflight?.checks.map((check) => (
                <span className="rail-check" key={check.id}>
                  <span className={`check-dot ${check.status}`}></span>
                  <span>
                    <strong>{check.id}</strong>
                    <small>{check.detail}</small>
                  </span>
                </span>
              ))}
              {apiState === "loading" ? (
                <p className="empty-note">Running fixture and dependency checks…</p>
              ) : null}
            </div>

            <div className="rail-section">
              <div className="rail-title">Guided flow</div>
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
              <div className="rail-title">Fixture provenance</div>
              <span className="rail-kv">
                <span>Path</span>
                <strong>{preflight?.fixture.path ?? "checking…"}</strong>
              </span>
              <span className="rail-kv">
                <span>Mode</span>
                <strong>{preflight?.fixture.kind ?? "illustrative schema fixture"}</strong>
              </span>
            </div>
          </div>
        </aside>

        <section className="workspace">
          <div className="workspace-header">
            <p className="eyebrow">transparent materials workflow</p>
            <h1>From public records to a validation-ready candidate.</h1>
            <p className="subhead">
              A reproducible Ti–Al–N screening walkthrough: preserve provenance, enforce slice
              guardrails, export crystal graphs, audit a transparent baseline, then run one local
              relaxation.
            </p>
          </div>

          {bootstrapError ? (
            <div className="api-offline" role="alert">
              <div>
                <span className="eval-label">Demo API offline</span>
                <strong>The workbench stopped waiting for the unavailable API.</strong>
                <p>{bootstrapError}</p>
              </div>
              <button className="primary-button" type="button" onClick={() => setLoadAttempt((n) => n + 1)}>
                Retry preflight
              </button>
            </div>
          ) : null}

          <div className="status-strip">
            <Status label="Normalized records" value={preflight?.record_count ?? "—"} />
            <Status label="Graph ready" value={preflight?.graph.included_count ?? "—"} />
            <Status label="Graph excluded" value={preflight?.graph.excluded_count ?? "—"} />
            <Status label="Rank eligible" value={preflight?.ranking.ranked_count ?? "—"} />
            <Status label="Hard excluded" value={preflight?.ranking.excluded_by_constraints ?? "—"} />
            <Status label="Rank output" value={audit ? `${audit.ranked.length} candidates` : "not run"} />
          </div>

          <section className="section-block" id="source">
            <SectionHeader index="01" label="Ingest + normalize" />
            <div className="panel scenario-panel">
              <div>
                <span className="metric-label">Screening question</span>
                <h2>Which lightweight, stiff, near-stable nitride should reach local validation?</h2>
              </div>
              <p>{preflight?.fixture.disclaimer ?? "Loading fixture contract…"}</p>
            </div>

            <div className="panel">
              <div className="panel-heading">
                <span>Open-source capability ledger</span>
                <span>A1</span>
              </div>
              {capabilities.length ? (
                <CapabilityLedger capabilities={capabilities} />
              ) : (
                <p className="empty-note">Loading code-backed capability status…</p>
              )}
            </div>

            <div className="layout-two">
              <div className="panel">
                <div className="panel-heading">
                  <span>Normalized records</span>
                  <span>B1</span>
                </div>
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
                  <span>Provenance inspector</span>
                  <span>C1</span>
                </div>
                <MaterialCard m={selectedMaterial} />
              </div>
            </div>
          </section>

          <section className="section-block" id="slice">
            <SectionHeader index="02" label="Slice + guardrails" />
            <WorkflowSummaryPanel
              workflow={workflow}
              loading={apiState === "loading"}
              error={apiState === "offline" ? bootstrapError : null}
            />
          </section>

          <section className="section-block" id="graph">
            <SectionHeader index="03" label="Graph + benchmark readiness" />
            <div className="panel">
              <div className="panel-heading">
                <span>Selected crystal graph · {selectedId ?? "none"}</span>
                <span>D3</span>
              </div>
              <GraphSummaryPanel summary={graph} loading={graphLoading} error={graphError} />
            </div>
          </section>

          <section className="section-block" id="rank">
            <SectionHeader index="04" label="Rank + audit" />
            <div className="layout-two">
              <div className="panel">
                <div className="panel-heading">
                  <span>Objectives + constraints</span>
                  <span>E4</span>
                </div>
                <ConstraintPanel
                  eahMax={eaMax}
                  onEah={setEaMax}
                  dMax={dMax}
                  onD={setDMax}
                  densityWeight={densityWeight}
                  onDensityWeight={setDensityWeight}
                  bulkWeight={bulkWeight}
                  onBulkWeight={setBulkWeight}
                  missing={missing}
                  onMissing={setMissing}
                  loading={rankLoading}
                  onRank={async (objectives) => {
                    setRankLoading(true);
                    setRankError(null);
                    setAudit(null);
                    try {
                      const result = await rankMaterialsAudit(
                        objectives,
                        eaMax,
                        dMax,
                        missing,
                      );
                      setAudit(result);
                      const lead = String(result.ranked[0]?.material_id ?? "");
                      if (lead) setSelectedId(lead);
                    } catch (error) {
                      setRankError(error instanceof Error ? error.message : String(error));
                    } finally {
                      setRankLoading(false);
                    }
                  }}
                />
              </div>
              <div className="panel">
                <div className="panel-heading">
                  <span>Ranked candidates + audit report</span>
                  <span>F4</span>
                </div>
                <ComparisonView
                  audit={audit}
                  loading={rankLoading}
                  error={rankError}
                  eahMax={eaMax}
                  densityMax={dMax}
                  onSelect={setSelectedId}
                />
              </div>
            </div>
          </section>

          <section className="section-block" id="simulation">
            <SectionHeader index="05" label="Local validation hook" />
            <div className="panel">
              <div className="panel-heading">
                <span>ASE / EMT relaxation</span>
                <span>G5</span>
              </div>
              <SimulationQueue
                materialId={String(selectedMaterial?.material_id ?? "")}
                formula={selectedMaterial?.formula}
                readiness={selectedReadiness}
              />
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}

function Status({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SectionHeader({ index, label }: { index: string; label: string }) {
  return (
    <div className="sheet-header">
      <span>
        {index} — {label}
      </span>
      <span>Step {index} / 05</span>
    </div>
  );
}

function apiStateClass(state: ApiState): "pass" | "warn" | "fail" {
  if (state === "ready") return "pass";
  if (state === "loading" || state === "degraded") return "warn";
  return "fail";
}
