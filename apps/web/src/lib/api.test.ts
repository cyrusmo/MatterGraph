import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiUnavailableError,
  fetchMaterials,
  fetchPreflight,
  importDataset,
  inspectDataset,
  rankMaterialsAudit,
} from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("demo API client", () => {
  it("loads preflight from the same-origin demo endpoint", async () => {
    const payload = {
      status: "ready",
      fixture: { path: "fixture.json", kind: "fixture", disclaimer: "demo" },
      record_count: 24,
      graph: { included_count: 24, excluded_count: 0, invalid_count: 0, validation_state: "valid" },
      ranking: {
        ranked_count: 3,
        excluded_by_constraints: 1,
        binary_normalization: false,
        objectives: {},
        constraints: {},
      },
      default_material_id: "agm003273599",
      chgnet: { state: "cached_only", reference_available: true },
      simulation_targets: {},
      checks: [],
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchPreflight()).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "/demo/preflight",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("stops waiting after five seconds and reports an offline API", async () => {
    vi.stubGlobal("setTimeout", (callback: () => void) => {
      queueMicrotask(callback);
      return 1;
    });
    vi.stubGlobal("clearTimeout", vi.fn());
    const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("Aborted", "AbortError"));
        });
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = fetchPreflight();
    const result = request.catch((error: unknown) => error);
    const error = await result;
    expect(error).toBeInstanceOf(ApiUnavailableError);
    expect(error).toHaveProperty("message", expect.stringContaining("timed out after five seconds"));
  });

  it("sends weights, directions, constraints, and missing policy to the audited route", async () => {
    const response = { ranked: [], report: {}, request: {} };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await rankMaterialsAudit(
      {
        density: { direction: "minimize", weight: 0.6 },
        energy_above_hull: { direction: "minimize", weight: 0.4 },
      },
      0.05,
      0.2,
      "worst",
    );

    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock.mock.calls[0][0]).toBe("/scores/rank/audit");
    expect(JSON.parse(String(init?.body))).toEqual({
      objectives: {
        density: { direction: "minimize", weight: 0.6 },
        energy_above_hull: { direction: "minimize", weight: 0.4 },
      },
      constraints: {
        energy_above_hull: { max: 0.05 },
        max_force: { max: 0.2 },
      },
      missing: "worst",
    });
  });

  it("scopes material requests to an explicitly selected local dataset", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchMaterials("mg_ds_example");

    expect(fetchMock.mock.calls[0][0]).toBe("/materials?dataset_id=mg_ds_example");
  });

  it("keeps inspect non-registering and sends explicit import policy plus mapping", async () => {
    const inspection = {
      status: "ready",
      checksum: "a".repeat(64),
      row_count: 1,
      accepted_count: 1,
      rejected_count: 0,
      columns: ["id", "formula", "density"],
      inferred_mapping: {
        identity_column: "id",
        formula_column: "formula",
        structure_column: null,
        source_id_column: null,
        property_columns: [
          { column: "density", name: "density", unit: null, source: "local_file", method: "unknown" },
        ],
      },
      issues: [],
      issue_counts: {},
      truncated_issue_count: 0,
    };
    const imported = {
      dataset_id: "mg_ds_example",
      manifest: {},
      accepted_count: 1,
      rejected_count: 0,
      issues: [],
      issue_counts: {},
      truncated_issue_count: 0,
      preview: [],
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(inspection), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(imported), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const file = { filename: "one.csv", format: "csv" as const, content: "id,formula\na,AlN\n" };

    const report = await inspectDataset(file);
    await importDataset({
      ...file,
      mapping: report.inferred_mapping!,
      error_policy: "skip_invalid_rows",
    });

    expect(fetchMock.mock.calls[0][0]).toBe("/datasets/inspect");
    expect(fetchMock.mock.calls[1][0]).toBe("/datasets/import");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      filename: "one.csv",
      error_policy: "skip_invalid_rows",
      mapping: { identity_column: "id" },
    });
  });
});
