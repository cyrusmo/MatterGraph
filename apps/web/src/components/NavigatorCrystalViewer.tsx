import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import type { NavigatorMaterial, NavigatorStructure } from "../types/navigator";

export function NavigatorCrystalViewer({ material }: { material: NavigatorMaterial }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [webglFailed, setWebglFailed] = useState(false);
  const issues = useMemo(() => structureIssues(material.structure), [material.structure]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || issues.length) return;
    host.replaceChildren();
    setWebglFailed(false);
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setWebglFailed(true);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const lattice = material.structure.structure.lattice.map((row) => new THREE.Vector3(...row));
    const center = lattice.reduce((sum, vector) => sum.add(vector), new THREE.Vector3()).multiplyScalar(0.5);
    const span = Math.max(...lattice.map((vector) => vector.length()), 1);
    const camera = new THREE.PerspectiveCamera(34, 1, 0.05, 500);
    camera.position.copy(center).add(new THREE.Vector3(span * 1.7, span * 1.35, span * 1.9));
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(center);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.update();

    scene.add(new THREE.AmbientLight(0xffffff, 2.4));
    const key = new THREE.DirectionalLight(0xffffff, 2.8);
    key.position.set(8, 10, 12);
    scene.add(key);
    scene.add(unitCell(lattice));

    const geometry = new THREE.SphereGeometry(Math.max(0.12, span * 0.035), 24, 16);
    const materials = new Map<string, THREE.MeshStandardMaterial>();
    material.structure.structure.coords.forEach((coordinate, index) => {
      const label = speciesLabel(material.structure.structure.species[index]);
      const atomMaterial = materials.get(label) ?? new THREE.MeshStandardMaterial({
        color: elementColor(label),
        roughness: 0.42,
        metalness: 0.08,
      });
      materials.set(label, atomMaterial);
      const atom = new THREE.Mesh(geometry, atomMaterial);
      const fractional = coordinate.map((value) => ((value % 1) + 1) % 1);
      atom.position.copy(lattice[0].clone().multiplyScalar(fractional[0]))
        .add(lattice[1].clone().multiplyScalar(fractional[1]))
        .add(lattice[2].clone().multiplyScalar(fractional[2]));
      scene.add(atom);
    });

    const resize = () => {
      const width = Math.max(host.clientWidth, 280);
      const height = Math.max(host.clientHeight, 320);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();
    let frame = 0;
    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    };
    animate();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
          object.geometry.dispose();
          const owned = object.material;
          if (Array.isArray(owned)) owned.forEach((item) => item.dispose());
          else owned.dispose();
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [issues, material]);

  if (issues.length) {
    return (
      <div className="eval-output fail" role="alert">
        <span className="eval-label">Structure blocked</span>
        {issues.map((issue) => <span key={issue}>{issue}</span>)}
      </div>
    );
  }

  return (
    <div className="navigator-crystal-layout">
      <div>
        <div ref={hostRef} className="navigator-crystal-viewport" aria-label={`${material.formula} atoms and unit cell`} />
        {webglFailed ? <p className="empty-note" role="status">WebGL unavailable; use the exact site table.</p> : null}
        <p className="boundary-note">
          Atoms and the source unit cell only. No bonds or neighbor chemistry are inferred.
        </p>
      </div>
      <div className="navigator-structure-data">
        <dl>
          <div><dt>Structure ID</dt><dd>{material.structure.structure_id}</dd></div>
          <div><dt>Source</dt><dd>{material.structure.source}</dd></div>
          <div><dt>Method</dt><dd>{material.structure.method}</dd></div>
          <div><dt>Coordinates</dt><dd>fractional · periodic x/y/z</dd></div>
          <div><dt>Lattice unit</dt><dd>angstrom</dd></div>
        </dl>
        <div className="navigator-site-table-wrap">
          <table className="data-table navigator-site-table">
            <caption>Exact source-backed fractional sites</caption>
            <thead><tr><th>Site</th><th>Species</th><th>Fractional coordinate</th></tr></thead>
            <tbody>
              {material.structure.structure.coords.slice(0, 200).map((coordinate, index) => (
                <tr key={`${index}-${coordinate.join("-")}`}>
                  <td>{index + 1}</td>
                  <td>{speciesLabel(material.structure.structure.species[index])}</td>
                  <td>{coordinate.map((value) => value.toFixed(5)).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export function structureIssues(contract: NavigatorStructure): string[] {
  const issues: string[] = [];
  const { lattice, coords, species } = contract.structure;
  if (contract.lattice_unit !== "angstrom") issues.push("Lattice unit is not angstrom.");
  if (contract.coordinate_convention !== "fractional") issues.push("Coordinate convention is ambiguous.");
  if (contract.occupancy_convention !== "species_mapping") issues.push("Occupancy semantics are unknown.");
  if (contract.periodic_axes.length !== 3 || !contract.periodic_axes.every(Boolean)) issues.push("Periodic axes are incomplete.");
  if (lattice.length !== 3 || lattice.some((row) => row.length !== 3 || row.some((value) => !Number.isFinite(value)))) {
    issues.push("Lattice must be a finite 3×3 matrix.");
  } else if (Math.abs(determinant(lattice)) <= 1e-10) {
    issues.push("Periodic lattice is singular.");
  }
  if (!coords.length || coords.length !== species.length) issues.push("Species and coordinate counts differ.");
  if (coords.some((row) => row.length !== 3 || row.some((value) => !Number.isFinite(value)))) issues.push("Coordinates must be finite N×3 values.");
  if (!contract.source || !contract.source_id || !contract.method || !contract.provenance.length) issues.push("Structure provenance is incomplete.");
  return issues;
}

function unitCell(lattice: THREE.Vector3[]) {
  const [a, b, c] = lattice;
  const origin = new THREE.Vector3();
  const vertices = [origin, a, b, c, a.clone().add(b), a.clone().add(c), b.clone().add(c), a.clone().add(b).add(c)];
  const pairs = [[0, 1], [0, 2], [0, 3], [1, 4], [1, 5], [2, 4], [2, 6], [3, 5], [3, 6], [4, 7], [5, 7], [6, 7]];
  const geometry = new THREE.BufferGeometry().setFromPoints(pairs.flatMap(([start, end]) => [vertices[start], vertices[end]]));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: 0x74c7d3, transparent: true, opacity: 0.72 }));
}

function speciesLabel(species: string | Record<string, number>): string {
  return typeof species === "string" ? species : Object.keys(species).sort().join("/");
}

function elementColor(label: string): THREE.Color {
  let hash = 0;
  for (const character of label) hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0;
  return new THREE.Color().setHSL(Math.abs(hash % 360) / 360, 0.48, 0.62);
}

function determinant(matrix: [number, number, number][]): number {
  const [a, b, c] = matrix;
  return a[0] * (b[1] * c[2] - b[2] * c[1])
    - a[1] * (b[0] * c[2] - b[2] * c[0])
    + a[2] * (b[0] * c[1] - b[1] * c[0]);
}
