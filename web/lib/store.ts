/**
 * The supervisor's progress: a reducer over plain data, and the helpers that keep it in the browser's local storage.
 *
 * Nothing here talks to a server. Saved progress is tied to the cases file and the policy it was made for: if either changed, it
 * is discarded rather than shown.
 */
import type { Packet, PacketDecline } from "./types";

export const STORAGE_KEY = "vk-review-v1";
export const MIN_RATIONALE = 20;
export const MIN_NOTE = 5;

export type Status = "new" | "in-review" | "returned" | "released" | "closed";
export type EventKind = "prepared" | "opened" | "reopened" | "returned" | "released" | "closed";
export type AuditEvent = { at: string; kind: EventKind; text?: string };
export type CaseState = {
  status: Status;
  packet?: Packet | PacketDecline;
  note?: string; // the supervisor's return note, in their own words
  rationale?: string; // the supervisor's rationale for a release, in their own words
  events: AuditEvent[];
};
export type Saved = { version: 1; casesHash: string; policyId: string; introDismissed: boolean; cases: Record<string, CaseState> };

export type Action =
  | { type: "hydrate"; saved: Saved }
  | { type: "open"; id: string; at: string; preparedAt: string; preparer: string }
  | { type: "packet"; id: string; packet: Packet | PacketDecline }
  | { type: "return"; id: string; at: string; note: string }
  | { type: "release"; id: string; at: string; rationale: string }
  | { type: "close"; id: string; at: string }
  | { type: "reopen"; id: string; at: string }
  | { type: "dismissIntro" }
  | { type: "reset"; casesHash: string; policyId: string };

export function initial(casesHash: string, policyId: string): Saved {
  return { version: 1, casesHash, policyId, introDismissed: false, cases: {} };
}

export const statusOf = (saved: Saved, id: string): Status => saved.cases[id]?.status ?? "new";

const base = (saved: Saved, id: string): CaseState => saved.cases[id] ?? { status: "new", events: [] };
const put = (saved: Saved, id: string, next: CaseState): Saved => ({ ...saved, cases: { ...saved.cases, [id]: next } });

export function reduce(saved: Saved, action: Action): Saved {
  switch (action.type) {
    case "hydrate":
      return action.saved;
    case "open": {
      const c = base(saved, action.id);
      if (c.status !== "new") return saved; // reopening a decided case changes nothing; a returned one is reopened explicitly
      const prepared: AuditEvent = { at: action.preparedAt, kind: "prepared", text: `Prepared by ${action.preparer} (simulated)` };
      return put(saved, action.id, { ...c, status: "in-review", events: [prepared, { at: action.at, kind: "opened" }] });
    }
    case "packet":
      return put(saved, action.id, { ...base(saved, action.id), packet: action.packet });
    case "return": {
      const c = base(saved, action.id);
      if (c.status !== "in-review" || action.note.trim().length < MIN_NOTE) return saved;
      return put(saved, action.id, { ...c, status: "returned", note: action.note.trim(), events: [...c.events, { at: action.at, kind: "returned" }] });
    }
    case "release": {
      const c = base(saved, action.id);
      if (c.status !== "in-review") return saved;
      const rationale = action.rationale.trim();
      return put(saved, action.id, { ...c, status: "released", rationale: rationale || undefined, events: [...c.events, { at: action.at, kind: "released" }] });
    }
    case "close": {
      const c = base(saved, action.id);
      if (c.status !== "in-review") return saved;
      return put(saved, action.id, { ...c, status: "closed", events: [...c.events, { at: action.at, kind: "closed" }] });
    }
    case "reopen": {
      const c = base(saved, action.id);
      if (c.status !== "returned") return saved;
      return put(saved, action.id, { ...c, status: "in-review", events: [...c.events, { at: action.at, kind: "reopened" }] });
    }
    case "dismissIntro":
      return { ...saved, introDismissed: true };
    case "reset":
      return initial(action.casesHash, action.policyId);
  }
}

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

/** Saved progress for these cases and this policy, or a fresh start if there is none, it is unreadable, or it was made for other data. */
export function load(storage: StorageLike | null, casesHash: string, policyId: string): Saved {
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    if (!raw) return initial(casesHash, policyId);
    const saved = JSON.parse(raw) as Saved;
    if (saved?.version !== 1 || saved.casesHash !== casesHash || saved.policyId !== policyId || typeof saved.cases !== "object" || !saved.cases) {
      return initial(casesHash, policyId);
    }
    return { ...saved, introDismissed: saved.introDismissed === true };
  } catch {
    return initial(casesHash, policyId);
  }
}

export function save(storage: StorageLike | null, saved: Saved): void {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(saved));
  } catch {
    /* storage full or blocked: the session still works, it just will not survive a reload */
  }
}

export function clear(storage: StorageLike | null): void {
  try {
    storage?.removeItem(STORAGE_KEY);
  } catch {
    /* nothing to clear */
  }
}

/** The release rule: what stands in the way of releasing, given the packet's criterion statuses and the rationale typed so far. */
export function releaseBlock(packet: Packet | PacketDecline | undefined, rationale: string): string | null {
  if (!packet || packet.declined) return "The packet is not available yet.";
  const unknown = packet.criteria.filter((c) => c.status === "unknown");
  if (unknown.length) return `${unknown.map((c) => c.id).join(", ")} ${unknown.length === 1 ? "is" : "are"} unknown, so the packet is incomplete. Return it to the preparer.`;
  const unmet = packet.criteria.filter((c) => c.status === "unmet");
  if (unmet.length && rationale.trim().length < MIN_RATIONALE) {
    return `${unmet.map((c) => c.id).join(", ")} ${unmet.length === 1 ? "is" : "are"} unmet. Write your own rationale (at least ${MIN_RATIONALE} characters) to release it anyway.`;
  }
  return null;
}

/** Nothing has been done yet: no case touched and the intro not dismissed. A fresh state is never written to storage. */
export function isFresh(saved: Saved): boolean {
  return !saved.introDismissed && Object.keys(saved.cases).length === 0;
}
