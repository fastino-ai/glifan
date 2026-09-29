import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "glifan: which AI model plays fantasy football best?",
  description: "A season-long fantasy football league where decision models and classic strategies manage their own teams.",
  openGraph: {
    title: "glifan",
    description: "Six managers, one fantasy league: fine-tuned GLiNER vs Jev vs expert consensus. Lineups lock at kickoff.",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <nav className="top">
          <div className="wrap">
            <Link href="/" className="brand"><span>glifan</span></Link>
            <Link href="/" className="link">League</Link>
            <Link href="/draft/" className="link">Draft</Link>
            <Link href="/how/" className="link">How it works</Link>
            <a className="cta" href="https://agent.fastino.ai" target="_blank" rel="noreferrer">Train your own</a>
          </div>
        </nav>
        <main className="wrap">{children}</main>
        <footer>
          <div className="wrap">
            glifan is powered by <a href="https://huggingface.co/fastino/GLiNER2.5-Decide">GLiNER2.5-Decide</a>, fine-tuned on
            the <a href="https://agent.fastino.ai">Fastino API</a>. Jev via Vercel AI Gateway. Stats from{" "}
            <a href="https://github.com/nflverse">nflverse</a>; expert consensus from FantasyPros via{" "}
            <a href="https://github.com/dynastyprocess/data">DynastyProcess</a>. Lineups lock at kickoff and are committed to{" "}
            <a href="https://github.com/fastino-ai/glifan">GitHub</a>. For entertainment; not betting advice.
          </div>
        </footer>
      </body>
    </html>
  );
}
