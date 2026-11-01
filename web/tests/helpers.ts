import { expect, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import type { CaseRecord } from "../lib/types";

export const CASES: CaseRecord[] = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "content", "cases.json"), "utf8")).cases;

export type Kind = "releasable" | "blocked" | "unmet";

/** Each case's kind, found by asking the (scripted) service the way the page does. */
export async function classify(request: APIRequestContext): Promise<Record<string, { kind: Kind; statuses: Record<string, string> }>> {
  const out: Record<string, { kind: Kind; statuses: Record<string, string> }> = {};
  for (const c of CASES) {
    const r = await request.post("/api/packet", { data: { message: c.message, attestations: c.answers } });
    const packet = (await r.json()).packet;
    const statuses = Object.fromEntries(packet.criteria.map((x: { id: string; status: string }) => [x.id, x.status]));
    const values = Object.values(statuses);
    out[c.id] = { statuses, kind: values.every((v) => v === "met") ? "releasable" : values.includes("unknown") ? "blocked" : "unmet" };
  }
  return out;
}

export const first = (kinds: Record<string, { kind: Kind }>, kind: Kind, skip = 0): CaseRecord => CASES.filter((c) => kinds[c.id].kind === kind)[skip];

export const openCase = async (page: Page, c: CaseRecord) => {
  await page.getByRole("button", { name: c.request_code }).click();
  await expect(page.getByTestId("case-title")).toHaveText(c.request_code);
};

export const waitForPacket = (page: Page) => expect(page.getByTestId("packet-checklist")).toBeVisible();
export const backToQueue = (page: Page) => page.getByRole("button", { name: "Back to the queue" }).click();
export const dialogButton = (page: Page, name: string) => page.getByRole("dialog").getByRole("button", { name, exact: true });
