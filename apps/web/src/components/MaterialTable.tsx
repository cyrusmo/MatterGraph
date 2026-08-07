import { propertyNumber } from "../lib/format";
import type { Material } from "../types/material";

type Props = {
  materials: Material[];
  selectedId: string | null;
  onSelect: (materialId: string) => void;
  eahMax: number;
  densityMax: number;
};

export function MaterialTable({ materials, selectedId, onSelect, eahMax, densityMax }: Props) {
  if (!materials.length) {
    return <p className="empty-note">No demo materials loaded.</p>;
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Formula</th>
          <th>Elements</th>
          <th>Constraints</th>
        </tr>
      </thead>
      <tbody>
        {materials.map((m) => {
          const id = String(m.material_id);
          const selected = m.material_id === selectedId;
          const verdict = constraintVerdict(m, eahMax, densityMax);
          return (
            <tr
              key={id}
              className={`selectable-row${selected ? " selected-row" : ""}`}
              aria-current={selected ? "true" : undefined}
              onClick={() => onSelect(id)}
            >
              <td>
                {/* The button, not the row, is the keyboard path. Clicking it would also
                    bubble to the row handler, which selects the same id — harmless. */}
                <button className="row-select" type="button" onClick={() => onSelect(id)}>
                  {id}
                </button>
              </td>
              <td>{String(m.formula)}</td>
              <td>{(m.elements ?? []).join(", ")}</td>
              <td>
                <span className={`tag ${verdict.state}`}>{verdict.label}</span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/**
 * Whether a record would survive the hard constraints currently set on the scorecard.
 * Shown before ranking, so the table explains why a candidate never reaches the results.
 */
function constraintVerdict(
  material: Material,
  eahMax: number,
  densityMax: number,
): { state: "pass" | "fail" | ""; label: string } {
  const density = propertyNumber(material, "density");
  const eah = propertyNumber(material, "energy_above_hull");
  if (density === null && eah === null) {
    return { state: "", label: "no data" };
  }
  if (density !== null && density > densityMax) {
    return { state: "fail", label: "density" };
  }
  if (eah !== null && eah > eahMax) {
    return { state: "fail", label: "hull" };
  }
  return { state: "pass", label: "pass" };
}
