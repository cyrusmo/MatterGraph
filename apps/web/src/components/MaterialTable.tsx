import type { Material } from "../types/material";

export function MaterialTable({ materials }: { materials: Material[] }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr style={{ textAlign: "left", borderBottom: "1px solid #cbd5e1" }}>
          <th>ID</th>
          <th>Formula</th>
        </tr>
      </thead>
      <tbody>
        {materials.map((m) => (
          <tr key={String(m.material_id)} style={{ borderBottom: "1px solid #e2e8f0" }}>
            <td>{String(m.material_id)}</td>
            <td>{String(m.formula)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
