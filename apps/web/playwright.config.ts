import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:5193",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "MATTERGRAPH_API_PORT=8013 MATTERGRAPH_WEB_PORT=5193 ../../scripts/run_public_demo.sh",
    url: "http://127.0.0.1:5193",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "chromium-narrow",
      use: { ...devices["Desktop Chrome"], viewport: { width: 833, height: 965 } },
    },
  ],
});
