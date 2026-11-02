/**
 * Asks the server for the estimate while a control moves, without flooding it.
 *
 * At most one request goes out per window while the inputs keep changing, and one more when they stop. Every request carries a
 * sequence number and an answer older than the one already shown is dropped, so a slow reply can never put an older patient's
 * number back. A 429 keeps the last estimate on screen and says to slow down; a first answer that takes long shows the
 * "waking up" state. Nothing here imports React or the browser, so the timing is tested with a fake clock.
 */
import type { Estimate, EstimateInputs, ShownError } from "./types";

export const WINDOW_MS = 150;
export const WAKING_MS = 1500;

export type EstimateStatus = "idle" | "updating" | "waking" | "slow_down" | "error";
export type Posted = { status: number; body: unknown };
export type Scheduler = { set(fn: () => void, ms: number): unknown; clear(handle: unknown): void };

const real: Scheduler = { set: (fn, ms) => setTimeout(fn, ms), clear: (h) => clearTimeout(h as ReturnType<typeof setTimeout>) };

export function createEstimator(opts: {
  post: (inputs: EstimateInputs) => Promise<Posted>;
  onResult: (estimate: Estimate, inputs: EstimateInputs) => void;
  onStatus: (status: EstimateStatus, error?: ShownError) => void;
  scheduler?: Scheduler;
}) {
  const clock = opts.scheduler ?? real;
  let seq = 0; // the number of the latest request sent
  let shown = 0; // the number of the newest answer shown
  let windowTimer: unknown = null;
  let wakingTimer: unknown = null;
  let pending: EstimateInputs | null = null;
  let inFlight = 0;

  const endWindow = () => {
    windowTimer = null;
    if (pending) {
      const next = pending;
      pending = null;
      send(next);
    }
  };

  function send(inputs: EstimateInputs) {
    const mine = ++seq;
    windowTimer = clock.set(endWindow, WINDOW_MS);
    inFlight += 1;
    opts.onStatus("updating");
    if (wakingTimer === null) wakingTimer = clock.set(() => opts.onStatus("waking"), WAKING_MS);
    opts.post(inputs).then(
      (reply) => settle(mine, inputs, reply),
      () => settle(mine, inputs, { status: 0, body: null }),
    );
  }

  function settle(mine: number, inputs: EstimateInputs, reply: Posted) {
    inFlight -= 1;
    if (inFlight === 0 && wakingTimer !== null) {
      clock.clear(wakingTimer);
      wakingTimer = null;
    }
    if (mine < shown) return; // an older answer than the one on screen
    if (reply.status === 200 && reply.body && typeof reply.body === "object" && "estimate" in reply.body) {
      shown = mine;
      opts.onResult((reply.body as { estimate: Estimate }).estimate, inputs);
      if (inFlight === 0 && pending === null) opts.onStatus("idle");
      return;
    }
    const error = reply.body && typeof reply.body === "object" && "error" in reply.body ? ((reply.body as { error: ShownError }).error) : undefined;
    opts.onStatus(reply.status === 429 ? "slow_down" : "error", error ?? { code: "network", message: "Could not reach the demo. Please check your connection and try again." });
  }

  return {
    /** The inputs changed: send now if the window is free, else keep only the latest for the end of the window. */
    request(inputs: EstimateInputs) {
      if (windowTimer === null) send(inputs);
      else pending = inputs;
    },
    /** Forget anything waiting and ignore every answer still on its way. */
    cancel() {
      pending = null;
      shown = seq + 1; // every answer still on its way is older than the next request
      if (windowTimer !== null) clock.clear(windowTimer);
      if (wakingTimer !== null) clock.clear(wakingTimer);
      windowTimer = wakingTimer = null;
    },
  };
}
