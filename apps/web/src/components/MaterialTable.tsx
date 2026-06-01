import type { Material } from "../types/material";

type Props = {
  materials: Material[];
  selectedId: string | null;
  onSelect: (materialId: string) => void;
};

export function MaterialTable({ materials, selectedId, onSelect }: Props) {
  if (!materials.length) {
    return <div className="empty-note">No demo materials loaded.</div>;
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Formula</th>
          <th>Elements</th>
        </tr>
      </thead>
      <tbody>
        {materials.map((m) => (
          <tr
            key={String(m.material_id)}
            className={m.material_id === selectedId ? "selected-row" : undefined}
          >
            <td>
              <button
                className="row-select"
                type="button"
                onClick={() => onSelect(String(m.material_id))}
              >
                {String(m.material_id)}
              </button>
            </td>
            <td>{String(m.formula)}</td>
            <td>{(m.elements ?? []).join(", ")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
