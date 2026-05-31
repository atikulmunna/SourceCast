import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "SourceCast — Timestamp-Cited Research Assistant",
  description:
    "Ask, compare, and research long-form audio and video with timestamped evidence. Turn podcasts, YouTube lectures, and interviews into a searchable knowledge base.",
  keywords:
    "podcast research, youtube transcription, timestamp citations, evidence-based answers, knowledge base",
  openGraph: {
    title: "SourceCast",
    description:
      "Ask long-form audio and video questions. Get answers with exact source evidence.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
