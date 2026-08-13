type Props = {
  eahMax: number;
  onEah: (value: number) => void;
  forceMax: number;
  onForce: (value: number) => void;
  loading: boolean;
  densityWeight: number;
  onDensityWeight: (value: number) => void;
  hullWeight: number;
  onHullWeight: (value: number) => void;
  missing: "worst" | "neutral" | "exclude";
  onMissing: (value: "worst" | "neutral" | "exclude") => void;
  onRank: (
    objectives: Record<string, { direction: "minimize" | "maximize"; weight: number }>,
  ) => void;
};

export function ConstraintPanel({
  eahMax,
  onEah,
  forceMax,
  onForce,
  loading,
  densityWeight,
  onDensityWeight,
  hullWeight,
  onHullWeight,
  missing,
  onMissing,
  onRank,
}: Props) {
  return (
    <div className="control-panel">
      <div className="control-grid">
        <label>
          DFT hull max (eV/atom)
          <input type="number" step="0.01" value={eahMax} onChange={(event) => onEah(Number(event.target.value))} />
        </label>
        <label>
          Residual max force (eV/Å)
          <input type="number" step="0.05" value={forceMax} onChange={(event) => onForce(Number(event.target.value))} />
        </label>
      </div>
      <div className="control-grid">
        <label>
          Density weight · minimize
          <input type="number" min="0" step="0.1" value={densityWeight} onChange={(event) => onDensityWeight(Number(event.target.value))} />
        </label>
        <label>
          DFT hull weight · minimize
          <input type="number" min="0" step="0.1" value={hullWeight} onChange={(event) => onHullWeight(Number(event.target.value))} />
        </label>
      </div>
      <label>
        Missing objective policy
        <select value={missing} onChange={(event) => onMissing(event.target.value as Props["missing"])}>
          <option value="worst">score as worst</option>
          <option value="neutral">score as neutral</option>
          <option value="exclude">exclude candidate</option>
        </select>
      </label>
      <button
        className="primary-button"
        type="button"
        aria-busy={loading}
        onClick={() => onRank({
          density: { direction: "minimize", weight: densityWeight },
          energy_above_hull: { direction: "minimize", weight: hullWeight },
        })}
        disabled={loading}
      >
        {loading ? "Computing…" : "Run transparent scorecard"}
      </button>
    </div>
  );
}
