import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import { Providers } from "@/lib/providers";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist-sans" });

export const metadata: Metadata = {
  title: "Telegram News Bot — Admin",
  description: "Admin dashboard for Telegram News Bot",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${geist.variable} font-sans bg-zinc-950 text-zinc-100 antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
