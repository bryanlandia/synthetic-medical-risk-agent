import { NextRequest, NextResponse } from "next/server";
import { cleanEstimateInputs, describe, failure, forwardEstimate, visitorAddress, type ForwardedEstimate } from "@/lib/forward";

export const maxDuration = 30;
export const dynamic = "force-dynamic";

const MAX_BODY_BYTES = 5_000;

function respond(result: ForwardedEstimate): NextResponse {
  const headers: Record<string, string> = { "cache-control": "no-store" };
  if (result.retryAfter) headers["retry-after"] = String(result.retryAfter);
  return NextResponse.json(result.body, { status: result.status, headers });
}

/** The what-if estimate: the labs and symptoms the visitor set, forwarded with the secret; no language model is behind it. */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const url = process.env.AGENT_URL;
  const secret = process.env.AGENT_SHARED_SECRET;
  if (!url || !secret) return NextResponse.json({ error: describe(401, null, null) }, { status: 500, headers: { "cache-control": "no-store" } });
  const raw = await request.text();
  if (raw.length > MAX_BODY_BYTES) return respond(failure(413));
  let inputs = null;
  try {
    inputs = cleanEstimateInputs(JSON.parse(raw));
  } catch {
    inputs = null;
  }
  if (!inputs) return NextResponse.json({ error: { code: "invalid_inputs", message: "Those values are outside what the demo accepts." } }, { status: 422, headers: { "cache-control": "no-store" } });
  return respond(await forwardEstimate(inputs, visitorAddress(request.headers), { url, secret, timeoutMs: 8_000 }));
}
