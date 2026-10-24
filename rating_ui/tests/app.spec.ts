import os from "node:os";
import { expect, test, type Page } from "@playwright/test";
import { GuardError, raterSlug } from "../lib/guard";
import { KEY_SENTINEL, NOTE_IDS, ROUND_DIR, readRatingFile } from "./fixture";
import fs from "node:fs";
import path from "node:path";

const LLM = "http://127.0.0.1:3102";
let n = 0;
const uniqueName = (tag: string) => `${tag}-${Date.now()}-${n++}`;

async function startAs(page: Page, name: string) {
  await page.goto("/");
  await expect(page.getByTestId("rater-name-input")).toBeVisible();
  await page.keyboard.type(name); // the name field has focus on load
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("rater")).toHaveText(name);
}

/** y, then 1 2 3 4 1 for the five symptoms, then Enter for the next note: no pointer needed. */
async function rateWithKeys(page: Page, plausible: "y" | "n" = "y") {
  await page.keyboard.press(plausible);
  for (const k of ["1", "2", "3", "4", "1"]) await page.keyboard.press(k);
}

test.describe("rating with the keyboard", () => {
  test("a note can be rated and advanced with keys only", async ({ page }) => {
    const name = uniqueName("kbd");
    await startAs(page, name);
    await expect(page.getByTestId("progress")).toHaveText("0 of 6 rated");
    await rateWithKeys(page);
    await expect(page.getByTestId("progress")).toHaveText("1 of 6 rated");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("note-id")).toContainText("n02");
    await expect(page.getByTestId("save-state")).toHaveText("Saved");
    const file = readRatingFile(name);
    expect(file.kind).toBe("human");
    expect(file.ratings.n01).toMatchObject({
      plausible: "y",
      symptoms: { tremor: "present", fatigue: "possible", photophobia: "absent", joint_stiffness: "none", dizziness: "present" },
    });
  });

  test("a comment can be added with the keyboard", async ({ page }) => {
    const name = uniqueName("cmt");
    await startAs(page, name);
    await page.keyboard.press("c");
    await page.keyboard.type("reads like a template");
    await page.keyboard.press("Escape");
    await page.keyboard.press("n");
    await expect(page.getByTestId("save-state")).toHaveText("Saved");
    expect(readRatingFile(name).ratings.n01.comment).toBe("reads like a template");
  });
});

test.describe("resuming and incomplete notes", () => {
  test("reload resumes at the first unrated note with earlier ratings intact", async ({ page }) => {
    const name = uniqueName("resume");
    await startAs(page, name);
    for (let i = 0; i < 3; i++) {
      await rateWithKeys(page, i === 1 ? "n" : "y");
      await page.keyboard.press("Enter");
    }
    await expect(page.getByTestId("progress")).toHaveText("3 of 6 rated");
    await expect(page.getByTestId("save-state")).toHaveText("Saved");

    await page.reload();
    await expect(page.getByTestId("rater-name-input")).toHaveValue(name); // remembered in this browser
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("progress")).toHaveText("3 of 6 rated");
    await expect(page.getByTestId("note-id")).toContainText("n04");
    await page.getByTestId("chip-n02").click();
    await expect(page.getByTestId("plausible-n")).toHaveAttribute("aria-pressed", "true");
  });

  test("a rater typing the same name again gets their earlier work back", async ({ page, context }) => {
    const name = uniqueName("again");
    await startAs(page, name);
    await rateWithKeys(page);
    await expect(page.getByTestId("save-state")).toHaveText("Saved");
    const fresh = await context.browser()!.newContext(); // no remembered name
    const p2 = await fresh.newPage();
    await startAs(p2, name);
    await expect(p2.getByTestId("progress")).toHaveText("1 of 6 rated");
    await fresh.close();
  });

  test("incomplete notes are marked and the round is not reported finished", async ({ page }) => {
    const name = uniqueName("inc");
    await startAs(page, name);
    await page.keyboard.press("y"); // plausibility only: the symptoms are missing
    await expect(page.getByTestId("chip-n01")).toHaveAttribute("data-complete", "false");
    await expect(page.getByTestId("incomplete-count")).toHaveText("6 incomplete");
    await expect(page.getByTestId("finished")).toHaveCount(0);

    for (let i = 0; i < NOTE_IDS.length; i++) {
      await page.getByTestId(`chip-${NOTE_IDS[i]}`).click();
      await rateWithKeys(page);
    }
    await expect(page.getByTestId("incomplete-count")).toHaveText("0 incomplete");
    await expect(page.getByTestId("finished")).toBeVisible();
  });
});

test.describe("the key cannot be reached", () => {
  test("no route serves key contents", async ({ request, baseURL }) => {
    const paths = [
      "/", "/api/sheet", "/api/session", "/api/ratings", "/api/ratings?rater=../key", "/api/ratings?rater=key.json",
      "/api/key", "/key.json", "/api/ratings/../key.json", "/api/sheet?file=key.json", "/%2e%2e/key.json",
      "/_next/static/../../key.json", "/api/ratings?rater=..%2F..%2Fkey",
    ];
    for (const p of paths) {
      const res = await request.get(baseURL + p);
      expect(await res.text(), p).not.toContain(KEY_SENTINEL);
    }
    for (const p of ["/api/key", "/key.json"]) {
      expect((await request.get(baseURL + p)).status(), p).toBe(404);
    }
  });

  test("the sheet it serves carries no key data", async ({ request, baseURL }) => {
    const body = await (await request.get(baseURL + "/api/sheet")).json();
    expect(Object.keys(body).sort()).toEqual(
      ["notes", "notice", "plausible_values", "symptom_keys", "symptom_values", "version"],
    );
  });

  test("rater names that try to escape stay inside the round directory", async ({ request, baseURL }) => {
    const before = fs.readFileSync(path.join(ROUND_DIR, "key.json"), "utf8");
    const rating = { plausible: "y", symptoms: {} };
    const res = await request.put(baseURL + "/api/ratings", { data: { rater: "../../key", noteId: "n01", rating } });
    expect(res.status()).toBe(200);
    expect(fs.existsSync(path.join(ROUND_DIR, "ratings.key.json"))).toBe(true); // a harmless name inside the dir
    expect(fs.readFileSync(path.join(ROUND_DIR, "key.json"), "utf8")).toBe(before);
    expect(fs.existsSync(path.join(ROUND_DIR, "..", "key.json"))).toBe(false);
    const bad = await request.put(baseURL + "/api/ratings", { data: { rater: "///", noteId: "n01", rating } });
    expect(bad.status()).toBe(400); // no usable characters: the guard rejects it
    const bad2 = await request.get(baseURL + "/api/ratings?rater=%2F%2F");
    expect(bad2.status()).toBe(400);
  });

  test("unknown notes and bad values are rejected", async ({ request, baseURL }) => {
    const name = uniqueName("bad");
    const put = (noteId: string, rating: unknown) =>
      request.put(baseURL + "/api/ratings", { data: { rater: name, noteId, rating } });
    expect((await put("n99", { plausible: "y" })).status()).toBe(400);
    expect((await put("n01", { plausible: "maybe" })).status()).toBe(400);
    expect((await put("n01", { symptoms: { tremor: "sometimes" } })).status()).toBe(400);
    expect((await put("n01", { symptoms: { mystery: "present" } })).status()).toBe(400);
    expect((await put("n01", { plausible: "y" })).status()).toBe(200);
  });
});

test.describe("the rater kind is fixed at launch", () => {
  test("a kind in the request body is ignored (human session)", async ({ request, baseURL }) => {
    const name = uniqueName("kind");
    const res = await request.put(baseURL + "/api/ratings", {
      data: { rater: name, kind: "llm", model_id: "x", noteId: "n01", rating: { plausible: "y" } },
    });
    expect(res.status()).toBe(200);
    const file = readRatingFile(name);
    expect(file.kind).toBe("human");
    expect(file.model_id).toBeNull();
  });

  test("an llm session writes the llm file under its fixed name and model", async ({ request }) => {
    const session = await (await request.get(LLM + "/api/session")).json();
    expect(session).toMatchObject({ kind: "llm", fixedRater: "test-reviewer" });
    const res = await request.put(LLM + "/api/ratings", {
      data: { rater: "someone-else", kind: "human", noteId: "n02", rating: { plausible: "n", reason: "template residue" } },
    });
    expect(res.status()).toBe(200);
    const file = readRatingFile("test-reviewer");
    expect(file).toMatchObject({ kind: "llm", rater: "test-reviewer", model_id: "claude-sonnet-5-5", prompt_version: "1" });
    expect(file.ratings.n02.reason).toBe("template residue");
    expect(fs.existsSync(path.join(ROUND_DIR, "ratings.someone-else.json"))).toBe(false);
  });
});

test.describe("local binding", () => {
  test("the app is not reachable on a non-loopback address", async ({ request }) => {
    const external = Object.values(os.networkInterfaces())
      .flat()
      .find((i) => i && i.family === "IPv4" && !i.internal);
    test.skip(!external, "no non-loopback IPv4 address on this machine");
    await expect(request.get(`http://${external!.address}:3101/api/session`, { timeout: 3000 })).rejects.toThrow();
  });
});

test.describe("file naming matches the Python side", () => {
  test("rater slugs agree with data_gen's rater_slug", async () => {
    const cases: [string, string | null][] = JSON.parse(fs.readFileSync(path.join(__dirname, "slug-cases.json"), "utf8"));
    for (const [name, slug] of cases) {
      if (slug === null) expect(() => raterSlug(name), name).toThrow(GuardError);
      else expect(raterSlug(name), name).toBe(slug);
    }
  });
});
