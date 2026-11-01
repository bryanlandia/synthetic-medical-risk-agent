import { NextRequest, NextResponse } from "next/server";
import { cleanAnswers, describe, failure, forwardPacket, visitorAddress, type ForwardedPacket } from "@/lib/forward";

export const maxDuration = 60;
export const dynamic = "force-dynamic";

const MAX_BODY_BYTES = 70_000;

function respond(result: ForwardedPacket): NextResponse {
  const headers: Record<string, string> = { "cache-control": "no-store" };
  if (result.retryAfter) headers["retry-after"] = String(result.retryAfter);
  return NextResponse.json(result.body, { status: result.status, headers });
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const url = process.env.AGENT_URL;
  const secret = process.env.AGENT_SHARED_SECRET;
  if (!url || !secret) return NextResponse.json({ error: describe(401, null, null) }, { status: 500, headers: { "cache-control": "no-store" } });
  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) return respond(failure(413));
  let parsed: { message?: unknown; attestations?: unknown } = {};
  try {
    parsed = JSON.parse(raw) as typeof parsed;
  } catch {
    return respond(failure(422));
  }
  const answers = cleanAnswers(parsed.attestations);
  if (typeof parsed.message !== "string" || !parsed.message.trim() || answers === null) return respond(failure(422));
  return respond(await forwardPacket(parsed.message, answers, visitorAddress(request.headers), { url, secret, timeoutMs: 45_000 }));
}
