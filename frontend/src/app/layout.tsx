import type { Metadata } from "next";
import { DM_Sans, Noto_Sans_Kannada } from "next/font/google";
import "./globals.css";
import { AppProvider } from "@/lib/language";
import { AppShell } from "@/components/AppShell";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const notoKannada = Noto_Sans_Kannada({
  variable: "--font-noto-kannada",
  subsets: ["kannada"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Kirana Khata Agent — Sri Lakshmi Kirana Stores",
  description:
    "MCP-powered digital khata, WhatsApp Kannada order inbox, and inventory approval workbench for Sri Lakshmi Kirana Stores.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${dmSans.variable} ${notoKannada.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-[#F7F4EE] text-[#173B3F]">
        <AppProvider>
          <AppShell>{children}</AppShell>
        </AppProvider>
      </body>
    </html>
  );
}
