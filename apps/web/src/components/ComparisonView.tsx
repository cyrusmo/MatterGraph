import type { RankedRow } from "../types/material";

export function ComparisonView({ rows }: { rows: RankedRow[] }) {
  const keys = Object.keys(rows[0] ?? {});
  return (
    <div style={{ overflowX: "auto", marginTop: 8 }}>
      <table style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {keys.map((k) => (
              <th key={k} style={{ textAlign: "left", borderBottom: "1px solid #94a3b8" }}>
                {k}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={String(r.material_id ?? Math.random())}>
              {keys.map((k) => (
                <td key={k} style={{ borderBottom: "1px solid #e2e8f0", paddingRight: 8 }}>
                  {String(r[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
