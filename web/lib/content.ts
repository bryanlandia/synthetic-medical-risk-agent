/** The committed content the page shows, read on the server. */
import fs from "node:fs";
import path from "node:path";
import type { DemoPatient } from "./types";

const dir = path.join(process.cwd(), "content");

export function demoPatients(): DemoPatient[] {
  return JSON.parse(fs.readFileSync(path.join(dir, "demo_patients.json"), "utf8")).patients as DemoPatient[];
}

/** The model card without its metadata block, and the model hash on its "Model hash" line. */
export function modelCard(): { body: string; hash: string | null } {
  const text = fs.readFileSync(path.join(dir, "model-card.md"), "utf8");
  const body = text.startsWith("---\n") ? text.slice(text.indexOf("\n---\n", 4) + 5).trimStart() : text;
  const hash = /\*\*Model hash:\*\* `([0-9a-f]{64})`/.exec(body)?.[1] ?? null;
  return { body, hash };
}
