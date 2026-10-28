import type { Metadata } from "next";
import { Analytics } from "@/components/Analytics";
import "./globals.css";

export const metadata: Metadata = {
  title: "VK-Check: a mock EHR demo",
  description: "A mock chart with a decision-support panel for a fictional disease. All data is synthetic. Not medical advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <div className="bottom-stack">
          <Analytics />
        </div>
      </body>
    </html>
  );
}
