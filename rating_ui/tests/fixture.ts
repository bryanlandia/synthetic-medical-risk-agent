import fs from "node:fs";
import path from "node:path";

export const ROUND_DIR = path.resolve(__dirname, "../test-results/fixture-round");
export const KEY_SENTINEL = "KEY-SENTINEL-DO-NOT-SERVE-7f3a";
export const NOTE_IDS = ["n01", "n02", "n03", "n04", "n05", "n06"];

/** A tiny blind round: sheet.json plus a key.json whose contents must never be served. */
export function makeFixtureRound(): void {
  fs.rmSync(ROUND_DIR, { recursive: true, force: true });
  fs.mkdirSync(ROUND_DIR, { recursive: true });
  const sheet = {
    version: 1,
    notice: "ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use.",
    symptom_keys: ["tremor", "fatigue", "photophobia", "joint_stiffness", "dizziness"],
    plausible_values: ["y", "n"],
    symptom_values: ["present", "possible", "absent", "none"],
    notes: NOTE_IDS.map((id) => ({ id, text: `Synthetic follow-up note ${id}.\nDenies tremor. Reports fatigue.` })),
  };
  fs.writeFileSync(path.join(ROUND_DIR, "sheet.json"), JSON.stringify(sheet, null, 2));
  fs.writeFileSync(path.join(ROUND_DIR, "key.json"), JSON.stringify({ secret: KEY_SENTINEL }));
}

export function readRatingFile(name: string): any {
  return JSON.parse(fs.readFileSync(path.join(ROUND_DIR, `ratings.${name}.json`), "utf8"));
}
