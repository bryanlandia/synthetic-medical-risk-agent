import fs from "node:fs/promises";
import { config } from "./config";
import { ratingPath, sheetPath } from "./guard";
import {
  PLAUSIBLE_VALUES,
  SYMPTOM_KEYS,
  SYMPTOM_VALUES,
  type NoteRating,
  type RatingFile,
  type Sheet,
} from "./types";

export class BadRequest extends Error {}

export async function readSheet(): Promise<Sheet> {
  const text = await fs.readFile(sheetPath(config().roundDir), "utf8");
  return JSON.parse(text) as Sheet;
}

export async function readRatings(rater: string): Promise<RatingFile | null> {
  const cfg = config();
  try {
    return JSON.parse(await fs.readFile(ratingPath(cfg.roundDir, rater), "utf8")) as RatingFile;
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw err;
  }
}

/** Check one note's rating. Unknown fields are dropped, bad values rejected. */
export function cleanRating(input: unknown): NoteRating {
  if (typeof input !== "object" || input === null) throw new BadRequest("rating must be an object");
  const r = input as Record<string, unknown>;
  const plausible = r.plausible ?? null;
  if (plausible !== null && !(PLAUSIBLE_VALUES as readonly unknown[]).includes(plausible)) {
    throw new BadRequest("plausible must be y or n");
  }
  const symptoms: NoteRating["symptoms"] = {};
  const given = (r.symptoms ?? {}) as Record<string, unknown>;
  for (const k of Object.keys(given)) {
    if (!(SYMPTOM_KEYS as readonly string[]).includes(k)) throw new BadRequest(`unknown symptom ${k}`);
    const v = given[k] ?? null;
    if (v !== null && !(SYMPTOM_VALUES as readonly unknown[]).includes(v)) {
      throw new BadRequest(`${k} must be one of ${SYMPTOM_VALUES.join(", ")}`);
    }
    symptoms[k as (typeof SYMPTOM_KEYS)[number]] = v as never;
  }
  const comment = typeof r.comment === "string" ? r.comment.slice(0, 2000) : "";
  const reason = typeof r.reason === "string" ? r.reason.slice(0, 500) : "";
  return { plausible: plausible as NoteRating["plausible"], symptoms, comment, reason };
}

let queue: Promise<unknown> = Promise.resolve();

/** Save one note's rating into the rater's file. Writes are serialised and atomic (temp file, then rename),
 *  and the kind and model are taken from the launch configuration, never from the request. */
export function saveRating(rater: string, noteId: string, input: unknown): Promise<RatingFile> {
  const run = queue.then(async () => {
    const cfg = config();
    const sheet = await readSheet();
    if (!sheet.notes.some((n) => n.id === noteId)) throw new BadRequest(`unknown note id ${noteId}`);
    const rating = cleanRating(input);
    const name = cfg.kind === "llm" ? (cfg.fixedRater as string) : rater;
    const file: RatingFile = (await readRatings(name)) ?? {
      version: 1,
      rater: name.trim(),
      kind: cfg.kind,
      model_id: cfg.modelId,
      prompt_version: cfg.promptVersion,
      ratings: {},
    };
    file.ratings[noteId] = rating;
    const target = ratingPath(cfg.roundDir, name);
    const tmp = `${target}.tmp`;
    await fs.writeFile(tmp, JSON.stringify(sortKeys(file), null, 2) + "\n");
    await fs.rename(tmp, target);
    return file;
  });
  queue = run.catch(() => undefined);
  return run;
}

function sortKeys(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(sortKeys);
  if (v && typeof v === "object") {
    return Object.fromEntries(
      Object.entries(v as Record<string, unknown>)
        .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
        .map(([k, val]) => [k, sortKeys(val)]),
    );
  }
  return v;
}
