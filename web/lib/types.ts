/** What the page shows from the agent service: a whitelist of its response, never the raw body. */

export type DataQuality = { type: string; lab?: string | null };

export type Report = {
  probability: number;
  uncertain: boolean;
  symptoms: Record<string, string>;
  labs_used: { lab: string; value: number; unit: string }[];
  data_quality: DataQuality[];
  evidence: string[];
  disclaimer: string;
};

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
  labs: { lab: string; name: string; abbr: string; value: number | null; unit: string }[];
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
