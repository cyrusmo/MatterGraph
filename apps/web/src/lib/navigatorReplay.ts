import type { ConstraintPlan, EvaluationResult, RelaxationResult } from "../types/navigator";

const DATABASE = "mattergraph-navigator";
const STORE = "private-replays";

export async function savePrivateNavigatorReplay(
  plan: ConstraintPlan,
  evaluation: EvaluationResult,
  recoveries: RelaxationResult | null,
): Promise<string> {
  const canonical = canonicalJson({
    plan,
    evaluation,
    recoveries,
    versions: {
      index_id: evaluation.index_id,
      registry_version: evaluation.registry_version,
      engine_version: evaluation.engine_version,
    },
  });
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical));
  const replayId = `local-${hex(digest)}`;
  const database = await openDatabase();
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(STORE, "readwrite");
    transaction.objectStore(STORE).put({
      replay_id: replayId,
      confirmed_plan: plan,
      result: evaluation,
      recoveries,
      created_at: new Date().toISOString(),
      privacy: "Client-local confirmed plan and deterministic results; no raw prompt or provider output.",
    });
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  database.close();
  return replayId;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) {
        request.result.createObjectStore(STORE, { keyPath: "replay_id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function canonicalJson(value: unknown): string {
  return JSON.stringify(sortValue(value));
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, sortValue(item)]),
    );
  }
  return value;
}

function hex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer), (value) => value.toString(16).padStart(2, "0")).join("");
}
