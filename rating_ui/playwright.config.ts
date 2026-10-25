import { defineConfig } from "@playwright/test";
import { makeFixtureRound, ROUND_DIR } from "./tests/fixture";

makeFixtureRound();

const HUMAN_PORT = 3101;
const LLM_PORT = 3102;
const build = process.env.PW_USE_DEV ? "" : "npm run build && ";
const run = process.env.PW_USE_DEV ? "npx next dev" : "npx next start";

export default defineConfig({
  testDir: "./tests",
  testMatch: /.*\.spec\.ts/,
  workers: 1,
  timeout: 30_000,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${HUMAN_PORT}`, trace: "retain-on-failure" },
  webServer: [
    {
      command: `${build}${run} -H 127.0.0.1 -p ${HUMAN_PORT}`,
      url: `http://127.0.0.1:${HUMAN_PORT}/api/session`,
      reuseExistingServer: false,
      timeout: 180_000,
      env: { REALISM_ROUND_DIR: ROUND_DIR, RATER_KIND: "human" },
    },
    {
      command: `${run} -H 127.0.0.1 -p ${LLM_PORT}`,
      url: `http://127.0.0.1:${LLM_PORT}/api/session`,
      reuseExistingServer: false,
      timeout: 180_000,
      env: {
        REALISM_ROUND_DIR: ROUND_DIR,
        RATER_KIND: "llm",
        RATER_NAME: "test-reviewer",
        RATER_MODEL_ID: "claude-sonnet-5-5",
        RATER_PROMPT_VERSION: "1",
      },
    },
  ],
});
