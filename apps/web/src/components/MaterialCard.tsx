import { Fragment } from "react";

import { formatValue } from "../lib/format";
import type { Material } from "../types/material";

export function MaterialCard({ m }: { m: Material | undefined }) {
  if (!m) {
    return <p className="empty-note">Select a material first.</p>;
  }
  const properties = m.properties ?? [];
  const recordProvenance = m.provenance?.[0];
  const fieldProvenance = m.metadata?.field_provenance;
  const fieldEntries = fieldProvenance && typeof fieldProvenance === "object"
    ? Object.entries(fieldProvenance as Record<string, unknown>)
    : [];

  return (
    <div className="detail-panel">
      <h3>Identity</h3>
      <div className="property-grid">
        <div className="property-box">
          <span>Material</span>
          <strong>{String(m.material_id)}</strong>
        </div>
        <div className="property-box">
          <span>Formula</span>
          <strong>{String(m.formula)}</strong>
        </div>
        <div className="property-box">
          <span>Reduced formula</span>
          <strong>{m.reduced_formula ?? "unknown"}</strong>
        </div>
        <div className="property-box">
          <span>Structure</span>
          <strong>{m.structure ? "present" : "missing"}</strong>
        </div>
      </div>

      <h3>Elements</h3>
      <div className="status-pill-row">
        {(m.elements ?? []).length ? (
          (m.elements ?? []).map((element) => (
            <span className="chip" key={element}>
              {element}
            </span>
          ))
        ) : (
          <span className="empty-note">unknown</span>
        )}
      </div>

      <h3>Properties</h3>
      {properties.length ? (
        <div className="property-grid">
          {properties.map((property) => (
            <div
              className="property-box"
              key={`${property.name}-${property.source ?? ""}-${property.method ?? ""}`}
            >
              <span>{property.name}</span>
              <strong>{formatValue(property.value, property.unit)}</strong>
              {/* Provenance is a first-class field here, not tooltip material: every
                  number states where it came from and how it was produced. */}
              <span className="property-source">
                {property.source ?? "unknown"} · {property.method ?? "unknown"}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-note">No properties attached.</p>
      )}

      <h3>Record provenance</h3>
      <div className="kv-grid">
        <span>Record source</span>
        <strong>{String(recordProvenance?.source ?? "unknown")}</strong>
        <span>Source ID</span>
        <strong>{String(m.source_id ?? recordProvenance?.source_id ?? "unknown")}</strong>
        <span>Source dataset</span>
        <strong>{String(m.metadata?.source_dataset ?? "unknown")}</strong>
        <span>Subset</span>
        <strong>{String(m.metadata?.source_subset ?? "unknown")}</strong>
        <span>Functional</span>
        <strong>{String(m.metadata?.functional ?? "unknown")}</strong>
        <span>Immutable ID</span>
        <strong>{String(m.metadata?.immutable_id ?? "unknown")}</strong>
        <span>Fingerprint</span>
        <strong>{String(m.metadata?.structure_fingerprint ?? "unknown")}</strong>
      </div>

      {fieldEntries.length ? (
        <>
          <h3>Field sources</h3>
          <div className="kv-grid">
            {fieldEntries.map(([field, source]) => (
              <Fragment key={field}>
                <span>{field}</span>
                <strong>{String(source)}</strong>
              </Fragment>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
