import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { outboundLinkName } from "@/lib/analytics";

/**
 * The one markdown renderer for the model card and the About text. Links open in a new tab without giving it access to this
 * page, and images are not rendered, so a description cannot load anything from another site.
 */
export function MarkdownBody({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      disallowedElements={["img"]}
      components={{
        a: ({ href, children: label }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" data-track={outboundLinkName(href) ?? undefined}>{label}</a>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}

export function Markdown({ children }: { children: string }) {
  return (
    <article className="doc">
      <MarkdownBody>{children}</MarkdownBody>
    </article>
  );
}
