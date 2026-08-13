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

const SCREENS = [
  { id: "records", index: "01", label: "Real records" },
  { id: "structure", index: "02", label: "Reconstructed structure" },
  { id: "graph", index: "03", label: "Periodic graph" },
  { id: "rank", index: "04", label: "Transparent shortlist" },
  { id: "relax", index: "05", label: "ML evidence" },
] as const;

const DEFAULT_HULL_MAX = 0.05;
const DEFAULT_FORCE_MAX = 0.2;
const DEFAULT_DENSITY_WEIGHT = 0.6;
const DEFAULT_HULL_WEIGHT = 0.4;

type ApiState = "loading" | "ready" | "degraded" | "offline";

export function App() {
  const [screen, setScreen] = useState(0);
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
  const [hullMax, setHullMax] = useState(DEFAULT_HULL_MAX);
  const [forceMax, setForceMax] = useState(DEFAULT_FORCE_MAX);
  const [densityWeight, setDensityWeight] = useState(DEFAULT_DENSITY_WEIGHT);
  const [hullWeight, setHullWeight] = useState(DEFAULT_HULL_WEIGHT);
  const [missing, setMissing] = useState<"worst" | "neutral" | "exclude">("worst");
  const [audit, setAudit] = useState<ScoreAudit | null>(null);
  const [rankLoading, setRankLoading] = useState(false);
  const [rankError, setRankError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, select, textarea")) return;
      if (event.key === "ArrowRight" || event.key === "PageDown") {
        event.preventDefault();
        setScreen((value) => Math.min(value + 1, SCREENS.length - 1));
      }
      if (event.key === "ArrowLeft" || event.key === "PageUp") {
        event.preventDefault();
        setScreen((value) => Math.max(value - 1, 0));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [screen]);

  useEffect(() => {
    let active = true;
    setApiState("loading");
    setBootstrapError(null);
    Promise.all([fetchPreflight(), fetchCapabilities(), fetchMaterials(), fetchLeMaterialWorkflow()])
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
    return () => { active = false; };
  }, [loadAttempt]);

  useEffect(() => {
    let active = true;
    if (!selectedId || apiState === "offline") return;
    setGraphLoading(true);
    setGraphError(null);
    fetchGraphSummary(selectedId)
      .then((summary) => { if (active) setGraph(summary); })
      .catch((error: unknown) => {
        if (!active) return;
        setGraph(null);
        setGraphError(error instanceof Error ? error.message : String(error));
      })
      .finally(() => { if (active) setGraphLoading(false); });
    return () => { active = false; };
  }, [apiState, selectedId]);

  const selectedMaterial = rows.find((row) => row.material_id === selectedId) ?? rows[0];

  function resetDemo() {
    setScreen(0);
    setHullMax(DEFAULT_HULL_MAX);
    setForceMax(DEFAULT_FORCE_MAX);
    setDensityWeight(DEFAULT_DENSITY_WEIGHT);
    setHullWeight(DEFAULT_HULL_WEIGHT);
    setMissing("worst");
    setAudit(null);
    setRankError(null);
    setSelectedId(preflight?.default_material_id ?? null);
  }

  return (
    <div className="shell presentation-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="dot" />
          <span className="brand">MatterGraph</span>
          <span className="mode">evidence-first public demo</span>
        </div>
        <div className="topbar-actions">
          <span>offline snapshot · v1</span>
          <button className="text-button" type="button" onClick={resetDemo}>Reset demo</button>
        </div>
      </header>

      <main className="presentation-grid">
        <aside className="rail presentation-rail">
          <div className="rail-inner">
            <div className="rail-section">
              <div className="rail-title">Preflight</div>
              <span className={`tag ${apiStateClass(apiState)}`}>{apiState}</span>
              {preflight?.checks.map((check) => (
                <span className="rail-check" key={check.id}>
                  <span className={`check-dot ${check.status}`} />
                  <span><strong>{check.id}</strong><small>{check.detail}</small></span>
                </span>
              ))}
              {apiState === "loading" ? <p className="empty-note">Checking local evidence…</p> : null}
            </div>
            <nav className="rail-section rail-nav" aria-label="Presentation screens">
              <div className="rail-title">Five-screen story</div>
              {SCREENS.map((item, index) => (
                <button
                  key={item.id}
                  className="nav-item"
                  type="button"
                  aria-current={screen === index ? "step" : undefined}
                  onClick={() => setScreen(index)}
                >
                  {item.index} {item.label}
                </button>
              ))}
            </nav>
            <div className="rail-section keyboard-hint">← / → navigate</div>
          </div>
        </aside>

        <section className="presentation-workspace">
          <div className="workspace-header presentation-header">
            <p className="eyebrow">{SCREENS[screen].index} / 05 · {SCREENS[screen].label}</p>
            <h1>Which lightweight, near-hull nitride should receive local ML validation?</h1>
            <p className="subhead">Real records → reconstructed structure → reciprocal periodic graph → audited scorecard → explicitly labeled CHGNet evidence.</p>
          </div>

          {bootstrapError ? (
            <div className="api-offline" role="alert">
              <div><span className="eval-label">Demo API offline</span><strong>The UI stopped waiting after five seconds.</strong><p>{bootstrapError}</p></div>
              <button className="primary-button" type="button" onClick={() => setLoadAttempt((value) => value + 1)}>Retry preflight</button>
            </div>
          ) : null}

          <div className="presentation-screen" key={SCREENS[screen].id}>
            {screen === 0 ? (
              <>
                <div className="status-strip">
                  <Status label="Frozen records" value={preflight?.record_count ?? "—"} />
                  <Status label="Source rows" value={preflight ? preflight.fixture.source_population.toLocaleString() : "—"} />
                  <Status label="License" value={preflight?.fixture.license ?? "—"} />
                  <Status label="Snapshot" value={preflight?.fixture.snapshot_sha256.slice(0, 12) ?? "—"} />
                </div>
                <div className="layout-two presentation-content">
                  <div className="panel">
                    <div className="panel-heading"><span>Real frozen cohort</span><span>A1</span></div>
                    <MaterialTable materials={rows} selectedId={selectedId} onSelect={setSelectedId} eahMax={hullMax} forceMax={forceMax} />
                  </div>
                  <div className="panel"><div className="panel-heading"><span>Field-level provenance</span><span>B1</span></div><MaterialCard m={selectedMaterial} /></div>
                </div>
                <ScreenAction label="Inspect reconstruction" onClick={() => setScreen(1)} />
              </>
            ) : null}

            {screen === 1 ? (
              <>
                <WorkflowSummaryPanel workflow={workflow} loading={apiState === "loading"} error={apiState === "offline" ? bootstrapError : null} />
                <ScreenAction label="Open periodic graph" onClick={() => setScreen(2)} />
              </>
            ) : null}

            {screen === 2 ? (
              <>
                <div className="panel presentation-content"><div className="panel-heading"><span>Exact graph geometry · {selectedId}</span><span>C3</span></div><GraphSummaryPanel summary={graph} loading={graphLoading} error={graphError} /></div>
                <ScreenAction label="Review shortlist" onClick={() => setScreen(3)} />
              </>
            ) : null}

            {screen === 3 ? (
              <div className="layout-two presentation-content">
                <div className="panel">
                  <div className="panel-heading"><span>Objectives + constraints</span><span>D4</span></div>
                  <ConstraintPanel
                    eahMax={hullMax} onEah={setHullMax} forceMax={forceMax} onForce={setForceMax}
                    densityWeight={densityWeight} onDensityWeight={setDensityWeight}
                    hullWeight={hullWeight} onHullWeight={setHullWeight}
                    missing={missing} onMissing={setMissing} loading={rankLoading}
                    onRank={async (objectives) => {
                      setRankLoading(true); setRankError(null); setAudit(null);
                      try {
                        const result = await rankMaterialsAudit(objectives, hullMax, forceMax, missing);
                        setAudit(result);
                        const lead = String(result.ranked[0]?.material_id ?? "");
                        if (lead) setSelectedId(lead);
                      } catch (error) { setRankError(error instanceof Error ? error.message : String(error)); }
                      finally { setRankLoading(false); }
                    }}
                  />
                </div>
                <div className="panel"><div className="panel-heading"><span>Audited result</span><span>E4</span></div><ComparisonView audit={audit} loading={rankLoading} error={rankError} eahMax={hullMax} forceMax={forceMax} onSelect={setSelectedId} /></div>
              </div>
            ) : null}

            {screen === 4 ? (
              <div className="panel presentation-content">
                <div className="panel-heading"><span>CHGNet relaxation evidence</span><span>F5</span></div>
                <SimulationQueue materialId={String(selectedMaterial?.material_id ?? "")} formula={selectedMaterial?.formula} chgnet={preflight?.chgnet} />
              </div>
            ) : null}
          </div>

          <div className="screen-pagination" aria-label="Presentation pagination">
            <button type="button" onClick={() => setScreen((value) => Math.max(0, value - 1))} disabled={screen === 0}>← Previous</button>
            <span>{SCREENS[screen].index} / 05</span>
            <button type="button" onClick={() => setScreen((value) => Math.min(SCREENS.length - 1, value + 1))} disabled={screen === SCREENS.length - 1}>Next →</button>
          </div>

          <details className="evidence-drawer">
            <summary>Technical evidence & capability boundaries</summary>
            <div className="drawer-content">
              <div className="kv-grid">
                <span>Dataset</span><strong>{preflight?.fixture.dataset ?? "—"} / {preflight?.fixture.subset ?? "—"}</strong>
                <span>Revision</span><strong>{preflight?.fixture.upstream_revision ?? "—"}</strong>
                <span>Hull join</span><strong>{preflight?.fixture.hull_revision ?? "—"}</strong>
                <span>Citation</span><strong>DOI {preflight?.fixture.citation_doi ?? "—"}</strong>
              </div>
              {capabilities.length ? <CapabilityLedger capabilities={capabilities} /> : <p className="empty-note">Loading capability evidence…</p>}
            </div>
          </details>
        </section>
      </main>
    </div>
  );
}

function Status({ label, value }: { label: string; value: string | number }) {
  return <div><span className="metric-label">{label}</span><strong>{value}</strong></div>;
}

function ScreenAction({ label, onClick }: { label: string; onClick: () => void }) {
  return <div className="screen-action"><button className="primary-button" type="button" onClick={onClick}>{label} →</button></div>;
}

function apiStateClass(state: ApiState): "pass" | "warn" | "fail" {
  if (state === "ready") return "pass";
  if (state === "loading" || state === "degraded") return "warn";
  return "fail";
}
