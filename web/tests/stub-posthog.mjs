// A stand-in for PostHog's ingestion host for the analytics tests: records every request (decoded) and answers 200.
import http from "node:http";
import zlib from "node:zlib";

const PORT = Number(process.env.STUB_PORT || 8799);
const seen = [];

function decode(buffer) {
  let text;
  try {
    text = zlib.gunzipSync(buffer).toString("utf8");
  } catch {
    text = buffer.toString("utf8");
  }
  if (text.startsWith("data=")) {
    try {
      text = Buffer.from(decodeURIComponent(text.slice(5)), "base64").toString("utf8");
    } catch {
      /* keep the raw text */
    }
  }
  return text;
}

http
  .createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const url = new URL(req.url, "http://stub");
      if (url.pathname === "/__requests") {
        res.setHeader("content-type", "application/json");
        return res.end(JSON.stringify(seen));
      }
      if (url.pathname === "/__reset") {
        seen.length = 0;
        return res.end("ok");
      }
      seen.push({ method: req.method, path: url.pathname, query: url.search, body: decode(Buffer.concat(chunks)) });
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({ status: 1, featureFlags: {}, config: { enable_collect_everything: false } }));
    });
  })
  .listen(PORT, "127.0.0.1", () => console.log(`stub posthog on ${PORT}`));
