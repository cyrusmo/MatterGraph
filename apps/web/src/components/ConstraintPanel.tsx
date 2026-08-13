import { useState } from "react";

type Props = {
  eahMax: number;
  onEah: (v: number) => void;
  dMax: number;
  onD: (v: number) => void;
  loading: boolean;
  densityWeight: number;
  onDensityWeight: (value: number) => void;
  bulkWeight: number;
  onBulkWeight: (value: number) => void;
  missing: "worst" | "neutral" | "exclude";
  onMissing: (value: "worst" | "neutral" | "exclude") => void;
  onRank: (
    objectives: Record<string, { direction: "minimize" | "maximize"; weight: number }>,
  ) => void;
};

export function ConstraintPanel({
  eahMax,
  onEah,
  dMax,
  onD,
  loading,
  densityWeight,
  onDensityWeight,
  bulkWeight,
  onBulkWeight,
  missing,
  onMissing,
  onRank,
}: Props) {
  const [minD, setMinD] = useState(true);

  return (
    <div className="control-panel">
      <div className="control-grid">
        <label>
          Energy above hull max (eV/atom)
          <input
            type="number"
            step="0.01"
            value={eahMax}
            onChange={(e) => onEah(Number(e.target.value))}
          />
        </label>
        <label>
          Density max (g/cm^3)
          <input type="number" step="0.1" value={dMax} onChange={(e) => onD(Number(e.target.value))} />
        </label>
      </div>

      <div className="control-grid">
        <label>
          Density weight
          <input
            type="number"
            min="0"
            step="0.1"
            value={densityWeight}
            onChange={(event) => onDensityWeight(Number(event.target.value))}
          />
        </label>
        <label>
          Bulk modulus weight
          <input
            type="number"
            min="0"
            step="0.1"
            value={bulkWeight}
            onChange={(event) => onBulkWeight(Number(event.target.value))}
          />
        </label>
      </div>

      <label>
        Missing objective policy
        <select
          value={missing}
          onChange={(event) =>
            onMissing(event.target.value as "worst" | "neutral" | "exclude")
          }
        >
          <option value="worst">score as worst</option>
          <option value="neutral">score as neutral</option>
          <option value="exclude">exclude candidate</option>
        </select>
      </label>

      <div className="toggle-row">
        <button
          className="toggle-button"
          type="button"
          aria-pressed={minD}
          onClick={() => setMinD(true)}
        >
          minimize density
        </button>
        <button
          className="toggle-button"
          type="button"
          aria-pressed={!minD}
          onClick={() => setMinD(false)}
        >
          maximize density
        </button>
      </div>

      <button
        className="primary-button"
        type="button"
        aria-busy={loading}
        onClick={() =>
          onRank({
            density: {
              direction: minD ? "minimize" : "maximize",
              weight: densityWeight,
            },
            bulk_modulus: { direction: "maximize", weight: bulkWeight },
          })
        }
        disabled={loading}
      >
        {loading ? "Computing…" : "Run audited baseline"}
      </button>
    </div>
  );
}
