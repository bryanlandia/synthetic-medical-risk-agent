import { expect, test } from "@playwright/test";
import { cleanEstimateInputs, forwardEstimate, pickEstimate } from "../lib/forward";

const CFG = { url: "http://agent.invalid", secret: "unit-secret-1234", timeoutMs: 200 };
const LABS = { velorin_index: 100, serum_k17: 4.2, tarnic_acid: 300, brell_enzyme: 35, halvin_titer: 4, osmet_level: 290, plexa_count: 250, dorrin_ratio: 1 };
const SYMPTOMS = { tremor: "absent", fatigue: "absent", photophobia: "absent", joint_stiffness: "absent", dizziness: "absent" } as const;
const ROWS = [...Object.keys(LABS).map((key) => ({ kind: "lab", key, contribution: 0.1, internal: "x" })), ...Object.keys(SYMPTOMS).map((key) => ({ kind: "symptom", key, contribution: -0.1 }))];
const OK = { request_id: "r1", probability: 0.42, band: "uncertain", score: -0.3, start: -1.2, breakdown: ROWS, message: "Labs:\n- ...", model_hash: "abc", extra: 1, secret_echo: CFG.secret, usage: { cost_usd: 1 } };
const reply = (status: number, body: unknown, headers: Record<string, string> = {}) => (async () => new Response(JSON.stringify(body), { status, headers })) as unknown as typeof fetch;

test("an estimate is passed on as a whitelist and nothing else", async () => {
  const out = await forwardEstimate({ labs: LABS, symptoms: SYMPTOMS }, "1.2.3.4", CFG, reply(200, OK));
  expect(out.status).toBe(200);
  const text = JSON.stringify(out.body);
  for (const leaked of ["internal", "extra", "secret_echo", "usage", CFG.secret]) expect(text).not.toContain(leaked);
  expect((out.body as { estimate: { breakdown: unknown[] } }).estimate.breakdown).toHaveLength(13);
});

test("the request carries the secret, the visitor, and the labs and symptoms only", async () => {
  let seen: { url: string; init: RequestInit } | null = null;
  const spy = (async (url: string, init: RequestInit) => { seen = { url, init }; return new Response(JSON.stringify(OK), { status: 200 }); }) as unknown as typeof fetch;
  await forwardEstimate({ labs: LABS, symptoms: SYMPTOMS }, "203.0.113.5", CFG, spy);
  const { url, init } = seen!;
  expect(url).toBe("http://agent.invalid/estimate");
  expect((init.headers as Record<string, string>)["x-shared-secret"]).toBe(CFG.secret);
  expect((init.headers as Record<string, string>)["x-visitor-address"]).toBe("203.0.113.5");
  expect(JSON.parse(init.body as string)).toEqual({ labs: LABS, symptoms: SYMPTOMS });
});

test("a body that is not an estimate is a 502 and a probability outside 0 to 1 is refused", async () => {
  expect((await forwardEstimate({ labs: LABS, symptoms: SYMPTOMS }, "v", CFG, reply(200, { probability: 0.5 }))).status).toBe(502);
  expect(pickEstimate({ ...OK, probability: 1.5 })).toBeNull();
  expect(pickEstimate({ ...OK, band: "red" })).toBeNull();
  expect(pickEstimate({ ...OK, breakdown: ROWS.slice(1) })).toBeNull();
});

test("a 429 is explained with the wait, and a refused input is not called an empty message", async () => {
  const limited = await forwardEstimate({ labs: LABS, symptoms: SYMPTOMS }, "v", CFG, reply(429, { error: "rate_limited" }, { "retry-after": "30" }));
  expect(limited).toMatchObject({ status: 429, retryAfter: 30, body: { error: { code: "rate_limited", retry_after: 30 } } });
  const refused = await forwardEstimate({ labs: LABS, symptoms: SYMPTOMS }, "v", CFG, reply(422, { error: "invalid_request" }));
  expect(refused.body).toEqual({ error: { code: "invalid_inputs", message: "Those values are outside what the demo accepts." } });
  const down = await forwardEstimate({ labs: LABS, symptoms: SYMPTOMS }, "v", CFG, reply(500, { error: "boom", detail: "upstream stack trace" }));
  expect(JSON.stringify(down.body)).not.toContain("stack trace");
});

test("only the eight labs and five symptoms shapes are accepted", () => {
  expect(cleanEstimateInputs({ labs: LABS, symptoms: SYMPTOMS })).toEqual({ labs: LABS, symptoms: SYMPTOMS });
  expect(cleanEstimateInputs({ labs: { ...LABS, plexa_count: null }, symptoms: SYMPTOMS })).not.toBeNull();
  for (const bad of [null, "x", [], { labs: LABS }, { labs: LABS, symptoms: SYMPTOMS, message: "hi" }, { labs: { ...LABS, plexa_count: "250" }, symptoms: SYMPTOMS }, { labs: LABS, symptoms: { ...SYMPTOMS, tremor: "maybe" } }]) {
    expect(cleanEstimateInputs(bad)).toBeNull();
  }
});

test("the route answers a real estimate from the scripted service and refuses bad inputs", async ({ request }) => {
  const ok = await request.post("/api/estimate", { data: { labs: LABS, symptoms: SYMPTOMS } });
  expect(ok.status()).toBe(200);
  const { estimate } = await ok.json();
  expect(Object.keys(estimate).sort()).toEqual(["band", "breakdown", "message", "model_hash", "probability", "request_id", "score", "start"]);
  expect(estimate.probability).toBeGreaterThan(0);
  expect(ok.headers()["cache-control"]).toBe("no-store");
  for (const data of [{ labs: { ...LABS, velorin_index: 1040 }, symptoms: SYMPTOMS }, { labs: LABS }, { labs: LABS, symptoms: SYMPTOMS, message: "hi" }]) {
    expect((await request.post("/api/estimate", { data })).status()).toBe(422);
  }
  expect((await request.post("/api/estimate", { data: "not json", headers: { "content-type": "application/json" } })).status()).toBe(422);
  expect((await request.post("/api/estimate", { data: "x".repeat(6000) })).status()).toBe(413);
});
