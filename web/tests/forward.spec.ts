import { expect, test } from "@playwright/test";
import { describe, forward, visitorAddress } from "../lib/forward";

const CFG = { url: "http://agent.invalid", secret: "unit-secret-1234", timeoutMs: 200 };
const REPORT = {
  probability: 0.31, uncertain: false, symptoms: { tremor: "present" }, labs_used: [{ lab: "serum_k17", value: 4.1, unit: "mmol/L", extra: 1 }],
  data_quality: [{ type: "missing_value", lab: "velorin_index", internal: "x" }], evidence: ["e1"], disclaimer: "d", ground_truth: { label: 1 },
};
const OK = { request_id: "r1", declined: false, decline_reason: null, reply: "hello", reply_source: "model", report: REPORT,
  usage: { input_tokens: 10, output_tokens: 5, cost_usd: 0.0001, tools: ["score_message"] }, secret_echo: CFG.secret };

const reply = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  (async () => new Response(JSON.stringify(body), { status, headers })) as unknown as typeof fetch;

test("a scored response is passed on as a whitelist and nothing else", async () => {
  const out = await forward("m", "1.2.3.4", CFG, reply(200, OK));
  expect(out.status).toBe(200);
  const text = JSON.stringify(out.body);
  expect(text).not.toContain("ground_truth");
  expect(text).not.toContain("secret_echo");
  expect(text).not.toContain("internal");
  expect(text).not.toContain("tools");
  expect(text).not.toContain(CFG.secret);
  expect(out.body).toMatchObject({ analysis: { declined: false, reply: "hello", report: { probability: 0.31 } } });
});

test("a decline is passed on without a report", async () => {
  const out = await forward("m", "v", CFG, reply(200, { ...OK, declined: true, decline_reason: "treatment_request", report: null }));
  expect(out.body).toMatchObject({ analysis: { declined: true, decline_reason: "treatment_request", report: null } });
});

test("the request carries the secret, the visitor and only the message", async () => {
  let seen: { url: string; init: RequestInit } | null = null;
  const spy = (async (url: string, init: RequestInit) => { seen = { url, init }; return new Response(JSON.stringify(OK), { status: 200 }); }) as unknown as typeof fetch;
  await forward("the message", "203.0.113.5", CFG, spy);
  const { url, init } = seen!;
  expect(url).toBe("http://agent.invalid/analyze");
  const headers = init.headers as Record<string, string>;
  expect(headers["x-shared-secret"]).toBe(CFG.secret);
  expect(headers["x-visitor-address"]).toBe("203.0.113.5");
  expect(JSON.parse(init.body as string)).toEqual({ message: "the message" });
});

const CASES: [number, object, string, string | null][] = [
  [401, { error: "unauthorized" }, "misconfigured", "not configured"],
  [413, { error: "message_too_long" }, "too_long", "too long"],
  [422, { error: "invalid_request" }, "empty", "enter a message"],
  [503, { error: "daily_budget_used" }, "daily_budget_used", "come back tomorrow"],
  [503, { error: "limits_unavailable" }, "unavailable", "temporarily unavailable"],
  [502, { error: "model_unavailable" }, "model_unavailable", "language model is unavailable"],
  [500, { detail: "boom with secret unit-secret-1234" }, "error", "Something went wrong"],
];
for (const [status, body, code, words] of CASES) {
  test(`an upstream ${status} (${(body as Record<string, string>).error ?? "other"}) is explained and its body is not shown`, async () => {
    const out = await forward("m", "v", CFG, reply(status, body));
    expect(out.status).toBe(status);
    expect(out.body).toMatchObject({ error: { code } });
    const text = JSON.stringify(out.body);
    expect(text).toContain(words!);
    expect(text).not.toContain("boom");
    expect(text).not.toContain(CFG.secret);
  });
}

test("a 429 tells the visitor how long to wait and passes Retry-After on", async () => {
  const out = await forward("m", "v", CFG, reply(429, { error: "rate_limited" }, { "retry-after": "30" }));
  expect(out.status).toBe(429);
  expect(out.retryAfter).toBe(30);
  expect(JSON.stringify(out.body)).toContain("about 30 seconds");
});

test("a 429 without Retry-After falls back to a minute", async () => {
  const out = await forward("m", "v", CFG, reply(429, { error: "rate_limited" }));
  expect(out.retryAfter).toBe(60);
});

test("a service that does not answer in time is a 504, and a refused connection a 502", async () => {
  const hang = ((_: string, init: RequestInit) => new Promise((_, reject) => init.signal!.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" }))))) as unknown as typeof fetch;
  expect((await forward("m", "v", { ...CFG, timeoutMs: 30 }, hang)).status).toBe(504);
  const refused = (async () => { throw new TypeError("fetch failed"); }) as unknown as typeof fetch;
  expect((await forward("m", "v", CFG, refused)).status).toBe(502);
});

test("a 200 that is not an analysis is a 502, not passed through", async () => {
  const out = await forward("m", "v", CFG, reply(200, { hello: "world" }));
  expect(out.status).toBe(502);
  expect(JSON.stringify(out.body)).not.toContain("world");
});

test("the visitor is the first forwarded address", () => {
  const h = (m: Record<string, string>) => ({ get: (n: string) => m[n] ?? null });
  expect(visitorAddress(h({ "x-forwarded-for": "198.51.100.7, 10.0.0.1" }))).toBe("198.51.100.7");
  expect(visitorAddress(h({ "x-real-ip": "198.51.100.8" }))).toBe("198.51.100.8");
  expect(visitorAddress(h({}))).toBe("unknown");
});

test("describe names the wait for a rate limit", () => {
  expect(describe(429, null, 45).message).toContain("45 seconds");
});
