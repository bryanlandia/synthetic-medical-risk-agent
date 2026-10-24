import path from "node:path";

/** The only files this app may touch: the blind sheet (read) and rating files (read and write).
 *  The key file is not on the list, so no request can reach it. */
export class GuardError extends Error {}

/** Must match rater_slug in data_gen/llm/ratings.py: both sides name the file from the rater name. */
export function raterSlug(name: string): string {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^[-.]+|[-.]+$/g, "")
    .slice(0, 60);
  if (!slug) throw new GuardError("rater name has no usable characters");
  return slug;
}

export function sheetPath(roundDir: string): string {
  return guard(roundDir, "sheet.json");
}

export function ratingPath(roundDir: string, rater: string): string {
  return guard(roundDir, `ratings.${raterSlug(rater)}.json`);
}

const ALLOWED = /^(sheet\.json|ratings\.[a-z0-9._-]+\.json)$/;

function guard(roundDir: string, name: string): string {
  if (!ALLOWED.test(name) || name.includes("..")) throw new GuardError(`file not allowed: ${name}`);
  const full = path.resolve(roundDir, name);
  if (path.dirname(full) !== path.resolve(roundDir)) throw new GuardError(`path escapes the round directory`);
  return full;
}
