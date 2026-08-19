import { expect, test } from "@playwright/test";

const LOCAL_JSONL = `${JSON.stringify({
  material_id: "local-aln",
  formula: "AlN",
  structure: {
    lattice: [[3.11, 0, 0], [-1.555, 2.693, 0], [0, 0, 4.98]],
    species: ["Al", "Al", "N", "N"],
    coords: [
      [1 / 3, 2 / 3, 0],
      [2 / 3, 1 / 3, 0.5],
      [1 / 3, 2 / 3, 0.382],
      [2 / 3, 1 / 3, 0.882],
    ],
  },
  properties: [
    { name: "density", value: 3.26, unit: "g/cm^3", source: "contributor" },
  ],
})}\n`;

test("preserves the five-screen SPC presentation and keyboard flow", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Which lightweight, near-hull nitride")).toBeVisible();
  await expect(page.getByText("24", { exact: true }).first()).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByText("02 / 05 · Reconstructed structure")).toBeVisible();
  await page.getByRole("button", { name: /03 Periodic graph/ }).click();
  await expect(page.getByText(/Exact graph geometry/)).toBeVisible();
  await expect(page.locator(".crystal-viewport canvas, .webgl-fallback")).toBeVisible();
  await page.getByRole("button", { name: /05 ML evidence/ }).click();
  await expect(page.locator(".ml-boundary")).toContainText(
    "not a DFT or experimental measurement",
  );
});

test("imports a local dataset through graph, ranking, export, and fixture boundary", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Local workbench" }).click();
  await expect(page.getByRole("heading", { name: /Inspect local materials data/ })).toBeVisible();
  await page.getByTestId("local-file-input").setInputFiles({
    name: "contributor.jsonl",
    mimeType: "application/x-ndjson",
    buffer: Buffer.from(LOCAL_JSONL),
  });
  await page.getByRole("button", { name: "Inspect columns" }).click();
  await expect(page.getByText(/Inspected 1 rows/)).toBeVisible();
  await page.getByRole("button", { name: "Import ephemeral dataset" }).click();
  await expect(page.getByText("1 local records ready.")).toBeVisible();
  await expect(page.getByRole("button", { name: "local-aln" })).toBeVisible();
  await expect(page.locator(".crystal-viewport canvas, .webgl-fallback")).toBeVisible();

  await page.getByLabel("Objective").selectOption("density");
  await page.getByRole("button", { name: "Run transparent scorecard" }).click();
  await expect(page.getByText(/Scores are pool-relative/)).toBeVisible();
  await expect(page.getByText("Bundled AlN reference not applicable")).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export normalized JSONL" }).click();
  expect((await download).suggestedFilename()).toMatch(/mg_ds_.*\.jsonl/);
  await page.getByRole("button", { name: "Reset local dataset" }).click();
  await expect(page.getByText("Which lightweight, near-hull nitride")).toBeVisible();
});

test("keeps graph evidence usable when WebGL is unavailable", async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function patchedGetContext(type, ...args) {
      if (String(type).includes("webgl")) return null;
      return original.call(this, type, ...args);
    } as typeof HTMLCanvasElement.prototype.getContext;
  });
  await page.goto("/");
  await page.getByRole("button", { name: /03 Periodic graph/ }).click();
  await expect(page.getByText("WebGL is unavailable. Geometry metadata and validation remain available.")).toBeVisible();
  await expect(page.getByText("Graph validation")).toBeVisible();
});

test("recovers from an offline preflight with one retry", async ({ page }) => {
  await page.route("**/demo/preflight", async (route) => {
    await route.fulfill({ status: 503, body: '{"detail":"temporarily offline"}' });
  });
  await page.goto("/");
  await expect(page.getByText("Demo API offline")).toBeVisible();
  await page.unroute("**/demo/preflight");
  await page.getByRole("button", { name: "Retry preflight" }).click();
  await expect(page.locator(".tag.pass", { hasText: "ready" })).toBeVisible();
});
