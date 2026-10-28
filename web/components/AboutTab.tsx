import { Markdown } from "./Markdown";

export function AboutTab({ body }: { body: string }) {
  return (
    <section aria-label="About this project">
      {/* the file opens with a title for its other reader, the repository README; the page already has its own */}
      <Markdown>{body.replace(/^# .*\n+/, "")}</Markdown>
    </section>
  );
}
