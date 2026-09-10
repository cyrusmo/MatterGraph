import { expect, test } from "@playwright/test";

test("executes the grounded navigator golden loop", async ({ page }) => {
  const externalRequests: string[] = [];
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) externalRequests.push(request.url());
  });
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/?view=navigator");
  await expect(page.getByRole("heading", { name: "Navigate a real crystal design space." })).toBeVisible();
  await expect(page.getByText("24 frozen records")).toBeVisible();
  await page.getByRole("button", { name: "Compile request" }).click();
  await expect(page.getByText(/proposed · 0 unresolved/)).toBeVisible();
  await page.getByRole("button", { name: "Confirm all interpretations" }).click();
  await page.getByRole("button", { name: "Execute confirmed plan" }).click();

  await expect(page.getByText("Feasible indexed set")).toBeVisible();
  await expect(page.locator(".navigator-plot")).toBeVisible();
  await expect(page.locator(".navigator-candidate-table")).toBeVisible();
  await expect(page.locator(".navigator-inspector").getByText("pass", { exact: true }).first()).toBeVisible();
  await expect(page.locator(".navigator-crystal-viewport canvas, .navigator-crystal-viewport + .empty-note")).toBeVisible();
  await expect(page.getByText("No bonds or neighbor chemistry are inferred.")).toBeVisible();
  if (process.env.MATTERGRAPH_CAPTURE_EVIDENCE) {
    await page.screenshot({ path: "../../output/playwright/navigator-golden-desktop.png", fullPage: true });
  }
  expect(externalRequests).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test("keeps conflict, capability, evidence, and no-feasible recovery distinct", async ({ page }) => {
  await page.goto("/?view=navigator");
  const request = page.getByLabel("Describe the indexed material requirements");

  await request.fill("Find a nitride with density below 0.01 g/cm3.");
  await page.getByRole("button", { name: "Compile request" }).click();
  await page.getByRole("button", { name: "Confirm all interpretations" }).click();
  await page.getByRole("button", { name: "Execute confirmed plan" }).click();
  await expect(page.getByText("No feasible indexed candidate")).toBeVisible();
  await expect(page.getByText("Physical / categorical changes")).toBeVisible();
  await expect(page.getByText(/relative to demo_snapshot_v1/).first()).toBeVisible();

  await request.fill("Require SCAN and corrosion resistance.");
  await page.getByRole("button", { name: "Compile request" }).click();
  await page.getByRole("button", { name: "Confirm all interpretations" }).click();
  await page.getByRole("button", { name: "Execute confirmed plan" }).click();
  await expect(page.getByText("Index capability mismatch")).toBeVisible();
  await expect(page.getByText("Keep as unevaluated")).toBeVisible();

  await request.fill("Find a material with magnetization below 0.1 μB.");
  await page.getByRole("button", { name: "Compile request" }).click();
  await page.getByRole("button", { name: "Confirm all interpretations" }).click();
  await page.getByRole("button", { name: "Execute confirmed plan" }).click();
  await expect(page.getByText("Required evidence unknown")).toBeVisible();
  await expect(page.getByText("Require reported evidence")).toBeVisible();
  if (process.env.MATTERGRAPH_CAPTURE_EVIDENCE) {
    await page.screenshot({ path: "../../output/playwright/navigator-evidence-unknown.png", fullPage: true });
  }
});

for (const viewport of [
  { name: "desktop", width: 1440, height: 900 },
  { name: "narrow", width: 860, height: 851 },
  { name: "mobile", width: 585, height: 851 },
]) {
  test(`navigator has no viewport overflow at ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto("/?view=navigator");
    await page.getByRole("button", { name: "Compile request" }).click();
    await page.getByRole("button", { name: "Confirm all interpretations" }).click();
    await page.getByRole("button", { name: "Execute confirmed plan" }).click();
    await expect(page.getByText("Feasible indexed set")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    if (process.env.MATTERGRAPH_CAPTURE_EVIDENCE) {
      await expect(page.getByText("No bonds or neighbor chemistry are inferred.")).toBeVisible();
      await page.screenshot({ path: `../../output/playwright/navigator-${viewport.name}.png`, fullPage: true });
    }
  });
}
