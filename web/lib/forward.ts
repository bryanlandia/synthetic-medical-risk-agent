/**
 * The server side of the page: forward one message to the agent service and return only what the page shows.
 *
 * Nothing here imports Next, so the tests run it directly with a fake `fetch`. The shared secret and the service address are
 * arguments, read from the server's environment by the route; they are never part of a response.
 */
import type { Analysis, DataQuality, Report, ShownError } from "./types";

export type ForwardConfig = { url: string; secret: string; timeoutMs: number };
export type Forwarded = { status: number; body: { analysis: Analysis } | { error: ShownError }; retryAfter?: number };

const WAIT_DEFAULT = 60;

export function describe(status: number, code: string | null, retryAfter: number | null): ShownError {
  if (status === 401) return { code: "misconfigured", message: "The demo is not configured correctly. Please try again later." };
  if (status === 413) return { code: "too_long", message: "That message is too long. Please keep it under 6,000 characters." };
  if (status === 422) return { code: "empty", message: "Please enter a message to send." };
  if (status === 429) {
    const wait = retryAfter && retryAfter > 0 ? retryAfter : WAIT_DEFAULT;
    return { code: "rate_limited", message: `You have sent a lot of requests. Please wait about ${wait} seconds and try again.`, retry_after: wait };
  }
  if (status === 503 && code === "daily_budget_used") {
    return { code: "daily_budget_used", message: "The demo's daily budget has been used up. Please come back tomorrow." };
  }
  if (status === 503) return { code: "unavailable", message: "The demo is temporarily unavailable. Please try again in a minute." };
  if (status === 502) return { code: "model_unavailable", message: "The language model is unavailable right now. Please try again." };
  if (status === 504) return { code: "timeout", message: "The demo took too long to answer. Please try again." };
  return { code: "error", message: "Something went wrong. Please try again." };
}

const str = (v: unknown): v is string => typeof v === "string";
const num = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function pickReport(r: unknown): Report | null {
  if (!r || typeof r !== "object") return null;
  const o = r as Record<string, unknown>;
  if (!num(o.probability) || typeof o.uncertain !== "boolean" || !Array.isArray(o.evidence) || !Array.isArray(o.data_quality)) return null;
  const symptoms: Record<string, string> = {};
  for (const [k, v] of Object.entries((o.symptoms ?? {}) as Record<string, unknown>)) if (str(v)) symptoms[k] = v;
  return {
    probability: o.probability,
    uncertain: o.uncertain,
    symptoms,
    labs_used: (Array.isArray(o.labs_used) ? o.labs_used : [])
      .filter((l): l is { lab: string; value: number; unit: string } => !!l && str(l.lab) && num(l.value) && str(l.unit))
      .map((l) => ({ lab: l.lab, value: l.value, unit: l.unit })),
    data_quality: o.data_quality
      .filter((d): d is DataQuality => !!d && str((d as DataQuality).type))
      .map((d) => ({ type: d.type, lab: str(d.lab) ? d.lab : null })),
    evidence: o.evidence.filter(str),
    disclaimer: str(o.disclaimer) ? o.disclaimer : "",
  };
}

/** The whitelisted analysis, or null if the body is not a response this page understands. */
export function pickAnalysis(body: unknown): Analysis | null {
  if (!body || typeof body !== "object") return null;
  const o = body as Record<string, unknown>;
  if (typeof o.declined !== "boolean" || !str(o.reply)) return null;
  const usage = (o.usage ?? {}) as Record<string, unknown>;
  return {
    request_id: str(o.request_id) ? o.request_id : "",
    declined: o.declined,
    decline_reason: str(o.decline_reason) ? o.decline_reason : null,
    reply: o.reply,
    reply_source: o.reply_source === "template" ? "template" : "model",
    report: o.declined ? null : pickReport(o.report),
    usage: {
      input_tokens: num(usage.input_tokens) ? usage.input_tokens : 0,
      output_tokens: num(usage.output_tokens) ? usage.output_tokens : 0,
      cost_usd: num(usage.cost_usd) ? usage.cost_usd : 0,
    },
  };
}

export function failure(status: number, code: string | null = null, retryAfter: number | null = null): Forwarded {
  const error = describe(status, code, retryAfter);
  return { status, body: { error }, retryAfter: error.retry_after };
}

export async function forward(message: string, visitor: string, cfg: ForwardConfig, fetchImpl: typeof fetch = fetch): Promise<Forwarded> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), cfg.timeoutMs);
  try {
    const response = await fetchImpl(`${cfg.url.replace(/\/$/, "")}/analyze`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-shared-secret": cfg.secret, "x-visitor-address": visitor },
      body: JSON.stringify({ message }),
      signal: controller.signal,
      cache: "no-store",
    });
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    if (response.status === 200) {
      const analysis = pickAnalysis(body);
      return analysis ? { status: 200, body: { analysis } } : failure(502);
    }
    const code = body && typeof body === "object" && str((body as Record<string, unknown>).error) ? ((body as Record<string, unknown>).error as string) : null;
    const wait = Number(response.headers.get("retry-after"));
    return failure(response.status, code, Number.isFinite(wait) ? wait : null);
  } catch (exc) {
    return failure((exc as Error).name === "AbortError" ? 504 : 502);
  } finally {
    clearTimeout(timer);
  }
}

/** The visitor the platform saw: the first address of its forwarded-for header (the browser cannot set this behind the platform). */
export function visitorAddress(headers: { get(name: string): string | null }): string {
  const forwarded = headers.get("x-forwarded-for");
  const first = forwarded ? forwarded.split(",")[0].trim() : headers.get("x-real-ip");
  return (first || "unknown").slice(0, 100);
}
