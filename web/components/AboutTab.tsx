import { MarkdownBody } from "./Markdown";

// Two kinds of line become something other than text. Both are written so the repository README, which shows the same file,
// still reads well. Only files served from this site are accepted.
//  - `<!-- video: /file.webm | caption -->` puts a player there. It is a comment, so the README does not show it.
//  - `![alt](web/public/file.svg)` puts a figure there. On GitHub the path finds the file in the repository; here it is the
//    same file served from the site's root. The renderer itself still refuses images, so nothing else can load one.
const MEDIA = /^(?:<!-- video: (\/[\w.-]+\.webm) \| (.+?) -->|!\[([^\]\n]+)\]\(web\/public\/([\w-]+\.svg)\))$/gm;

type Part =
  | { kind: "text"; text: string }
  | { kind: "video"; src: string; caption: string }
  | { kind: "figure"; src: string; alt: string };

function parts(body: string): Part[] {
  const out: Part[] = [];
  let last = 0;
  for (const m of body.matchAll(MEDIA)) {
    out.push({ kind: "text", text: body.slice(last, m.index) });
    out.push(m[1] ? { kind: "video", src: m[1], caption: m[2] } : { kind: "figure", src: `/${m[4]}`, alt: m[3] });
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
          ) : p.kind === "video" ? (
            <figure key={i} className="clip">
              <video controls preload="none" src={p.src} aria-label={p.caption} />
              <figcaption>{p.caption}</figcaption>
            </figure>
          ) : (
            <figure key={i} className="diagram">
              <img src={p.src} alt={p.alt} />
            </figure>
          ),
        )}
      </article>
    </section>
  );
}
