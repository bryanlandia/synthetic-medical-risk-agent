import { expect, test } from "@playwright/test";
import { clear, initial, load, MIN_NOTE, MIN_RATIONALE, reduce, releaseBlock, save, statusOf, STORAGE_KEY, type Saved } from "../lib/store";
import type { Packet } from "../lib/types";

const HASH = "abc123def456";
const POLICY = "fictional-k17-pet-ct-v2";
const T = (n: number) => `2026-11-01T10:0${n}:00.000Z`;

function memory() {
  const data = new Map<string, string>();
  return { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v), removeItem: (k: string) => void data.delete(k), data };
}

const open = (s: Saved, id = "case-01") => reduce(s, { type: "open", id, at: T(1), preparedAt: "08:12", preparer: "R. Okafor" });

function packet(statuses: string[]): Packet {
  return {
    request_id: "r", declined: false, policy_id: POLICY, notice: "n", disclaimer: "d", summary_source: "model", report: null, evidence: [], gaps: [], summary: [],
    criteria: statuses.map((status, i) => ({ id: `C${i + 1}`, text: "t", status: status as never, cites: [] })),
  };
}

test("a new case is New, and opening it makes it In review with the preparer's entry first", () => {
  const s0 = initial(HASH, POLICY);
  expect(statusOf(s0, "case-01")).toBe("new");
  const s1 = open(s0);
  expect(statusOf(s1, "case-01")).toBe("in-review");
  expect(s1.cases["case-01"].events.map((e) => e.kind)).toEqual(["prepared", "opened"]);
  expect(s1.cases["case-01"].events[0].text).toContain("simulated");
  expect(open(s1)).toBe(s1); // opening again changes nothing
});

test("return needs a note of at least 5 characters, release and close need In review, and decided cases are final", () => {
  const s1 = open(initial(HASH, POLICY));
  expect(reduce(s1, { type: "return", id: "case-01", at: T(2), note: "no" })).toBe(s1);
  expect(reduce(initial(HASH, POLICY), { type: "release", id: "case-01", at: T(2), rationale: "" }).cases["case-01"]).toBeUndefined();
  const returned = reduce(s1, { type: "return", id: "case-01", at: T(2), note: "  Please add the date of the prior scan.  " });
  expect(statusOf(returned, "case-01")).toBe("returned");
  expect(returned.cases["case-01"].note).toBe("Please add the date of the prior scan.");
  expect(reduce(returned, { type: "release", id: "case-01", at: T(3), rationale: "" })).toBe(returned);
  const reopened = reduce(returned, { type: "reopen", id: "case-01", at: T(3) });
  expect(statusOf(reopened, "case-01")).toBe("in-review");
  const released = reduce(reopened, { type: "release", id: "case-01", at: T(4), rationale: " My own reason for releasing. " });
  expect(statusOf(released, "case-01")).toBe("released");
  expect(released.cases["case-01"].rationale).toBe("My own reason for releasing.");
  expect(released.cases["case-01"].events.map((e) => e.kind)).toEqual(["prepared", "opened", "returned", "reopened", "released"]);
  for (const a of [{ type: "close" as const, id: "case-01", at: T(5) }, { type: "reopen" as const, id: "case-01", at: T(5) }]) expect(reduce(released, a)).toBe(released);
  const closed = reduce(s1, { type: "close", id: "case-01", at: T(2) });
  expect(statusOf(closed, "case-01")).toBe("closed");
  expect(reduce(closed, { type: "release", id: "case-01", at: T(3), rationale: "" })).toBe(closed);
});

test("the packet is kept with the case and the intro can be dismissed", () => {
  const p = packet(["met"]);
  const s = reduce(reduce(open(initial(HASH, POLICY)), { type: "packet", id: "case-01", packet: p }), { type: "dismissIntro" });
  expect(s.cases["case-01"].packet).toBe(p);
  expect(s.introDismissed).toBe(true);
  const reset = reduce(s, { type: "reset", casesHash: HASH, policyId: POLICY });
  expect(reset).toEqual(initial(HASH, POLICY));
});

test("saved progress round-trips, and progress for other data or a damaged value is discarded", () => {
  const store = memory();
  const s = reduce(open(initial(HASH, POLICY)), { type: "return", id: "case-01", at: T(2), note: "Please add the date." });
  save(store, s);
  expect(load(store, HASH, POLICY)).toEqual(s);
  expect(load(store, "other-hash", POLICY)).toEqual(initial("other-hash", POLICY));
  expect(load(store, HASH, "fictional-k17-pet-ct-v1")).toEqual(initial(HASH, "fictional-k17-pet-ct-v1"));
  store.setItem(STORAGE_KEY, "not json");
  expect(load(store, HASH, POLICY)).toEqual(initial(HASH, POLICY));
  store.setItem(STORAGE_KEY, JSON.stringify({ version: 2, casesHash: HASH, policyId: POLICY, cases: {} }));
  expect(load(store, HASH, POLICY)).toEqual(initial(HASH, POLICY));
  expect(load(null, HASH, POLICY)).toEqual(initial(HASH, POLICY));
  save(store, s);
  clear(store);
  expect(store.data.size).toBe(0);
});

test("release is blocked by an unknown criterion, needs a 20-character rationale for an unmet one, and is free when all are met", () => {
  expect(releaseBlock(packet(["met", "met", "met", "met", "met", "met"]), "")).toBeNull();
  expect(releaseBlock(packet(["met", "unknown", "met"]), "x".repeat(100))).toContain("C2 is unknown");
  expect(releaseBlock(packet(["met", "unmet", "met"]), "")).toContain("C2 is unmet");
  expect(releaseBlock(packet(["met", "unmet"]), "x".repeat(MIN_RATIONALE - 1))).not.toBeNull();
  expect(releaseBlock(packet(["met", "unmet"]), "x".repeat(MIN_RATIONALE))).toBeNull();
  expect(releaseBlock(packet(["met", "unmet"]), "   " + "x".repeat(MIN_RATIONALE - 1) + "   ")).not.toBeNull(); // spaces do not count
  expect(releaseBlock(undefined, "")).not.toBeNull();
  expect(MIN_NOTE).toBe(5);
});
