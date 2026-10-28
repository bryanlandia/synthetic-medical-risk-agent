import { MarkdownBody } from "./Markdown";

// A line `<!-- video: /file.webm | caption -->` in the text puts a player there. It is a comment so the repository README, which
// shows the same file, does not show it. Only files served from this site (a path starting with one slash) are accepted.
const VIDEO = /^<!-- video: (\/[\w.-]+\.webm) \| (.+?) -->$/gm;

type Part = { kind: "text"; text: string } | { kind: "video"; src: string; caption: string };

function parts(body: string): Part[] {
  const out: Part[] = [];
  let last = 0;
  for (const m of body.matchAll(VIDEO)) {
    out.push({ kind: "text", text: body.slice(last, m.index) });
    out.push({ kind: "video", src: m[1], caption: m[2] });
    last = m.index! + m[0].length;
  }
  out.push({ kind: "text", text: body.slice(last) });
  return out;
}

export function AboutTab({ body }: { body: string }) {
  // the file opens with a title for its other reader, the repository README; the page already has its own
  const text = body.replace(/^# .*\n+/, "");
  return (
    <section aria-label="About this project">
      <article className="doc">
        {parts(text).map((p, i) =>
          p.kind === "text" ? (
            <MarkdownBody key={i}>{p.text}</MarkdownBody>
          ) : (
            <figure key={i} className="clip">
              <video controls preload="none" src={p.src} aria-label={p.caption} />
              <figcaption>{p.caption}</figcaption>
            </figure>
          ),
        )}
      </article>
    </section>
  );
}
