import { defineConfig } from "@playwright/test";
import os from "node:os";
import path from "node:path";

export const AGENT_PORT = 8765;
export const WEB_PORT = 3200;
export const SECRET = "e2e-secret-value-7788";
const spendDb = path.join(os.tmpdir(), `web-e2e-spend-${process.pid}.db`);
const dev = process.env.PW_USE_DEV ? "npx next dev" : "npm run build && npx next start";

// The agent runs with the scripted model: no API key, no network, no spend. The web server is the production build.
export default defineConfig({
  testDir: "./tests",
  testMatch: /.*\.spec\.ts/,
  workers: 1,
  timeout: 30_000,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${WEB_PORT}`, trace: "retain-on-failure" },
  webServer: [
    {
      command: `cd ../agent && uv run agent serve --port ${AGENT_PORT}`,
      url: `http://127.0.0.1:${AGENT_PORT}/healthz`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        AGENT_ENV: "test",
        AGENT_SCRIPTED_MODEL: "1",
        AGENT_RELAX_LIMITS: "1",
        AGENT_SHARED_SECRET: SECRET,
        AGENT_SPEND_DB: spendDb,
        PATH: process.env.PATH ?? "",
      },
    },
    {
      command: `${dev} -H 127.0.0.1 -p ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 240_000,
      env: { AGENT_URL: `http://127.0.0.1:${AGENT_PORT}`, AGENT_SHARED_SECRET: SECRET, PATH: process.env.PATH ?? "" },
    },
  ],
});
