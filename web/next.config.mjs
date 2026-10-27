// Analytics is built in only when a project key is set; then the browser talks to /ingest on this site and the server forwards
// to PostHog (the recipe in PostHog's Next.js proxy guide). NEXT_PUBLIC_POSTHOG_HOST is the region's ingest host.
const key = process.env.NEXT_PUBLIC_POSTHOG_KEY || "";
const host = (process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com").replace(/\/$/, "");
const assets = host.replace(/^(https:\/\/(?:us|eu))\.i\.posthog\.com$/, "$1-assets.i.posthog.com");

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // a second build (the analytics tests) writes to its own directory
  distDir: process.env.NEXT_DIST_DIR || ".next",
  ...(key
    ? {
        skipTrailingSlashRedirect: true,
        async rewrites() {
          return [
            { source: "/ingest/static/:path*", destination: `${assets}/static/:path*` },
            { source: "/ingest/array/:path*", destination: `${assets}/array/:path*` },
            { source: "/ingest/:path*", destination: `${host}/:path*` },
          ];
        },
      }
    : {}),
};

export default nextConfig;
