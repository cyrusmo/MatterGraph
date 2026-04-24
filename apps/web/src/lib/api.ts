import type { Material, RankedRow } from "../types/material";

const API = import.meta.env.VITE_API_URL || "";

export async function fetchMaterials(): Promise<Material[]> {
  const response = await fetch(`${API}/materials`);
  if (!response.ok) {
    throw new Error(`materials request failed: ${response.status}`);
  }
  return (await response.json()) as Material[];
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
    throw new Error(`rank request failed: ${response.status}`);
  }
  return (await response.json()) as RankedRow[];
}
