import type { Answer, AttestedId, Packet, PacketDecline, ShownError } from "./types";

export type PacketResult = { kind: "done"; packet: Packet | PacketDecline } | { kind: "error"; error: ShownError };

/** One request to this app's packet route. The caller keeps the result, so a case is requested once. */
export async function requestPacket(message: string, attestations: Record<AttestedId, Answer>, fetchImpl: typeof fetch = fetch): Promise<PacketResult> {
  try {
    const response = await fetchImpl("/api/packet", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message, attestations }),
    });
    const body = (await response.json()) as { packet?: Packet | PacketDecline; error?: ShownError };
    if (response.ok && body.packet) return { kind: "done", packet: body.packet };
    return { kind: "error", error: body.error ?? { code: "error", message: "Something went wrong. Please try again." } };
  } catch {
    return { kind: "error", error: { code: "network", message: "Could not reach the demo. Please check your connection and try again." } };
  }
}
