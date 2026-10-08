import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata = {
  title: "Witness — Incident Review",
  description:
    "Review conflicting driver statements against dashcam video evidence. Human review required.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-cyan-400 focus:px-3 focus:py-1 focus:text-sm focus:font-bold focus:text-slate-950"
        >
          Skip to content
        </a>
        <header className="border-b border-slate-800 bg-slate-950/90">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
            <Link href="/" className="flex items-center gap-2.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400">
              <span
                aria-hidden="true"
                className="flex h-8 w-8 items-center justify-center rounded-md bg-cyan-400 text-lg font-black text-slate-950"
              >
                W
              </span>
              <span className="leading-tight">
                <span className="block text-[15px] font-extrabold tracking-tight">Witness</span>
                <span className="block text-[11px] font-medium tracking-widest text-slate-400 uppercase">
                  Incident review
                </span>
              </span>
            </Link>
            <nav aria-label="Primary" className="flex items-center gap-1 text-sm">
              <Link
                href="/incidents/demo-001"
                className="rounded-md px-3 py-2 font-semibold text-slate-300 hover:bg-slate-800 hover:text-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400"
              >
                Demo incident
              </Link>
              <Link
                href="/sweep"
                className="rounded-md px-3 py-2 font-semibold text-slate-300 hover:bg-slate-800 hover:text-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400"
              >
                Archive sweep
              </Link>
            </nav>
          </div>
        </header>
        <main id="main-content" className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
          {children}
        </main>
        <footer className="border-t border-slate-800">
          <div className="mx-auto max-w-7xl px-4 py-4 text-xs leading-relaxed text-slate-500 sm:px-6">
            Witness verdicts are investigative leads. Human review is always required, and no
            legal fault determination is provided.
          </div>
        </footer>
      </body>
    </html>
  );
}
