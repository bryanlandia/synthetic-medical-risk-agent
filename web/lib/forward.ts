/**
 * The server side of the page: forward one message to the agent service and return only what the page shows.
 *
 * Nothing here imports Next, so the tests run it directly with a fake `fetch`. The shared secret and the service address are
 * arguments, read from the server's environment by the route; they are never part of a response.
 */
import type { Analysis, CriterionStatus, Criterion, DataQuality, Evidence, Gap, Packet, PacketDecline, PacketGap, Report, ShownError, SummarySentence } from "./types";

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

const prob = (v: unknown): v is number => num(v) && v >= 0 && v <= 1;

/** The range and gaps, only when they are well formed; anything else is dropped, never passed on. */
function pickRange(o: Record<string, unknown>): Pick<Report, "interval" | "gaps"> {
  const out: Pick<Report, "interval" | "gaps"> = {};
  if (Array.isArray(o.interval) && o.interval.length === 2 && prob(o.interval[0]) && prob(o.interval[1])) out.interval = [o.interval[0], o.interval[1]];
  if (Array.isArray(o.gaps)) {
    out.gaps = o.gaps
      .filter((g): g is Gap => !!g && (g.kind === "lab" || g.kind === "symptom") && str(g.key) && prob(g.low) && prob(g.high) && typeof g.changes_routing === "boolean")
      .map((g) => ({ kind: g.kind, key: g.key, low: g.low, high: g.high, changes_routing: g.changes_routing }));
  }
  return out;
}

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
    ...pickRange(o),
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

export function failure(status: number, code: string | null = null, retryAfter: number | null = null): { status: number; body: { error: ShownError }; retryAfter?: number } {
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

const STATUSES = ["met", "unmet", "unknown"];
const ATTESTED = ["C3", "C4", "C5", "C6"];
const strings = (v: unknown): string[] => (Array.isArray(v) ? v.filter(str) : []);
const isStatus = (v: unknown): v is CriterionStatus => str(v) && STATUSES.includes(v);

/** The whitelisted packet (or decline), or null if the body is not a response this page understands. */
export function pickPacket(body: unknown): Packet | PacketDecline | null {
  if (!body || typeof body !== "object") return null;
  const o = body as Record<string, unknown>;
  const request_id = str(o.request_id) ? o.request_id : "";
  if (o.declined === true) {
    return str(o.message) ? { request_id, declined: true, decline_reason: str(o.decline_reason) ? o.decline_reason : null, message: o.message } : null;
  }
  if (o.declined !== false || !Array.isArray(o.criteria) || !Array.isArray(o.evidence)) return null;
  const criteria = o.criteria
    .filter((c): c is Criterion => !!c && str(c.id) && str(c.text) && isStatus(c.status))
    .map((c) => ({ id: c.id, text: c.text, status: c.status, cites: strings(c.cites) }));
  if (criteria.length !== 6) return null;
  return {
    request_id,
    declined: false,
    policy_id: str(o.policy_id) ? o.policy_id : "",
    notice: str(o.notice) ? o.notice : "",
    criteria,
    evidence: o.evidence.filter((e): e is Evidence => !!e && str(e.id) && str(e.text)).map((e) => ({ id: e.id, label: str(e.label) ? e.label : "", text: e.text })),
    gaps: (Array.isArray(o.gaps) ? o.gaps : [])
      .filter((g): g is PacketGap => !!g && str(g.criterion) && str(g.prompt) && (g.kind === "lab" || g.kind === "symptom" || g.kind === "attestation"))
      .map((g) => ({ criterion: g.criterion, kind: g.kind, items: strings(g.items), prompt: g.prompt })),
    summary: (Array.isArray(o.summary) ? o.summary : [])
      .filter((s): s is SummarySentence => !!s && str(s.criterion) && str(s.text) && isStatus(s.status))
      .map((s) => ({ criterion: s.criterion, status: s.status, text: s.text, cites: strings(s.cites) })),
    summary_source: o.summary_source === "model" ? "model" : "template",
    report: pickReport(o.report),
    disclaimer: str(o.disclaimer) ? o.disclaimer : "",
  };
}

export type ForwardedPacket = { status: number; body: { packet: Packet | PacketDecline } | { error: ShownError }; retryAfter?: number };

/** Only C3 to C6 with yes or no pass; an unanswered item is left out, so the service sees it as not yet answered. */
export function cleanAnswers(raw: unknown): Record<string, "yes" | "no"> | null {
  if (raw === undefined || raw === null) return {};
  if (typeof raw !== "object" || Array.isArray(raw)) return null;
  const out: Record<string, "yes" | "no"> = {};
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (!ATTESTED.includes(k)) return null;
    if (v === "unanswered") continue;
    if (v !== "yes" && v !== "no") return null;
    out[k] = v;
  }
  return out;
}

export async function forwardPacket(message: string, attestations: Record<string, "yes" | "no">, visitor: string, cfg: ForwardConfig,
  fetchImpl: typeof fetch = fetch): Promise<ForwardedPacket> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), cfg.timeoutMs);
  try {
    const response = await fetchImpl(`${cfg.url.replace(/\/$/, "")}/packet`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-shared-secret": cfg.secret, "x-visitor-address": visitor },
      body: JSON.stringify({ message, attestations }),
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
      const packet = pickPacket(body);
      return packet ? { status: 200, body: { packet } } : failure(502);
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
