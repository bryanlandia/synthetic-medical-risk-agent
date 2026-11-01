import type { Metadata } from "next";
import { Analytics } from "@/components/Analytics";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "VK-Check: supervisor review for a fictional disease",
  description: "A demo of reviewing PET-CT request packets for Velorin-Kessler Syndrome, a fictional disease. All data is synthetic. Not medical advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          {children}
          <footer className="site-footer" data-testid="funder-footer">
            Funded by the Kessler Family Foundation (a fictional foundation) to improve diagnosis of and outcomes for Velorin-Kessler Syndrome (a fictional disease). All data is synthetic. Not medical advice.
          </footer>
          <div className="bottom-stack no-print">
            <Analytics />
          </div>
        </Providers>
      </body>
    </html>
  );
}
