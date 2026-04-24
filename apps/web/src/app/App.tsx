import { useEffect, useState } from "react";

import { MaterialTable } from "../components/MaterialTable";
import { ConstraintPanel } from "../components/ConstraintPanel";
import { MaterialCard } from "../components/MaterialCard";
import { SimulationQueue } from "../components/SimulationQueue";
import { ComparisonView } from "../components/ComparisonView";
import { fetchMaterials, rankMaterials } from "../lib/api";
import type { Material, RankedRow } from "../types/material";

export function App() {
  const [rows, setRows] = useState<Material[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [eaMax, setEaMax] = useState(0.05);
  const [dMax, setDMax] = useState(6.0);
  const [ranked, setRanked] = useState<RankedRow[] | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const materials = await fetchMaterials();
        setRows(materials);
      } catch (e) {
        setErr(String(e));
      }
    })();
  }, []);

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "2rem" }}>
      <h1 style={{ fontWeight: 600 }}>MatterGraph demo</h1>
      <p style={{ color: "#334155" }}>
        Minimal physics-aware data UI: dev server proxies <code>/materials</code> to the API on port 8000.
      </p>
      {err && <p style={{ color: "crimson" }}>API error: {err}</p>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
        <div>
          <h2>Materials</h2>
          <MaterialTable materials={rows} />
        </div>
        <div>
          <h2>First entry</h2>
          <MaterialCard m={rows[0]} />
        </div>
      </div>
      <div style={{ marginTop: 24 }}>
        <h2>Constraint panel (toy score)</h2>
        <ConstraintPanel
          eahMax={eaMax}
          onEah={setEaMax}
          dMax={dMax}
          onD={setDMax}
          onRank={async (objectives) => {
            setRanked(null);
            const rankedRows = await rankMaterials(objectives, eaMax, dMax);
            setRanked(rankedRows);
          }}
        />
        {ranked && <ComparisonView rows={ranked} />}
        <div style={{ marginTop: 24 }}>
          <h2>Simulation (placeholder)</h2>
          <SimulationQueue materialId={String(rows[0]?.material_id ?? "")} />
        </div>
      </div>
    </div>
  );
}
