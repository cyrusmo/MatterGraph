import type { Material } from "../types/material";

export function MaterialCard({ m }: { m: Material | undefined }) {
  if (!m) {
    return <p style={{ color: "#64748b" }}>No material loaded.</p>;
  }
  return (
    <div style={{ background: "white", padding: 12, border: "1px solid #e2e8f0", borderRadius: 8 }}>
      <div>
        <strong>ID</strong> {String(m.material_id)}
      </div>
      <div>
        <strong>Formula</strong> {String(m.formula)}
      </div>
    </div>
  );
}
