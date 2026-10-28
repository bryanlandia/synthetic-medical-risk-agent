"use client";

import { useEffect, useState } from "react";
import { analyticsEnabled, clickEvent, initOptions, POSTHOG_KEY, privacySignalOn, resultEvent, sanitizeRef, type AnalyticsEvent } from "@/lib/analytics";

type Client = { capture: (event: string, properties?: Record<string, string>) => void; opt_out_capturing: () => void; register: (p: Record<string, string>) => void };

/** The started SDK, shared with the event helpers. Null until started, so every helper is a no-op when analytics is off. */
let client: Client | null = null;
let starting = false;
/** The visitor's choice. Kept here as well as in the SDK because the SDK's own opt-out does not stop cookieless capture. */
let countingOff = false;
const OPT_OUT_KEY = "vk-analytics-optout";

function send(e: AnalyticsEvent | null) {
  if (client && e && !countingOff) client.capture(e.event, e.properties);
}

function storedOptOut(): boolean {
  try {
    return window.localStorage.getItem(OPT_OUT_KEY) === "1";
  } catch {
    return false;
  }
}

/** Count the agent's answer by kind only: never its text, probability or report. */
export function trackResult(source: string, kind: string) {
  send(resultEvent(source, kind));
}

export function Analytics() {
  const [active, setActive] = useState(false);
  const [optedOut, setOptedOut] = useState(false);

  useEffect(() => {
    if (!analyticsEnabled || privacySignalOn(navigator as unknown as Parameters<typeof privacySignalOn>[0])) return;
    if (storedOptOut()) {
      countingOff = true; // chose not to be counted on an earlier visit: nothing starts
      return;
    }
    const onClick = (event: MouseEvent) => {
      const el = (event.target as Element | null)?.closest?.("[data-track]");
      send(clickEvent(el?.getAttribute("data-track")));
    };
    let live = true;
    if (!client && !starting) {
      starting = true;
      import("posthog-js").then(({ default: posthog }) => {
        posthog.init(POSTHOG_KEY, { ...initOptions(), before_send: (event) => (countingOff ? null : event) });
        const ref = sanitizeRef(new URLSearchParams(window.location.search).get("ref"));
        if (ref) posthog.register({ ref });
        client = posthog as unknown as Client;
        client.capture("$pageview");
        if (live) setActive(true);
      });
    } else if (client) {
      setActive(true);
    }
    document.addEventListener("click", onClick);
    return () => {
      live = false;
      document.removeEventListener("click", onClick);
    };
  }, []);

  if (!analyticsEnabled || !active) return null;
  return (
    <div className="notice-bar" role="region" aria-label="Analytics notice" data-testid="analytics-notice">
      {optedOut ? (
        <span>Counting is off for this visit.</span>
      ) : (
        <>
          <span>Visits to this demo and clicks on its buttons are counted anonymously. Nothing you type is collected and your screen is not recorded.</span>{" "}
          <button
            onClick={() => {
              countingOff = true;
              client?.opt_out_capturing();
              try {
                window.localStorage.setItem(OPT_OUT_KEY, "1");
              } catch {
                /* the choice still holds for this visit */
              }
              setOptedOut(true);
            }}
          >
            Don&apos;t count my visit
          </button>
        </>
      )}
    </div>
  );
}
