import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/layout/Sidebar";

export const metadata: Metadata = {
  title: "SlideBuddy",
  description: "PowerPoint Content Agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className="flex min-h-screen">
        <Providers>
          <Sidebar />
          <main className="flex-1 p-8 overflow-y-auto">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
