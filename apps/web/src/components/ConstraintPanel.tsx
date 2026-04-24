import { useState } from "react";

type Props = {
  eahMax: number;
  onEah: (v: number) => void;
  dMax: number;
  onD: (v: number) => void;
  onRank: (objectives: Record<string, "minimize" | "maximize">) => void;
};

export function ConstraintPanel({ eahMax, onEah, dMax, onD, onRank }: Props) {
  const [minD, setMinD] = useState(true);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 400 }}>
      <label>
        Energy above hull max (eV/atom){" "}
        <input
          type="number"
          step="0.01"
          value={eahMax}
          onChange={(e) => onEah(Number(e.target.value))}
        />
      </label>
      <label>
        Density max (g/cm³){" "}
        <input type="number" step="0.1" value={dMax} onChange={(e) => onD(Number(e.target.value))} />
      </label>
      <label>
        <input type="checkbox" checked={minD} onChange={() => setMinD(!minD)} /> minimize density
      </label>
      <button
        type="button"
        onClick={() =>
          onRank({
            density: minD ? "minimize" : "maximize",
            bulk_modulus: "maximize",
          })
        }
      >
        Compute rank
      </button>
    </div>
  );
}
