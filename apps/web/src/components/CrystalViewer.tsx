import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { formatNumber } from "../lib/format";
import type { GraphEdge, GraphSummary } from "../types/material";

type EdgeMode = "first_shell" | "model_graph";

const ELEMENT_COLORS: Record<string, number> = {
  Al: 0x79a8ff,
  Ti: 0xb7c0cf,
  N: 0x43d19e,
};

export function CrystalViewer({ summary }: { summary: GraphSummary }) {
  const mount = useRef<HTMLDivElement>(null);
  const [edgeMode, setEdgeMode] = useState<EdgeMode>("first_shell");
  const [showGhosts, setShowGhosts] = useState(true);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    const host = mount.current;
    if (!host) return;
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
    const camera = new THREE.PerspectiveCamera(34, 1, 0.05, 500);
    const lattice = summary.lattice_vectors.map((vector) => new THREE.Vector3(...vector));
    const center = lattice.reduce((total, vector) => total.add(vector), new THREE.Vector3()).multiplyScalar(0.5);
    const span = Math.max(...lattice.map((vector) => vector.length()), 1);
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

    const atomGeometry = new THREE.SphereGeometry(Math.max(0.12, span * 0.035), 24, 16);
    const materialCache = new Map<string, THREE.MeshStandardMaterial>();
    for (const node of summary.nodes) {
      const material = materialCache.get(node.species) ?? new THREE.MeshStandardMaterial({
        color: ELEMENT_COLORS[node.species] ?? 0xf1a95b,
        metalness: node.species === "Ti" ? 0.3 : 0.05,
        roughness: 0.45,
      });
      materialCache.set(node.species, material);
      const atom = new THREE.Mesh(atomGeometry, material);
      atom.position.set(...node.cartesian_coordinates);
      scene.add(atom);
    }

    const visibleEdges = edgeMode === "first_shell" ? firstShellEdges(summary) : summary.edges;
    const edgeMaterial = new THREE.MeshBasicMaterial({ color: 0x9aa9bd, transparent: true, opacity: 0.66 });
    for (const edge of visibleEdges) {
      const cylinder = edgeCylinder(edge, Math.max(0.018, span * 0.005), edgeMaterial);
      cylinder.userData.edge = edge;
      scene.add(cylinder);
    }

    if (showGhosts) {
      const ghostGeometry = new THREE.SphereGeometry(Math.max(0.1, span * 0.029), 18, 12);
      const ghostMaterials = new Map<string, THREE.MeshStandardMaterial>();
      for (const ghost of periodicGhosts(summary, visibleEdges)) {
        const species = summary.nodes[ghost.target]?.species ?? "?";
        const material = ghostMaterials.get(species) ?? new THREE.MeshStandardMaterial({
          color: ELEMENT_COLORS[species] ?? 0xf1a95b,
          transparent: true,
          opacity: 0.27,
          roughness: 0.55,
        });
        ghostMaterials.set(species, material);
        const mesh = new THREE.Mesh(ghostGeometry, material);
        mesh.position.set(...ghost.target_cartesian);
        scene.add(mesh);
      }
    }

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const onClick = (event: MouseEvent) => {
      const bounds = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(scene.children, false).find((item) => item.object.userData.edge);
      setSelectedEdge((hit?.object.userData.edge as GraphEdge | undefined) ?? null);
    };
    renderer.domElement.addEventListener("click", onClick);

    const resize = () => {
      const width = Math.max(host.clientWidth, 280);
      const height = Math.max(host.clientHeight, 300);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);
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
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("click", onClick);
      controls.dispose();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
          object.geometry.dispose();
        }
      });
      for (const material of materialCache.values()) material.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [edgeMode, showGhosts, summary]);

  return (
    <div className="viewer-shell">
      <div className="viewer-toolbar" aria-label="Crystal viewer controls">
        <button type="button" aria-pressed={edgeMode === "first_shell"} onClick={() => setEdgeMode("first_shell")}>
          first shell
        </button>
        <button type="button" aria-pressed={edgeMode === "model_graph"} onClick={() => setEdgeMode("model_graph")}>
          model graph
        </button>
        <button type="button" aria-pressed={showGhosts} onClick={() => setShowGhosts((value) => !value)}>
          periodic images
        </button>
      </div>
      <div ref={mount} className="crystal-viewport" aria-label={`${summary.formula} periodic crystal graph`} />
      {webglFailed ? (
        <div className="webgl-fallback" role="status">
          WebGL is unavailable. Geometry metadata and validation remain available.
        </div>
      ) : null}
      <div className="edge-readout" aria-live="polite">
        {selectedEdge ? (
          <>
            <strong>Edge {selectedEdge.source} → {selectedEdge.target}</strong>
            <span>{formatNumber(selectedEdge.distance)} Å</span>
            <span>image [{selectedEdge.image.join(", ")}]</span>
          </>
        ) : (
          <span>Select an edge to inspect its periodic image and distance.</span>
        )}
      </div>
    </div>
  );
}

function unitCell(lattice: THREE.Vector3[]) {
  const [a, b, c] = lattice;
  const origin = new THREE.Vector3();
  const vertices = [origin, a, b, c, a.clone().add(b), a.clone().add(c), b.clone().add(c), a.clone().add(b).add(c)];
  const pairs = [[0, 1], [0, 2], [0, 3], [1, 4], [1, 5], [2, 4], [2, 6], [3, 5], [3, 6], [4, 7], [5, 7], [6, 7]];
  const points = pairs.flatMap(([source, target]) => [vertices[source], vertices[target]]);
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: 0x526174, transparent: true, opacity: 0.8 }));
}

function edgeCylinder(edge: GraphEdge, radius: number, material: THREE.Material) {
  const start = new THREE.Vector3(...edge.source_cartesian);
  const end = new THREE.Vector3(...edge.target_cartesian);
  const midpoint = start.clone().add(end).multiplyScalar(0.5);
  const direction = end.clone().sub(start);
  const cylinder = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, direction.length(), 8), material);
  cylinder.position.copy(midpoint);
  cylinder.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
  return cylinder;
}

function firstShellEdges(summary: GraphSummary) {
  const firstDistance = new Map<number, number>();
  for (const edge of summary.edges) {
    firstDistance.set(edge.source, Math.min(firstDistance.get(edge.source) ?? Number.POSITIVE_INFINITY, edge.distance));
  }
  return summary.edges.filter((edge) => edge.distance <= (firstDistance.get(edge.source) ?? edge.distance) + 0.1);
}

function periodicGhosts(summary: GraphSummary, edges: GraphEdge[]) {
  const seen = new Set<string>();
  return edges.filter((edge) => {
    if (edge.image.every((value) => value === 0)) return false;
    const key = `${edge.target}:${edge.target_cartesian.map((value) => value.toFixed(5)).join(":")}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
