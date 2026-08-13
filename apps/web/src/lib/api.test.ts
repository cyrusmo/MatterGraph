import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiUnavailableError, fetchPreflight, rankMaterialsAudit } from "./api";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("demo API client", () => {
  it("loads preflight from the same-origin demo endpoint", async () => {
    const payload = {
      status: "ready",
      fixture: { path: "fixture.json", kind: "fixture", disclaimer: "demo" },
      record_count: 4,
      graph: { included_count: 3, excluded_count: 1 },
      ranking: {
        ranked_count: 3,
        excluded_by_constraints: 1,
        binary_normalization: false,
        objectives: {},
        constraints: {},
      },
      default_material_id: "lemat-aln",
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
    vi.useFakeTimers();
    const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("Aborted", "AbortError"));
        });
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = fetchPreflight();
    const result = expect(request).rejects.toBeInstanceOf(ApiUnavailableError);
    await vi.advanceTimersByTimeAsync(5_000);
    await result;
    await expect(request).rejects.toThrow("timed out after five seconds");
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
        bulk_modulus: { direction: "maximize", weight: 0.4 },
      },
      0.025,
      6,
      "worst",
    );

    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock.mock.calls[0][0]).toBe("/scores/rank/audit");
    expect(JSON.parse(String(init?.body))).toEqual({
      objectives: {
        density: { direction: "minimize", weight: 0.6 },
        bulk_modulus: { direction: "maximize", weight: 0.4 },
      },
      constraints: {
        energy_above_hull: { max: 0.025 },
        density: { max: 6 },
      },
      missing: "worst",
    });
  });
});
