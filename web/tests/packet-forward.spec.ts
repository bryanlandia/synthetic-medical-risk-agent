import { expect, test } from "@playwright/test";
import { cleanAnswers, forwardPacket } from "../lib/forward";

const CFG = { url: "http://agent.invalid", secret: "unit-secret-1234", timeoutMs: 200 };
const ROWS = ["C1", "C2", "C3", "C4", "C5", "C6"].map((id) => ({ id, text: `wording ${id}`, status: "unknown", cites: [`attest:${id}`], internal: "x" }));
const OK = {
  request_id: "r1", declined: false, policy_id: "p", notice: "fictional", criteria: ROWS,
  evidence: [{ id: "attest:C3", label: "l", text: "The clinician has not yet answered C3", extra: 1 }],
  gaps: [{ criterion: "C3", kind: "attestation", items: ["C3"], prompt: "answer", secret_echo: CFG.secret }],
  summary: [{ criterion: "C3", status: "unknown", text: "C3 is unknown", cites: ["attest:C3"] }], summary_source: "model",
  summary_fallback: ["number"], report: null, disclaimer: "not medical advice", usage: { cost_usd: 0.1 }, ground_truth: { label: 1 },
};
const reply = (status: number, body: unknown) => (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch;

test("a packet is passed on as a whitelist and nothing else", async () => {
  const out = await forwardPacket("m", {}, "1.2.3.4", CFG, reply(200, OK));
  expect(out.status).toBe(200);
  const text = JSON.stringify(out.body);
  for (const leaked of ["internal", "extra", "secret_echo", "ground_truth", "usage", "summary_fallback", CFG.secret]) expect(text).not.toContain(leaked);
  expect(out.body).toMatchObject({ packet: { declined: false, summary_source: "model" } });
  expect((out.body as { packet: { criteria: { id: string }[] } }).packet.criteria.map((c) => c.id)).toEqual(["C1", "C2", "C3", "C4", "C5", "C6"]);
});

test("a decline is passed on without a table", async () => {
  const out = await forwardPacket("m", {}, "v", CFG, reply(200, { request_id: "r", declined: true, decline_reason: "phi", message: "no", criteria: ROWS }));
  expect(out.body).toEqual({ packet: { request_id: "r", declined: true, decline_reason: "phi", message: "no" } });
});

test("the request carries the secret, the visitor, the message and the answers only", async () => {
  let seen: { url: string; init: RequestInit } | null = null;
  const spy = (async (url: string, init: RequestInit) => { seen = { url, init }; return new Response(JSON.stringify(OK), { status: 200 }); }) as unknown as typeof fetch;
  await forwardPacket("the message", { C3: "yes" }, "203.0.113.5", CFG, spy);
  const { url, init } = seen!;
  expect(url).toBe("http://agent.invalid/packet");
  expect((init.headers as Record<string, string>)["x-shared-secret"]).toBe(CFG.secret);
  expect(JSON.parse(init.body as string)).toEqual({ message: "the message", attestations: { C3: "yes" } });
});

test("a body that is not a packet is a 502 and an upstream error is explained without its body", async () => {
  expect((await forwardPacket("m", {}, "v", CFG, reply(200, { criteria: [] }))).status).toBe(502);
  const out = await forwardPacket("m", {}, "v", CFG, reply(503, { error: "daily_budget_used", detail: "boom unit-secret-1234" }));
  expect(out.status).toBe(503);
  expect(JSON.stringify(out.body)).toContain("come back tomorrow");
  expect(JSON.stringify(out.body)).not.toContain("boom");
});

test("only C3 to C6 with yes or no are accepted, and unanswered is left out", () => {
  expect(cleanAnswers(undefined)).toEqual({});
  expect(cleanAnswers({ C3: "yes", C4: "unanswered", C5: "no" })).toEqual({ C3: "yes", C5: "no" });
  for (const bad of [{ C3: "maybe" }, { C7: "yes" }, { C1: "yes" }, { C3: true }, "yes", ["C3"]]) expect(cleanAnswers(bad)).toBeNull();
});
