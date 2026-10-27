import { useEffect, useState } from "react";
import { Markdown } from "./Markdown";

type Status = "checking" | "match" | "mismatch" | "unknown";

export function ModelCardTab({ body, hash }: { body: string; hash: string | null }) {
  const [status, setStatus] = useState<Status>("checking");
  useEffect(() => {
    let live = true;
    fetch("/api/health")
      .then((r) => r.json() as Promise<{ model_hash: string | null }>)
      .then((h) => live && setStatus(!h.model_hash || !hash ? "unknown" : h.model_hash === hash ? "match" : "mismatch"))
      .catch(() => live && setStatus("unknown"));
    return () => { live = false; };
  }, [hash]);
  const text: Record<Status, string> = {
    checking: "Checking that this card describes the model that is running…",
    match: "This card describes the model that is running: the model hashes match.",
    mismatch: "Warning: this card does not describe the model that is running. The hashes differ.",
    unknown: "Could not check the running model's hash.",
  };
  return (
    <section aria-label="Model card">
      <p className={`hash ${status}`} data-testid="hash-status" role="status">{text[status]}</p>
      <Markdown>{body}</Markdown>
    </section>
  );
}
