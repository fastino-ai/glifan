import { getDraft, MANAGERS } from "../lib/data";

export const metadata = { title: "Draft · glifan" };

export default function DraftPage() {
  const d = getDraft();
  if (!d) return <div className="hero"><h1>No draft yet</h1></div>;
  const rounds = Math.max(...d.picks.map((p) => p.round));
  return (
    <>
      <div className="hero">
        <h1>The draft</h1>
        <p>Every team drafted from the same player pool, in a snake order shuffled with a fixed seed, taking the best available
          player by FantasyPros redraft consensus within roster limits. So the teams are comparable: the competition is who
          sets the better lineup every week.</p>
        <span className="pill">{new Date(d.drafted_at).toUTCString().slice(5, 22)} UTC</span>
      </div>
      <section style={{ overflowX: "auto" }}>
        <table>
          <thead><tr><th>Round</th>{d.order.map((k) => <th key={k} style={{ color: MANAGERS[k].color }}>{MANAGERS[k].name}</th>)}</tr></thead>
          <tbody>
            {Array.from({ length: rounds }, (_, r) => (
              <tr key={r}>
                <td className="meta">{r + 1}</td>
                {d.order.map((k) => {
                  const p = d.picks.find((x) => x.round === r + 1 && x.manager === k);
                  return <td key={k}>{p ? <>{p.name} <span className="meta">{p.pos} {p.team}</span></> : ""}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="meta">{d.method}</p>
      </section>
    </>
  );
}
