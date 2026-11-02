import { expect, test } from "@playwright/test";
import { WAKING_MS, WINDOW_MS, createEstimator, type EstimateStatus, type Posted, type Scheduler } from "../lib/estimator";
import type { Estimate, EstimateInputs } from "../lib/types";

class FakeClock implements Scheduler {
  now = 0;
  private timers: { at: number; fn: () => void; id: number }[] = [];
  private next = 1;
  set(fn: () => void, ms: number) {
    const id = this.next++;
    this.timers.push({ at: this.now + ms, fn, id });
    return id;
  }
  clear(h: unknown) {
    this.timers = this.timers.filter((t) => t.id !== h);
  }
  async advance(ms: number) {
    const end = this.now + ms;
    for (;;) {
      const due = this.timers.filter((t) => t.at <= end).sort((a, b) => a.at - b.at)[0];
      if (!due) break;
      this.timers = this.timers.filter((t) => t !== due);
      this.now = due.at;
      due.fn();
      await Promise.resolve();
    }
    this.now = end;
    await Promise.resolve();
  }
}

const inputs = (n: number): EstimateInputs => ({ labs: { velorin_index: n }, symptoms: { tremor: "absent" } });
const estimate = (p: number): Estimate => ({ request_id: "r", probability: p, band: "uncertain", score: 0, start: 0, breakdown: [], message: "", model_hash: "h" });
const ok = (p: number): Posted => ({ status: 200, body: { estimate: estimate(p) } });

function harness() {
  const clock = new FakeClock();
  const sent: { inputs: EstimateInputs; resolve: (r: Posted) => void }[] = [];
  const shown: number[] = [];
  const statuses: EstimateStatus[] = [];
  const estimator = createEstimator({
    post: (i) => new Promise<Posted>((resolve) => sent.push({ inputs: i, resolve })),
    onResult: (e) => shown.push(e.probability),
    onStatus: (s) => statuses.push(s),
    scheduler: clock,
  });
  return { clock, sent, shown, statuses, estimator };
}

test("a burst of 50 changes in one window sends the first at once and the last when the window ends", async () => {
  const h = harness();
  for (let i = 0; i < 50; i++) h.estimator.request(inputs(i));
  expect(h.sent).toHaveLength(1);
  expect(h.sent[0].inputs).toEqual(inputs(0));
  await h.clock.advance(WINDOW_MS);
  expect(h.sent).toHaveLength(2);
  expect(h.sent[1].inputs).toEqual(inputs(49)); // only the latest is kept
  await h.clock.advance(WINDOW_MS * 3);
  expect(h.sent).toHaveLength(2); // and nothing more once the inputs stop changing
});

test("steady changes send at most one request per window", async () => {
  const h = harness();
  for (let t = 0; t < 1000; t += 10) {
    h.estimator.request(inputs(t));
    await h.clock.advance(10);
  }
  await h.clock.advance(WINDOW_MS);
  expect(h.sent.length).toBeLessThanOrEqual(Math.ceil(1000 / WINDOW_MS) + 2);
  expect(h.sent.length).toBeGreaterThan(3);
});

test("a late old answer never replaces a newer one", async () => {
  const h = harness();
  h.estimator.request(inputs(1));
  await h.clock.advance(WINDOW_MS);
  h.estimator.request(inputs(2));
  expect(h.sent).toHaveLength(2);
  h.sent[1].resolve(ok(0.7));
  await h.clock.advance(1);
  h.sent[0].resolve(ok(0.2)); // the first request answers last
  await h.clock.advance(1);
  expect(h.shown).toEqual([0.7]);
});

test("a 429 keeps the last estimate on screen and says to slow down", async () => {
  const h = harness();
  h.estimator.request(inputs(1));
  h.sent[0].resolve(ok(0.4));
  await h.clock.advance(WINDOW_MS);
  h.estimator.request(inputs(2));
  h.sent[1].resolve({ status: 429, body: { error: { code: "rate_limited", message: "wait", retry_after: 30 } } });
  await h.clock.advance(1);
  expect(h.shown).toEqual([0.4]);
  expect(h.statuses.at(-1)).toBe("slow_down");
});

test("a failure to reach the server is an error and keeps the last estimate", async () => {
  const clock = new FakeClock();
  const statuses: EstimateStatus[] = [];
  const shown: number[] = [];
  const estimator = createEstimator({ post: () => Promise.reject(new Error("offline")), onResult: (e) => shown.push(e.probability), onStatus: (s) => statuses.push(s), scheduler: clock });
  estimator.request(inputs(1));
  await clock.advance(1);
  expect(shown).toEqual([]);
  expect(statuses.at(-1)).toBe("error");
});

test("a first answer that takes longer than 1.5 seconds shows the waking-up state, and an answer clears it", async () => {
  const h = harness();
  h.estimator.request(inputs(1));
  await h.clock.advance(WAKING_MS - 1);
  expect(h.statuses).not.toContain("waking");
  await h.clock.advance(1);
  expect(h.statuses.at(-1)).toBe("waking");
  h.sent[0].resolve(ok(0.5));
  await h.clock.advance(1);
  expect(h.statuses.at(-1)).toBe("idle");
});

test("cancel drops what waits and every answer still on its way", async () => {
  const h = harness();
  h.estimator.request(inputs(1));
  h.estimator.request(inputs(2));
  h.estimator.cancel();
  await h.clock.advance(WINDOW_MS * 2);
  expect(h.sent).toHaveLength(1); // the waiting one was never sent
  h.sent[0].resolve(ok(0.9));
  await h.clock.advance(1);
  expect(h.shown).toEqual([]);
  h.estimator.request(inputs(3)); // and a request after the cancel is answered normally
  h.sent[1].resolve(ok(0.3));
  await h.clock.advance(1);
  expect(h.shown).toEqual([0.3]);
});
