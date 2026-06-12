import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "LobbyLeaks",
  description:
    "Public investigative graph: lobby meetings, donations, travel and the people behind them.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen flex flex-col">
        <header className="border-b border-zinc-800 px-6 py-4 flex items-center gap-6">
          <Link href="/" className="font-semibold tracking-tight text-lg">
            LobbyLeaks
          </Link>
          <span className="text-xs text-zinc-500">
            Chile — datos públicos de InfoLobby
          </span>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-zinc-800 px-6 py-4 text-xs text-zinc-500">
          MIT · datos.infolobby.cl
        </footer>
      </body>
    </html>
  );
}
