import { Markdown } from "./Markdown";

export function AboutTab({ body }: { body: string }) {
  return (
    <section aria-label="About this project">
      <Markdown>{body}</Markdown>
    </section>
  );
}
