import { useEffect, useState } from "react";

import { ComparisonView } from "../components/ComparisonView";
import { ConstraintPanel } from "../components/ConstraintPanel";
import { MaterialCard } from "../components/MaterialCard";
import { MaterialTable } from "../components/MaterialTable";
import { SimulationQueue } from "../components/SimulationQueue";
import { WorkflowSummaryPanel } from "../components/WorkflowSummaryPanel";
import { fetchLeMaterialWorkflow, fetchMaterials, rankMaterials } from "../lib/api";
import type { LeMaterialWorkflowSummary, Material, RankedRow } from "../types/material";

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

      <main className="workspace">
        <section className="hero-panel">
          <p className="eyebrow">transparent materials workflow</p>
          <h1>Demo workbench</h1>
          <p>
            Inspect demo records, run a toy scorecard, review a LeMaterial demo workflow summary,
            and trigger an ASE demo relaxation.
          </p>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">LeMaterial demo workflow</p>
              <h2>Fixture -&gt; graph-ready summary</h2>
            </div>
          </div>
          <WorkflowSummaryPanel workflow={workflow} loading={workflowLoading} error={workflowErr} />
        </section>

        <section className="split-grid">
          <div className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">materials</p>
                <h2>Demo records</h2>
              </div>
            </div>
            {materialsErr && <div className="error-note">{materialsErr}</div>}
            <MaterialTable materials={rows} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
          <div className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">inspector</p>
                <h2>Selected material</h2>
              </div>
            </div>
            <MaterialCard m={selectedMaterial} />
          </div>
        </section>

        <section className="split-grid">
          <div className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">toy scorecard</p>
                <h2>Rank candidates</h2>
              </div>
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
            <ComparisonView
              rows={ranked}
              loading={rankLoading}
              error={rankErr}
              eahMax={eaMax}
              densityMax={dMax}
            />
          </div>

          <div className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">ASE demo relaxation</p>
                <h2>Simulation hook</h2>
              </div>
            </div>
            <SimulationQueue
              materialId={String(selectedMaterial?.material_id ?? "")}
              formula={selectedMaterial?.formula}
            />
          </div>
        </section>
      </main>
    </div>
  );
}

function preferredMaterialId(materials: Material[]): string | null {
  const preferred = materials.find((material) => material.material_id === "demo-al-fcc-1");
  return String(preferred?.material_id ?? materials[0]?.material_id ?? "") || null;
}
