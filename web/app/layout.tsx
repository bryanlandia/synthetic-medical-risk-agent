import type { Metadata } from "next";
import { Analytics } from "@/components/Analytics";
import "./globals.css";

export const metadata: Metadata = {
  title: "VK-Check: decision support for a fictional disease",
  description: "Decision support for Velorin-Kessler Syndrome diagnosis, a fictional disease. All data is synthetic. Not medical advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <footer className="site-footer" data-testid="funder-footer">
          Funded by the Kessler Family Foundation (a fictional foundation) to improve diagnosis of and outcomes for Velorin-Kessler Syndrome (a fictional disease). All data is synthetic. Not medical advice.
        </footer>
        <div className="bottom-stack">
          <Analytics />
        </div>
      </body>
    </html>
  );
}
