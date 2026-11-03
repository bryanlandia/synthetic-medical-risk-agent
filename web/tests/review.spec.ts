import { expect, test } from "@playwright/test";
import { HINTS, PURPOSE_PARAGRAPHS, PURPOSE_TITLE, DEMO_NOTES, formatReceived } from "../lib/copy";
import { STORAGE_KEY } from "../lib/store";
import { backToQueue, CASES, classify, dialogButton, first, openCase, waitForPacket, type Kind } from "./helpers";

let kinds: Awaited<ReturnType<typeof classify>>;
test.beforeAll(async ({ request }) => {
  kinds = await classify(request);
});

const VERDICT = /\b(approved|denied|eligible|qualifies)\b/i;
const packetRequests = (page: import("@playwright/test").Page) => {
  const bodies: { message: string; attestations: Record<string, string> }[] = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/packet")) bodies.push(JSON.parse(r.postData() ?? "{}"));
  });
  return bodies;
};

test("the 30 cases cover releasable, blocked and unmet-only packets", () => {
  const count = (k: Kind) => CASES.filter((c) => kinds[c.id].kind === k).length;
  expect(count("releasable")).toBeGreaterThanOrEqual(3);
  expect(count("blocked")).toBeGreaterThanOrEqual(5);
  expect(count("unmet")).toBeGreaterThanOrEqual(5);
});

// --- 4.1 the queue ------------------------------------------------------------------------------------------------

test("thirty New rows show their fields, and no packet is requested or shown for an unopened case", async ({ page }) => {
  const bodies = packetRequests(page);
  await page.goto("/");
  const rows = page.getByTestId("queue").locator("tbody tr");
  await expect(rows).toHaveCount(30);
  for (const c of CASES) {
    const row = page.getByTestId(`row-${c.ordinal}`);
    await expect(row).toContainText(c.request_code);
    await expect(row).toContainText(c.patient_id);
    await expect(row).toContainText(c.insurer);
    await expect(row).toContainText(c.preparer);
    await expect(row).toContainText(formatReceived(c.received));
    await expect(row).toContainText("of 4 answered");
    await expect(page.getByTestId(`chip-${c.ordinal}`)).toHaveText("New");
  }
  const text = await page.getByTestId("queue").innerText();
  expect(text).not.toMatch(/%|\bunmet\b|\bunknown\b|\bmet\b/i);
  expect(bodies).toHaveLength(0);
});

test("the status filter lists only matching cases", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("queue").locator("tbody tr")).toHaveCount(30);
  await page.getByRole("button", { name: "Released", exact: true }).click();
  await expect(page.getByText("No requests with this status.")).toBeVisible();
  await page.getByRole("button", { name: "New", exact: true }).click();
  await expect(page.getByTestId("queue").locator("tbody tr")).toHaveCount(30);
});

// --- 4.2 the explanation ------------------------------------------------------------------------------------------

test("the intro card explains what the packet is for, and the words are free of verdict wording", async ({ page }) => {
  await page.goto("/");
  const card = page.getByTestId("intro-card");
  await expect(card).toBeVisible();
  await expect(card.getByRole("heading", { name: PURPOSE_TITLE })).toBeVisible();
  const text = (await card.innerText()).toLowerCase();
  for (const phrase of ["kessler family foundation", "also fictional", "treatable if caught early", "speed insurer coverage", "aid diagnosis", "pet-ct", "expensive", "insurer", "criteria", "evidence", "missing", "supervisor", "decides nothing about the patient's care or about coverage"]) expect(text).toContain(phrase);
  expect([...PURPOSE_PARAGRAPHS, ...Object.values(HINTS), PURPOSE_TITLE].join(" ")).not.toMatch(VERDICT);
  expect(text).not.toMatch(VERDICT);
});

test("the three terms carry keyboard-reachable hints", async ({ page }) => {
  await page.goto("/");
  const card = page.getByTestId("intro-card");
  for (const term of ["PET-CT", "prior authorization", "packet"]) {
    const span = card.locator("span[tabindex='0']", { hasText: new RegExp(`^${term}$`) }).first();
    await span.focus();
    await expect(page.getByRole("tooltip").filter({ hasText: HINTS[term as keyof typeof HINTS] })).toBeVisible();
  }
});

test("the card stays dismissed across a reload and Reset brings it back", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Got it, hide this" }).click();
  await expect(page.getByTestId("intro-card")).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId("queue")).toBeVisible();
  await expect(page.getByTestId("intro-card")).toHaveCount(0);
  await page.getByRole("button", { name: "Reset demo" }).click();
  await dialogButton(page, "Reset").click();
  await expect(page.getByTestId("intro-card")).toBeVisible();
});

test("the help dialog from a case shows the same text and closes with Escape", async ({ page }) => {
  await page.goto("/");
  await openCase(page, CASES[0]);
  const help = page.getByRole("button", { name: PURPOSE_TITLE });
  await help.click();
  const dialog = page.getByTestId("help-dialog");
  for (const p of PURPOSE_PARAGRAPHS) await expect(dialog).toContainText(p);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(help).toBeFocused();
});

// --- 5.1 the case view --------------------------------------------------------------------------------------------

test("the first open makes one request with the stored message and the preparer's answers, and reopening makes none", async ({ page }) => {
  const bodies = packetRequests(page);
  await page.goto("/");
  const c = first(kinds, "releasable");
  await openCase(page, c);
  await waitForPacket(page);
  await expect(page.getByTestId("case-status")).toHaveText("In review");
  expect(bodies).toHaveLength(1);
  expect(bodies[0]).toEqual({ message: c.message, attestations: c.answers });
  await backToQueue(page);
  await expect(page.getByTestId(`chip-${c.ordinal}`)).toHaveText("In review");
  await openCase(page, c);
  await waitForPacket(page);
  expect(bodies).toHaveLength(1);
});

test("the chart, the sent message, the evidence and the estimate are beside the checklist", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "releasable");
  await openCase(page, c);
  await waitForPacket(page);
  await expect(page.getByTestId("chart")).toContainText(c.patient_id);
  for (const lab of c.chart.labs) await expect(page.getByTestId(`range-${lab.lab}`)).toContainText(`${lab.ref_lo}–${lab.ref_hi}`);
  await page.getByText("Show the message sent to the service").click();
  expect((await page.getByTestId("sent-message").innerText()).trim()).toBe(c.message.trim());
  await expect(page.getByTestId("crit-status-C1")).toHaveText("Met");
  await expect(page.getByTestId("criterion-C1")).toContainText("above the policy threshold");
  await expect(page.getByTestId("criterion-C1")).toContainText("lab reference range");
  await expect(page.getByTestId("estimate")).toContainText("decides no criterion");
  await expect(page.getByTestId("summary-source")).toBeVisible();
  expect(await page.getByTestId("packet-summary").locator("li").count()).toBeGreaterThan(0);
});

test("the preparer's answers are shown and cannot be changed", async ({ page }) => {
  await page.goto("/");
  const c = CASES[0];
  await openCase(page, c);
  await waitForPacket(page);
  const answers = page.getByTestId("answers");
  await expect(answers).toContainText("preparing clinician");
  await expect(answers).toContainText("simulated");
  for (const id of ["C3", "C4", "C5", "C6"] as const) await expect(page.getByTestId(`answer-${id}`)).toHaveText({ yes: "Yes", no: "No", unanswered: "Not yet answered" }[c.answers[id]]);
  expect(await answers.locator("input, select, textarea, [role=radio], [role=combobox], [role=switch]").count()).toBe(0);
});

test("a rate limit is explained, the case stays open, and trying again works", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/packet", async (route) => {
    calls += 1;
    if (calls === 1) await route.fulfill({ status: 429, headers: { "retry-after": "30" }, contentType: "application/json", body: JSON.stringify({ error: { code: "rate_limited", message: "You have sent a lot of requests. Please wait about 30 seconds and try again." } }) });
    else await route.continue();
  });
  await page.goto("/");
  await openCase(page, CASES[0]);
  await expect(page.getByTestId("packet-error")).toContainText("about 30 seconds");
  await expect(page.getByTestId("case-status")).toHaveText("In review");
  await page.getByRole("button", { name: "Try again" }).click();
  await waitForPacket(page);
  expect(calls).toBe(2);
});

// --- 5.2 the demo notes -------------------------------------------------------------------------------------------

test("each simulated element carries its quiet Demo note, and nothing in the flow talks about money or accuracy", async ({ page }) => {
  await page.goto("/");
  for (const key of ["role", "queue", "storage"] as const) await expect(page.getByTestId(`demo-note-${key}`)).toContainText(DEMO_NOTES[key]);
  const unmetCase = first(kinds, "unmet");
  await openCase(page, unmetCase);
  await waitForPacket(page);
  await expect(page.getByTestId("demo-note-answers")).toHaveCount(0); // the answers heading says "simulated" instead
  for (const key of ["policy", "estimate", "summary", "rationale"] as const) await expect(page.getByTestId(`demo-note-${key}`)).toContainText(DEMO_NOTES[key]);
  await page.getByRole("button", { name: "Return with a note" }).click();
  await expect(page.getByRole("dialog").getByTestId("demo-note-returnNote")).toBeVisible();
  await dialogButton(page, "Cancel").click();
  for (const key of ["role", "policy"] as const) {
    const note = page.getByTestId(`demo-note-${key}`).first();
    if (await note.count()) expect(await note.locator("button, [role=button]").count()).toBe(0); // not a dismissible banner
  }
  const flow = (await page.locator("main").innerText()).toLowerCase();
  expect(flow).not.toMatch(/\$|saving|auc\b|accuracy/);
});

// --- 6.1 the decisions --------------------------------------------------------------------------------------------

test("every criterion met: Release is open without a rationale, and confirming releases", async ({ page }) => {
  const bodies = packetRequests(page);
  await page.goto("/");
  const c = first(kinds, "releasable");
  await openCase(page, c);
  await waitForPacket(page);
  await expect(page.getByRole("button", { name: "Release", exact: true })).toBeEnabled();
  await expect(page.getByTestId("rationale")).toHaveCount(0);
  const before = bodies.length;
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Nothing is transmitted");
  await dialogButton(page, "Release").click();
  await expect(page.getByTestId("case-status")).toHaveText("Released");
  expect(bodies.length).toBe(before); // a decision sends nothing
});

test("an unknown criterion blocks Release, names the gap, and offers Return", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "blocked");
  await openCase(page, c);
  await waitForPacket(page);
  await expect(page.getByRole("button", { name: "Release", exact: true })).toBeDisabled();
  await expect(page.getByTestId("release-block")).toContainText("unknown");
  await expect(page.getByRole("button", { name: "Return with a note" })).toBeEnabled();
});

test("an unmet criterion needs the supervisor's own rationale of 20 characters before Release", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "unmet");
  await openCase(page, c);
  await waitForPacket(page);
  const release = page.getByRole("button", { name: "Release", exact: true });
  await expect(release).toBeDisabled();
  const box = page.getByTestId("rationale");
  await box.fill("too short");
  await expect(release).toBeDisabled();
  await box.fill("I have reviewed the chart and the history supports this request.");
  await expect(release).toBeEnabled();
  await release.click();
  await dialogButton(page, "Release").click();
  await expect(page.getByTestId("case-status")).toHaveText("Released");
  await expect(page.getByTestId("released-rationale")).toHaveText("I have reviewed the chart and the history supports this request.");
});

test("returning needs a note, shows a Returned chip with the note, and the case filter finds it", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "blocked");
  await openCase(page, c);
  await waitForPacket(page);
  await page.getByRole("button", { name: "Return with a note" }).click();
  const confirm = dialogButton(page, "Return");
  await expect(confirm).toBeDisabled();
  await page.getByTestId("return-note").fill("Please add the missing result.");
  await confirm.click();
  await expect(page.getByTestId("case-status")).toHaveText("Returned");
  await expect(page.getByTestId("return-note-shown")).toContainText("Please add the missing result.");
  await backToQueue(page);
  await expect(page.getByTestId(`chip-${c.ordinal}`)).toHaveText("Returned");
  await page.getByRole("button", { name: "Returned", exact: true }).click();
  await expect(page.getByTestId("queue").locator("tbody tr")).toHaveCount(1);
});

test("closing sets Closed, and a closed or released case has no decision controls", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "unmet");
  await openCase(page, c);
  await waitForPacket(page);
  await page.getByRole("button", { name: "Close, criteria not met" }).click();
  await dialogButton(page, "Close request").click();
  await expect(page.getByTestId("case-status")).toHaveText("Closed");
  await expect(page.getByTestId("decision-bar")).toHaveCount(0);
  await expect(page.getByTestId("closed-note")).toContainText("Nothing was sent");
  await backToQueue(page);
  await expect(page.getByTestId(`chip-${c.ordinal}`)).toHaveText("Closed");
});

test("a dialog returns focus to the control that opened it", async ({ page }) => {
  await page.goto("/");
  await openCase(page, first(kinds, "releasable"));
  await waitForPacket(page);
  const release = page.getByRole("button", { name: "Release", exact: true });
  await release.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(release).toBeFocused();
});

// --- 3.1 persistence ----------------------------------------------------------------------------------------------

test("a returned case and its note survive a reload", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "blocked");
  await openCase(page, c);
  await waitForPacket(page);
  await page.getByRole("button", { name: "Return with a note" }).click();
  await page.getByTestId("return-note").fill("Please confirm the missing result.");
  await dialogButton(page, "Return").click();
  await backToQueue(page);
  await page.reload();
  await expect(page.getByTestId(`chip-${c.ordinal}`)).toHaveText("Returned");
  const bodies = packetRequests(page);
  await openCase(page, c);
  await expect(page.getByTestId("return-note-shown")).toContainText("Please confirm the missing result.");
  await waitForPacket(page);
  expect(bodies).toHaveLength(0); // the packet came back from the browser, not the service
});

test("Reset restores 30 New cases after confirmation, and cancelling changes nothing", async ({ page }) => {
  await page.goto("/");
  const c = CASES[3];
  await openCase(page, c);
  await waitForPacket(page);
  await backToQueue(page);
  await page.getByRole("button", { name: "Reset demo" }).click();
  await dialogButton(page, "Cancel").click();
  await expect(page.getByTestId(`chip-${c.ordinal}`)).toHaveText("In review");
  await page.getByRole("button", { name: "Reset demo" }).click();
  await dialogButton(page, "Reset").click();
  await expect(page.getByTestId(`chip-${c.ordinal}`)).toHaveText("New");
  await page.reload();
  await expect(page.getByTestId(`chip-${c.ordinal}`)).toHaveText("New");
});

test("progress made for other data is discarded", async ({ page }) => {
  await page.goto("/");
  const c = CASES[2];
  await openCase(page, c);
  await waitForPacket(page);
  await page.evaluate((key) => {
    const saved = JSON.parse(window.localStorage.getItem(key)!);
    saved.casesHash = "some-other-hash";
    window.localStorage.setItem(key, JSON.stringify(saved));
  }, STORAGE_KEY);
  await page.reload();
  await expect(page.getByTestId(`chip-${c.ordinal}`)).toHaveText("New");
});

test("nothing is stored on the server: progress lives only in the browser", async ({ page, request }) => {
  await page.goto("/");
  await openCase(page, CASES[1]);
  await waitForPacket(page);
  expect(await page.evaluate((key) => window.localStorage.getItem(key) !== null, STORAGE_KEY)).toBe(true);
  const other = await request.get("/");
  expect(await other.text()).not.toContain(CASES[1].request_code + " In review");
});

test("a visit that changes nothing writes nothing to storage, and an action writes only the review progress", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByTestId("queue")).toBeVisible();
  await page.getByRole("button", { name: "How it works" }).click();
  await page.getByRole("menuitem", { name: "About this project" }).click();
  expect(await context.cookies()).toEqual([]);
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  await page.getByRole("button", { name: "Back to the queue" }).click();
  await openCase(page, CASES[5]);
  await waitForPacket(page);
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([STORAGE_KEY]);
  expect(await context.cookies()).toEqual([]);
  await backToQueue(page);
  await page.getByRole("button", { name: "Reset demo" }).click();
  await dialogButton(page, "Reset").click();
  expect(await page.evaluate(() => localStorage.length)).toBe(0); // reset clears it
});
