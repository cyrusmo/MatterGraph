import type { LeMaterialWorkflowSummary, Material, RankedRow, SimulationJob } from "../types/material";

const API = import.meta.env.VITE_API_URL || "";

export async function fetchMaterials(): Promise<Material[]> {
  const response = await fetch(`${API}/materials`);
  if (!response.ok) {
    throw new Error(await responseMessage(response, "materials request failed"));
  }
  return (await response.json()) as Material[];
}

export async function fetchLeMaterialWorkflow(): Promise<LeMaterialWorkflowSummary> {
  const response = await fetch(`${API}/workflows/lematerial/demo`);
  if (!response.ok) {
    throw new Error(await responseMessage(response, "workflow request failed"));
  }
  return (await response.json()) as LeMaterialWorkflowSummary;
}

export async function rankMaterials(
  objectives: Record<string, "minimize" | "maximize">,
  eahMax: number,
  densityMax: number
): Promise<RankedRow[]> {
  const response = await fetch(`${API}/scores/rank`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      objectives,
      constraints: {
        energy_above_hull: { max: eahMax },
        density: { max: densityMax },
      },
    }),
  });
  if (!response.ok) {
    throw new Error(await responseMessage(response, "rank request failed"));
  }
  return (await response.json()) as RankedRow[];
}

export async function runAseRelax(materialId: string): Promise<SimulationJob> {
  const response = await fetch(`${API}/simulations/ase/relax`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ material_id: materialId }),
  });
  if (!response.ok) {
    const message = await responseMessage(response, "ASE relaxation request failed");
    if (response.status === 503) {
      throw new Error(`ASE relaxation unavailable in this environment: ${message}`);
    }
    throw new Error(message);
  }
  return (await response.json()) as SimulationJob;
}

async function responseMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (body.detail) {
      return `${fallback}: ${String(body.detail)}`;
    }
  } catch {
    // Fall through to the status text.
  }
  return `${fallback}: ${response.status}`;
}
