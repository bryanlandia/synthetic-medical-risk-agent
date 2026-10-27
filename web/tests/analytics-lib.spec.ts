import { expect, test } from "@playwright/test";
import { clickEvent, initOptions, outboundLinkName, privacySignalOn, resultEvent, sanitizeRef, validClickName } from "../lib/analytics";

test("the SDK is configured to record nothing, capture nothing automatically and store nothing", () => {
  const o = initOptions();
  expect(o).toMatchObject({
    api_host: "/ingest", cookieless_mode: "always", persistence: "memory", disable_session_recording: true, autocapture: false,
    capture_pageview: false, capture_pageleave: false, capture_dead_clicks: false, capture_exceptions: false, disable_surveys: true,
    advanced_disable_flags: true, person_profiles: "identified_only", respect_dnt: true,
  });
});

test("a ref value is reduced to a short, safe label", () => {
  expect(sanitizeRef("Ode!!<script>")).toBe("odescript");
  expect(sanitizeRef("ode")).toBe("ode");
  expect(sanitizeRef("a_b-C")).toBe("a_b-c");
  expect(sanitizeRef("x".repeat(100))).toBe("x".repeat(32));
  expect(sanitizeRef("")).toBeNull();
  expect(sanitizeRef("!!!")).toBeNull();
  expect(sanitizeRef(null)).toBeNull();
});

test("only fixed click names are sent", () => {
  for (const ok of ["run_check", "send_free_text", "sent_message_expander", "tab:about", "tab:chart", "patient:unit-and-missing", "example:forced-low", "link:github.com"]) {
    expect(validClickName(ok), ok).toBe(true);
    expect(clickEvent(ok)).toEqual({ event: "ui_click", properties: { element: ok } });
  }
  for (const bad of ["opt_out", "tab:admin", "patient:Some One", "example:", "link:", "link:evil.com/path?x=1", "I typed this text", "", null, undefined, 7]) {
    expect(validClickName(bad), String(bad)).toBe(false);
    expect(clickEvent(bad)).toBeNull();
  }
});

test("a result is counted by source and kind only", () => {
  expect(resultEvent("chart", "scored")).toEqual({ event: "result_shown", properties: { source: "chart", kind: "scored" } });
  expect(resultEvent("free_text", "declined")?.properties.kind).toBe("declined");
  expect(resultEvent("free_text", "0.81 probability")).toBeNull();
  expect(resultEvent("my message", "scored")).toBeNull();
});

test("a link that leaves the site is named by its host alone", () => {
  expect(outboundLinkName("https://github.com/bryanlandia/synthetic-medical-risk-agent?tab=readme")).toBe("link:github.com");
  expect(outboundLinkName("/relative/path")).toBeNull();
  expect(outboundLinkName("#section")).toBeNull();
  expect(outboundLinkName("mailto:someone@example.com")).toBeNull();
  expect(outboundLinkName(undefined)).toBeNull();
});

test("Do Not Track and Global Privacy Control are honored", () => {
  expect(privacySignalOn({ doNotTrack: "1" })).toBe(true);
  expect(privacySignalOn({ doNotTrack: "yes" })).toBe(true);
  expect(privacySignalOn({ globalPrivacyControl: true })).toBe(true);
  expect(privacySignalOn({ doNotTrack: "0" })).toBe(false);
  expect(privacySignalOn({ doNotTrack: null })).toBe(false);
  expect(privacySignalOn({})).toBe(false);
});
