import type {
  Capability,
  DemoPreflight,
  GraphSummary,
  LeMaterialWorkflowSummary,
  Material,
  ScoreAudit,
  SimulationJob,
} from "../types/material";

const API = import.meta.env.VITE_API_URL || "";
const REQUEST_TIMEOUT_MS = 5_000;

export class ServiceUnavailableError extends Error {}
export class ApiUnavailableError extends Error {}

class HttpError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

export async function fetchMaterials(): Promise<Material[]> {
  return requestJson<Material[]>("/materials", {}, "materials request failed");
}

export async function fetchLeMaterialWorkflow(): Promise<LeMaterialWorkflowSummary> {
  return requestJson<LeMaterialWorkflowSummary>(
    "/workflows/lematerial/demo",
    {},
    "workflow request failed",
  );
}

export async function fetchPreflight(): Promise<DemoPreflight> {
  return requestJson<DemoPreflight>("/demo/preflight", {}, "demo preflight failed");
}

export async function fetchCapabilities(): Promise<Capability[]> {
  const response = await requestJson<{ capabilities: Capability[] }>(
    "/capabilities",
    {},
    "capability request failed",
  );
  return response.capabilities;
}

export async function fetchGraphSummary(materialId: string): Promise<GraphSummary> {
  return requestJson<GraphSummary>(
    `/materials/${encodeURIComponent(materialId)}/graph-summary`,
    {},
    "graph summary failed",
  );
}

export async function rankMaterialsAudit(
  objectives: Record<
    string,
    { direction: "minimize" | "maximize"; weight: number }
  >,
  eahMax: number,
  densityMax: number,
  missing: "worst" | "neutral" | "exclude",
): Promise<ScoreAudit> {
  return requestJson<ScoreAudit>(
    "/scores/rank/audit",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        objectives,
        constraints: {
          energy_above_hull: { max: eahMax },
          density: { max: densityMax },
        },
        missing,
      }),
    },
    "rank request failed",
  );
}

export async function runAseRelax(materialId: string): Promise<SimulationJob> {
  try {
    return await requestJson<SimulationJob>(
      "/simulations/ase/relax",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ material_id: materialId }),
      },
      "ASE relaxation request failed",
    );
  } catch (error) {
    if (error instanceof HttpError && error.status === 503) {
      throw new ServiceUnavailableError(
        `ASE relaxation unavailable in this environment: ${error.message}`,
      );
    }
    throw error;
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  fallback: string,
): Promise<T> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API}${path}`, { ...init, signal: controller.signal });
    if (!response.ok) {
      throw new HttpError(await responseMessage(response, fallback), response.status);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof HttpError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiUnavailableError(`${fallback}: timed out after five seconds`);
    }
    throw new ApiUnavailableError(
      `${fallback}: ${error instanceof Error ? error.message : String(error)}`,
    );
  } finally {
    globalThis.clearTimeout(timeout);
  }
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
