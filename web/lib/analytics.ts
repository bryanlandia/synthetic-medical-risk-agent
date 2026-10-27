/**
 * Anonymous visit and click counting with PostHog.
 *
 * Everything here is pure or a no-op unless a project key is configured, so the rules can be unit-tested without a browser:
 * what may be sent (a closed set of labels, never text a visitor typed or anything the agent said), what is never started
 * (a Do Not Track or Global Privacy Control visitor), and how a `ref` link value is reduced.
 */

/** The public project key, inlined at build time. Unset means analytics is off and nothing here sends anything. */
export const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY || "";
export const analyticsEnabled = POSTHOG_KEY !== "";

/** The site's own path that the server forwards to PostHog (see next.config.mjs). */
export const INGEST_PATH = "/ingest";

export const TABS = ["chart", "free", "card", "about"] as const;
export const RESULT_SOURCES = ["chart", "free_text"] as const;
export const RESULT_KINDS = ["scored", "declined", "error"] as const;

const FIXED_CLICKS = new Set(["run_check", "sent_message_expander", "send_free_text"]);
const CLICK_PATTERNS = [
  new RegExp(`^tab:(${TABS.join("|")})$`),
  /^patient:[a-z0-9-]{1,40}$/,
  /^example:[a-z0-9-]{1,40}$/,
  /^link:[a-z0-9.-]{1,100}$/,
];

export type AnalyticsEvent = { event: string; properties: Record<string, string> };

/** Whether a click name is one of the fixed set or a fixed pattern. Anything else is dropped, never sent. */
export function validClickName(name: unknown): name is string {
  return typeof name === "string" && (FIXED_CLICKS.has(name) || CLICK_PATTERNS.some((p) => p.test(name)));
}

export function clickEvent(name: unknown): AnalyticsEvent | null {
  return validClickName(name) ? { event: "ui_click", properties: { element: name } } : null;
}

export function resultEvent(source: unknown, kind: unknown): AnalyticsEvent | null {
  if (!(RESULT_SOURCES as readonly unknown[]).includes(source) || !(RESULT_KINDS as readonly unknown[]).includes(kind)) return null;
  return { event: "result_shown", properties: { source: source as string, kind: kind as string } };
}

/** A `ref` link value reduced to lowercase letters, digits, hyphen and underscore, at most 32 characters, or null. */
export function sanitizeRef(raw: string | null | undefined): string | null {
  const cleaned = (raw ?? "").toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 32);
  return cleaned === "" ? null : cleaned;
}

/** The name for a link that leaves the site: its host only, or null for a link that stays. */
export function outboundLinkName(href: string | undefined, here: string = ""): string | null {
  try {
    const host = new URL(href ?? "", here || "http://localhost").hostname.toLowerCase();
    if (!href || !/^https?:/i.test(href) || host === "" || host === (here ? new URL(here).hostname : "localhost")) return null;
    const name = `link:${host}`;
    return validClickName(name) ? name : null;
  } catch {
    return null;
  }
}

export type Privacy = { doNotTrack?: string | null; globalPrivacyControl?: boolean; msDoNotTrack?: string | null };

/** True when the browser asks not to be tracked: nothing is started at all. */
export function privacySignalOn(nav: Privacy): boolean {
  return nav.globalPrivacyControl === true || ["1", "yes"].includes(String(nav.doNotTrack ?? nav.msDoNotTrack ?? ""));
}

/** The SDK options: no recording, no automatic capture, no automatic page view, no stored identifier, first-party path. */
export function initOptions(uiHost?: string) {
  return {
    api_host: INGEST_PATH,
    ...(uiHost ? { ui_host: uiHost } : {}),
    cookieless_mode: "always" as const,
    persistence: "memory" as const,
    disable_session_recording: true,
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: false,
    capture_dead_clicks: false,
    capture_exceptions: false,
    disable_surveys: true,
    advanced_disable_flags: true,
    person_profiles: "identified_only" as const,
    respect_dnt: true,
  };
}
