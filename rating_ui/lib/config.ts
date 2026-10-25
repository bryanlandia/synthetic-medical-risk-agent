import path from "node:path";
import type { RaterKind } from "./types";

export const NOTICE =
  "ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.";

export interface Config {
  roundDir: string;
  kind: RaterKind;
  fixedRater: string | null;
  modelId: string | null;
  promptVersion: string | null;
}

/** Read at request time so tests can point the app at a different round. The rater kind comes from here
 *  (the launch environment) and never from a request. */
export function config(): Config {
  const dir = process.env.REALISM_ROUND_DIR;
  if (!dir) throw new Error("REALISM_ROUND_DIR must point at a round directory containing sheet.json");
  const kind = (process.env.RATER_KIND ?? "human") as RaterKind;
  if (kind !== "human" && kind !== "llm") throw new Error(`RATER_KIND must be human or llm, got ${kind}`);
  const fixedRater = process.env.RATER_NAME?.trim() || null;
  const modelId = process.env.RATER_MODEL_ID?.trim() || null;
  const promptVersion = process.env.RATER_PROMPT_VERSION?.trim() || null;
  if (kind === "llm" && !(fixedRater && modelId && promptVersion)) {
    throw new Error("an llm session needs RATER_NAME, RATER_MODEL_ID and RATER_PROMPT_VERSION");
  }
  return { roundDir: path.resolve(dir), kind, fixedRater, modelId, promptVersion };
}
