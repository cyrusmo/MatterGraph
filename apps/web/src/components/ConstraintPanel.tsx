import { useState } from "react";

type Props = {
  eahMax: number;
  onEah: (v: number) => void;
  dMax: number;
  onD: (v: number) => void;
  loading: boolean;
  onRank: (objectives: Record<string, "minimize" | "maximize">) => void;
};

export function ConstraintPanel({ eahMax, onEah, dMax, onD, loading, onRank }: Props) {
  const [minD, setMinD] = useState(true);
  return (
    <div className="control-panel">
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
        Density max (g/cm^3){" "}
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
        disabled={loading}
      >
        {loading ? "Computing..." : "Compute toy rank"}
      </button>
    </div>
  );
}
