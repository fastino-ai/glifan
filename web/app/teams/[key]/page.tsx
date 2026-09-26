import Link from "next/link";
import LineupCard from "../../components/LineupCard";
import { getDraft, getMeta, getWeek, MANAGERS } from "../../lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return Object.keys(MANAGERS).map((key) => ({ key }));
}

export default async function TeamPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const m = MANAGERS[key];
  const meta = getMeta();
  const draft = getDraft();
  const weeks = (meta?.weeks ?? []).map(getWeek).filter(Boolean).reverse();

  return (
    <>
      <div className="hero">
        <h1><span className="dot big" style={{ background: m.color }} />{m.name}</h1>
        <p>{m.blurb}</p>
        <span className="pill">{m.kind === "ai" ? "AI manager" : "Strategy bot"}</span>
        <span className="pill">runs on: {m.how}</span>
      </div>

      <section>
        <h2>Roster <small>drafted {draft ? new Date(draft.drafted_at).toDateString() : ""}</small></h2>
        <div className="roster">
          {draft?.rosters[key]?.map((p) => (
            <span key={p.player_id} className="pill">{p.pos} · {p.name} <span className="meta">{p.team}</span></span>
          ))}
        </div>
      </section>

      <section>
        <h2>Weekly lineups</h2>
        <div className="matchups">
          {weeks.map((w) => w && w.teams[key] && (
            <div key={w.week}>
              <p className="meta">Week {w.week}{w.results ? ` · ${w.results.totals[key].toFixed(1)} points` : " · in progress"}</p>
              <LineupCard teamKey={key} team={w.teams[key]} slots={meta!.slots} total={w.results?.totals[key]} />
            </div>
          ))}
        </div>
        {!weeks.length && <p className="meta">No lineups yet.</p>}
      </section>
      <p><Link href="/">← Back to the league</Link></p>
    </>
  );
}
