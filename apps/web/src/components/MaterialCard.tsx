import { Fragment } from "react";

import type { Material } from "../types/material";

export function MaterialCard({ m }: { m: Material | undefined }) {
  if (!m) {
    return <div className="empty-note">Select a material first.</div>;
  }
  const properties = m.properties ?? [];
  const provenance = m.provenance ?? [];
  const metadata = Object.entries(m.metadata ?? {});

  return (
    <div className="detail-card">
      <div className="identity-block">
        <div>
          <span className="metric-label">Material</span>
          <strong>{String(m.material_id)}</strong>
        </div>
        <div>
          <span className="metric-label">Formula</span>
          <strong>{String(m.formula)}</strong>
        </div>
      </div>
      <div className="kv-grid">
        <span>Elements</span>
        <strong>{(m.elements ?? []).join(", ") || "unknown"}</strong>
        <span>Reduced formula</span>
        <strong>{m.reduced_formula ?? "unknown"}</strong>
        <span>Structure</span>
        <strong>{m.structure ? "present" : "missing"}</strong>
      </div>
      <h3>Properties</h3>
      {properties.length ? (
        <table className="data-table compact-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Value</th>
              <th>Source</th>
              <th>Method</th>
            </tr>
          </thead>
          <tbody>
            {properties.map((property) => (
              <tr key={`${property.name}-${property.source ?? "source"}-${property.method ?? "method"}`}>
                <td>{property.name}</td>
                <td>{formatValue(property.value, property.unit)}</td>
                <td>{property.source ?? "unknown"}</td>
                <td>{property.method ?? "unknown"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="empty-note">No properties attached.</div>
      )}
      <h3>Provenance</h3>
      {provenance.length ? (
        <ul className="plain-list">
          {provenance.map((record, index) => (
            <li key={`${record.source ?? "source"}-${index}`}>
              {record.source ?? "unknown"} / {record.method ?? "unknown"}
            </li>
          ))}
        </ul>
      ) : (
        <div className="empty-note">Property rows carry source and method metadata.</div>
      )}
      <h3>Metadata</h3>
      {metadata.length ? (
        <div className="kv-grid">
          {metadata.map(([key, value]) => (
            <Fragment key={key}>
              <span>{key}</span>
              <strong>{formatUnknown(value)}</strong>
            </Fragment>
          ))}
        </div>
      ) : (
        <div className="empty-note">No extra metadata.</div>
      )}
    </div>
  );
}

function formatValue(value: unknown, unit?: string | null): string {
  const formatted = formatUnknown(value);
  return unit ? `${formatted} ${unit}` : formatted;
}

function formatUnknown(value: unknown): string {
  if (value === null || value === undefined) {
    return "unknown";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}
