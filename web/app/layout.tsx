import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VK-Check: a mock EHR demo",
  description: "A mock chart with a decision-support panel for a fictional disease. All data is synthetic. Not medical advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
