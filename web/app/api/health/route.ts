import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/** The model hash the running service reports, for the model-card tab. Nothing else from the service is passed on. */
export async function GET(): Promise<NextResponse> {
  const url = process.env.AGENT_URL;
  const headers = { "cache-control": "no-store" };
  if (!url) return NextResponse.json({ model_hash: null }, { headers });
  try {
    const response = await fetch(`${url.replace(/\/$/, "")}/healthz`, { cache: "no-store", signal: AbortSignal.timeout(10_000) });
    const body = (await response.json()) as { model_hash?: unknown };
    const hash = typeof body.model_hash === "string" && /^[0-9a-f]{64}$/.test(body.model_hash) ? body.model_hash : null;
    return NextResponse.json({ model_hash: hash }, { headers });
  } catch {
    return NextResponse.json({ model_hash: null }, { headers });
  }
}
