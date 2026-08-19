import type {
  Capability,
  ChgnetReference,
  DemoPreflight,
  DatasetImportMapping,
  DatasetList,
  ImportReport,
  ImportResult,
  GraphSummary,
  LeMaterialWorkflowSummary,
  Material,
  ScoreAudit,
  SlicePreview,
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

export async function fetchMaterials(datasetId?: string): Promise<Material[]> {
  return requestJson<Material[]>(
    withDataset("/materials", datasetId),
    {},
    "materials request failed",
  );
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

export async function fetchGraphSummary(
  materialId: string,
  datasetId?: string,
): Promise<GraphSummary> {
  return requestJson<GraphSummary>(
    withDataset(`/materials/${encodeURIComponent(materialId)}/graph-summary`, datasetId),
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
  forceMax: number,
  missing: "worst" | "neutral" | "exclude",
  datasetId?: string,
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
          max_force: { max: forceMax },
        },
        missing,
        ...(datasetId ? { dataset_id: datasetId } : {}),
      }),
    },
    "rank request failed",
  );
}

export async function rankDatasetAudit(
  datasetId: string,
  objectives: Record<string, { direction: "minimize" | "maximize"; weight: number }>,
  missing: "worst" | "neutral" | "exclude" = "worst",
): Promise<ScoreAudit> {
  return requestJson<ScoreAudit>(
    "/scores/rank/audit",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_id: datasetId, objectives, constraints: {}, missing }),
    },
    "local rank request failed",
  );
}

export async function inspectDataset(input: {
  filename: string;
  format: "csv" | "jsonl";
  content: string;
}): Promise<ImportReport> {
  return requestJson<ImportReport>(
    "/datasets/inspect",
    jsonPost(input),
    "dataset inspection failed",
  );
}

export async function importDataset(input: {
  filename: string;
  format: "csv" | "jsonl";
  content: string;
  mapping: DatasetImportMapping;
  error_policy: "reject_file" | "skip_invalid_rows";
}): Promise<ImportResult> {
  return requestJson<ImportResult>(
    "/datasets/import",
    jsonPost(input),
    "dataset import failed",
  );
}

export async function fetchDatasets(): Promise<DatasetList> {
  return requestJson<DatasetList>("/datasets", {}, "dataset registry request failed");
}

export async function deleteDataset(datasetId: string): Promise<void> {
  await requestJson(
    `/datasets/${encodeURIComponent(datasetId)}`,
    { method: "DELETE" },
    "dataset reset failed",
  );
}

export async function fetchSlicePreview(
  datasetId: string,
  request: {
    include_elements: string[];
    exclude_elements: string[];
    max_nsites?: number;
    max_nelements?: number;
    target?: string;
  },
): Promise<SlicePreview> {
  return requestJson<SlicePreview>(
    `/datasets/${encodeURIComponent(datasetId)}/slices/preview`,
    jsonPost(request),
    "slice preview failed",
  );
}

export async function exportDataset(datasetId: string): Promise<Blob> {
  const response = await requestRaw(
    `/datasets/${encodeURIComponent(datasetId)}/export?format=jsonl`,
    {},
    "dataset export failed",
  );
  return response.blob();
}

export async function fetchChgnetReference(materialId: string): Promise<ChgnetReference> {
  return requestJson<ChgnetReference>(
    `/simulations/chgnet/reference/${encodeURIComponent(materialId)}`,
    {},
    "CHGNet reference request failed",
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
  const response = await requestRaw(path, init, fallback);
  return (await response.json()) as T;
}

async function requestRaw(
  path: string,
  init: RequestInit,
  fallback: string,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API}${path}`, { ...init, signal: controller.signal });
    if (!response.ok) {
      throw new HttpError(await responseMessage(response, fallback), response.status);
    }
    return response;
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

function withDataset(path: string, datasetId?: string): string {
  return datasetId ? `${path}?dataset_id=${encodeURIComponent(datasetId)}` : path;
}

function jsonPost(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
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
