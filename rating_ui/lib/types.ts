export const SYMPTOM_KEYS = ["tremor", "fatigue", "photophobia", "joint_stiffness", "dizziness"] as const;
export const SYMPTOM_VALUES = ["present", "possible", "absent", "none"] as const;
export const PLAUSIBLE_VALUES = ["y", "n"] as const;

export type SymptomKey = (typeof SYMPTOM_KEYS)[number];
export type SymptomValue = (typeof SYMPTOM_VALUES)[number];
export type PlausibleValue = (typeof PLAUSIBLE_VALUES)[number];
export type RaterKind = "human" | "llm";

export interface Sheet {
  version: number;
  notice: string;
  symptom_keys: string[];
  plausible_values: string[];
  symptom_values: string[];
  notes: { id: string; text: string; kind?: { label: string; expect: string } }[];
}

export interface NoteRating {
  plausible: PlausibleValue | null;
  symptoms: Partial<Record<SymptomKey, SymptomValue | null>>;
  comment: string;
  reason: string;
}

export interface RatingFile {
  version: number;
  rater: string;
  kind: RaterKind;
  model_id: string | null;
  prompt_version: string | null;
  ratings: Record<string, NoteRating>;
}

export interface Session {
  kind: RaterKind;
  fixedRater: string | null; // set for llm sessions; a human types a name
  notice: string;
}

export function isComplete(r: NoteRating | undefined): boolean {
  return !!r && r.plausible !== null && SYMPTOM_KEYS.every((k) => !!r.symptoms[k]);
}
