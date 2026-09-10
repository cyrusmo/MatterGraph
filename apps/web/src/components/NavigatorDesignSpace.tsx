import { useEffect, useMemo, useRef, useState } from "react";

import type { CandidateEvaluation, CandidateStatus } from "../types/navigator";

type Props = {
  candidates: CandidateEvaluation[];
  selectedId: string | null;
  onSelect: (materialId: string) => void;
};

type Point = {
  candidate: CandidateEvaluation;
  x: number;
  y: number;
};

const STATUS_COLOR: Record<CandidateStatus, string> = {
  pass: "#5cc58a",
  fail: "#e36d6d",
  unknown: "#f0bc5e",
};

export function NavigatorDesignSpace({ candidates, selectedId, onSelect }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(640);
  const plotted = useMemo(() => candidates.filter((candidate) => (
    finiteNumber(candidate.properties.density) !== null
    && finiteNumber(candidate.properties.nsites) !== null
  )), [candidates]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(() => setWidth(Math.max(320, canvas.clientWidth)));
    observer.observe(canvas);
    setWidth(Math.max(320, canvas.clientWidth));
    return () => observer.disconnect();
  }, []);

  const points = useMemo(() => scalePoints(plotted, width, 320), [plotted, width]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = width * ratio;
    canvas.height = 320 * ratio;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.scale(ratio, ratio);
    drawPlot(context, points, selectedId, width, 320);
  }, [points, selectedId, width]);

  function pick(clientX: number, clientY: number) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const bounds = canvas.getBoundingClientRect();
    const x = clientX - bounds.left;
    const y = clientY - bounds.top;
    const nearest = points
      .map((point) => ({ point, distance: Math.hypot(point.x - x, point.y - y) }))
      .sort((left, right) => left.distance - right.distance)[0];
    if (nearest && nearest.distance <= 12) onSelect(nearest.point.candidate.material_id);
  }

  function moveSelection(direction: number) {
    if (!plotted.length) return;
    const current = plotted.findIndex((candidate) => candidate.material_id === selectedId);
    const next = current < 0 ? 0 : (current + direction + plotted.length) % plotted.length;
    onSelect(plotted[next].material_id);
  }

  return (
    <div className="navigator-plot-shell">
      <canvas
        ref={canvasRef}
        className="navigator-plot"
        height={320}
        role="img"
        tabIndex={0}
        aria-label={`Candidate design space: density versus site count for ${plotted.length} records. Use the candidate table for complete accessible data.`}
        onClick={(event) => pick(event.clientX, event.clientY)}
        onKeyDown={(event) => {
          if (event.key === "ArrowRight" || event.key === "ArrowDown") {
            event.preventDefault();
            moveSelection(1);
          }
          if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
            event.preventDefault();
            moveSelection(-1);
          }
        }}
      />
      <div className="navigator-plot-legend" aria-hidden="true">
        <span><i className="legend-mark pass" />passes</span>
        <span><i className="legend-mark fail" />fails</span>
        <span><i className="legend-mark unknown" />evidence unknown</span>
      </div>
      <p className="navigator-plot-note">
        Density (g/cm³) × site count. Shape and color both encode status; the table below is the
        accessible source of record.
      </p>
    </div>
  );
}

function scalePoints(
  candidates: CandidateEvaluation[],
  width: number,
  height: number,
): Point[] {
  const margin = { left: 54, right: 20, top: 20, bottom: 44 };
  const densities = candidates.map((candidate) => Number(candidate.properties.density));
  const sites = candidates.map((candidate) => Number(candidate.properties.nsites));
  const xDomain = paddedDomain(densities);
  const yDomain = paddedDomain(sites);
  return candidates.map((candidate) => ({
    candidate,
    x: margin.left + (
      (Number(candidate.properties.density) - xDomain[0]) / (xDomain[1] - xDomain[0])
    ) * (width - margin.left - margin.right),
    y: height - margin.bottom - (
      (Number(candidate.properties.nsites) - yDomain[0]) / (yDomain[1] - yDomain[0])
    ) * (height - margin.top - margin.bottom),
  }));
}

function drawPlot(
  context: CanvasRenderingContext2D,
  points: Point[],
  selectedId: string | null,
  width: number,
  height: number,
) {
  context.clearRect(0, 0, width, height);
  context.fillStyle = "rgba(5, 9, 14, 0.58)";
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "rgba(112, 146, 184, 0.22)";
  context.lineWidth = 1;
  for (let index = 0; index <= 4; index += 1) {
    const x = 54 + index * (width - 74) / 4;
    const y = 20 + index * (height - 64) / 4;
    context.beginPath(); context.moveTo(x, 20); context.lineTo(x, height - 44); context.stroke();
    context.beginPath(); context.moveTo(54, y); context.lineTo(width - 20, y); context.stroke();
  }
  context.fillStyle = "#96a6b8";
  context.font = "11px Inter, sans-serif";
  context.fillText("density (g/cm³) →", Math.max(54, width / 2 - 42), height - 12);
  context.save();
  context.translate(14, height / 2 + 38);
  context.rotate(-Math.PI / 2);
  context.fillText("site count →", 0, 0);
  context.restore();

  for (const point of points) {
    const { status } = point.candidate;
    context.strokeStyle = STATUS_COLOR[status];
    context.fillStyle = STATUS_COLOR[status];
    context.lineWidth = 1.5;
    if (status === "pass") {
      context.beginPath(); context.arc(point.x, point.y, 4, 0, Math.PI * 2); context.fill();
    } else if (status === "fail") {
      context.beginPath();
      context.moveTo(point.x - 4, point.y - 4); context.lineTo(point.x + 4, point.y + 4);
      context.moveTo(point.x + 4, point.y - 4); context.lineTo(point.x - 4, point.y + 4);
      context.stroke();
    } else {
      context.beginPath();
      context.moveTo(point.x, point.y - 5);
      context.lineTo(point.x + 5, point.y + 4);
      context.lineTo(point.x - 5, point.y + 4);
      context.closePath(); context.stroke();
    }
    if (point.candidate.material_id === selectedId) {
      context.strokeStyle = "#e8edf2";
      context.lineWidth = 2;
      context.beginPath(); context.arc(point.x, point.y, 9, 0, Math.PI * 2); context.stroke();
    }
  }
}

function paddedDomain(values: number[]): [number, number] {
  if (!values.length) return [0, 1];
  const low = Math.min(...values);
  const high = Math.max(...values);
  if (low === high) return [low - 0.5, high + 0.5];
  const padding = (high - low) * 0.08;
  return [low - padding, high + padding];
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
