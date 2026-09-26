import Link from "next/link";
import { MANAGERS, type Team } from "../lib/data";

function Call({ p }: { p: NonNullable<Team["players"][number]> }) {
  if (p.start === undefined) {
    return <span className="meta">{p.expert_rank ? `expert ${p.expert_rank}` : p.score !== undefined ? `${p.score.toFixed(1)} pts` : ""}</span>;
  }
  const t = (p.start ?? 0) + (p.flex ?? 0) + (p.bench ?? 0) || 1;
  return (
    <span className="bar" title={`start ${Math.round((p.start ?? 0) / t * 100)}% · flex ${Math.round((p.flex ?? 0) / t * 100)}% · bench ${Math.round((p.bench ?? 0) / t * 100)}%`}>
      <i style={{ width: `${(p.start ?? 0) / t * 100}%`, background: "var(--start)" }} />
      <i style={{ width: `${(p.flex ?? 0) / t * 100}%`, background: "var(--flex)" }} />
      <i style={{ width: `${(p.bench ?? 0) / t * 100}%`, background: "var(--bench)" }} />
    </span>
  );
}

export default function LineupCard({ teamKey, team, slots, total, won }: {
  teamKey: string; team: Team; slots: string[]; total?: number; won?: boolean;
}) {
  const m = MANAGERS[teamKey];
  return (
    <div className="lineup-card" style={{ borderTopColor: m.color }}>
      <div className="lc-head">
        <Link href={`/teams/${teamKey}/`} className="lc-name">{m.name}</Link>
        <span className={`kind ${m.kind}`}>{m.kind === "ai" ? "AI" : "bot"}</span>
        {total !== undefined && <b className={`lc-total ${won ? "win" : ""}`}>{total.toFixed(1)}</b>}
      </div>
      {team.lineup.map((pid, i) => {
        const p = team.players[i];
        return (
          <div className="lc-row" key={i}>
            <span className="slot">{slots[i]}</span>
            {p ? <>
              <span className="lc-player">{p.name} <span className="meta">{p.team}</span>
                {p.fill_in && <span className="kind bot" title="One-week free-agent fill-in for an empty slot">FA</span>}</span>
              {team.points ? <span className="lc-pts">{team.points[i].toFixed(1)}</span> : <Call p={p} />}
            </> : <span className="meta">empty</span>}
          </div>
        );
      })}
    </div>
  );
}
