import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SMAR — Memory-Driven Autonomous Voice Platform",
  description:
    "Autonomous voice intelligence grounded in persistent Knowledge Graph memory, subword vector retrieval, and local Epsilon 7B LLM.",
  icons: {
    icon: "/smar_logo_transparent.png",
    shortcut: "/smar_logo_transparent.png",
    apple: "/smar_logo_transparent.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}>
      <body className="min-h-full flex flex-col bg-[#07090e] text-slate-100">{children}</body>
    </html>
  );
}
