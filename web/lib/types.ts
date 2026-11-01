/** What the page shows from the agent service: a whitelist of its response, never the raw body. */

export type DataQuality = { type: string; lab?: string | null };

export type Report = {
  probability: number;
  uncertain: boolean;
  symptoms: Record<string, string>;
  labs_used: { lab: string; value: number; unit: string }[];
  data_quality: DataQuality[];
  evidence: string[];
  interval?: [number, number];
  gaps?: Gap[];
  disclaimer: string;
};

/** A finding the record lacks: the probability range if only that item were obtained. */
export type Gap = { kind: "lab" | "symptom"; key: string; low: number; high: number; changes_routing: boolean };

export type Analysis = {
  request_id: string;
  declined: boolean;
  decline_reason: string | null;
  reply: string;
  reply_source: "model" | "template";
  report: Report | null;
  usage: { input_tokens: number; output_tokens: number; cost_usd: number };
};

export type ShownError = { code: string; message: string; retry_after?: number };

export type Chart = {
  labs: {
    lab: string; name: string; abbr: string; value: number | null; unit: string;
    ref_lo: number; ref_hi: number; ref_unit: string; flag: "H" | "L" | null;
  }[];
  note: string;
};

export type DemoPatient = {
  slug: string;
  title: string;
  look_for: string;
  patient_id: string;
  split: "dev";
  chart: Chart;
  message: string;
};

/** The scan-readiness packet, as the page shows it: a whitelist of the service's response. */
export type CriterionStatus = "met" | "unmet" | "unknown";
export type Answer = "yes" | "no" | "unanswered";
export type AttestedId = "C3" | "C4" | "C5" | "C6";
export type Criterion = { id: string; text: string; status: CriterionStatus; cites: string[] };
export type Evidence = { id: string; label: string; text: string };
export type PacketGap = { criterion: string; kind: "lab" | "symptom" | "attestation"; items: string[]; prompt: string };
export type SummarySentence = { criterion: string; status: CriterionStatus; text: string; cites: string[] };

export type Packet = {
  request_id: string;
  declined: false;
  policy_id: string;
  notice: string;
  criteria: Criterion[];
  evidence: Evidence[];
  gaps: PacketGap[];
  summary: SummarySentence[];
  summary_source: "model" | "template";
  report: Report | null;
  disclaimer: string;
};
export type PacketDecline = { request_id: string; declined: true; decline_reason: string | null; message: string };
