import { defineConfig } from "@playwright/test";
import os from "node:os";
import path from "node:path";

export const AGENT_PORT = 8765;
export const WEB_PORT = 3200;
export const SECRET = "e2e-secret-value-7788";
export const STUB_PORT = 8799;
export const ANALYTICS_PORT = 3201;
const spendDb = path.join(os.tmpdir(), `web-e2e-spend-${process.pid}.db`);
const run = (dist: string) => (process.env.PW_USE_DEV ? `NEXT_DIST_DIR=${dist} npx next dev` : `NEXT_DIST_DIR=${dist} npm run build && NEXT_DIST_DIR=${dist} npx next start`);

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
      command: `${run(".next")} -H 127.0.0.1 -p ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 240_000,
      // no analytics key: this build must count nothing
      env: { AGENT_URL: `http://127.0.0.1:${AGENT_PORT}`, AGENT_SHARED_SECRET: SECRET, NEXT_PUBLIC_POSTHOG_KEY: "", PATH: process.env.PATH ?? "" },
    },
    {
      command: `node tests/stub-posthog.mjs`,
      url: `http://127.0.0.1:${STUB_PORT}/__requests`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: { STUB_PORT: String(STUB_PORT), PATH: process.env.PATH ?? "" },
    },
    {
      // the same app built with analytics on, pointing at the stub instead of PostHog
      command: `${run(".next-analytics")} -H 127.0.0.1 -p ${ANALYTICS_PORT}`,
      url: `http://127.0.0.1:${ANALYTICS_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 240_000,
      env: {
        AGENT_URL: `http://127.0.0.1:${AGENT_PORT}`, AGENT_SHARED_SECRET: SECRET, PATH: process.env.PATH ?? "",
        NEXT_PUBLIC_POSTHOG_KEY: "phc_test_key", NEXT_PUBLIC_POSTHOG_HOST: `http://127.0.0.1:${STUB_PORT}`,
      },
    },
  ],
});
