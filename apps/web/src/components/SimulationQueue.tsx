/**
 * UI placeholder: wire to POST /simulations/ase/relax when you want a one-click relax.
 */
export function SimulationQueue({ materialId }: { materialId: string }) {
  if (!materialId) {
    return <p style={{ color: "#64748b" }}>Select a material first.</p>;
  }
  return (
    <p style={{ color: "#64748b" }}>
      Ready for material <code>{materialId}</code>. Expose a backend route and add a `fetch` call here.
    </p>
  );
}
