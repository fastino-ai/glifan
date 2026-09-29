import Link from "next/link";
import { MANAGERS, type Standing } from "../lib/data";

export default function Standings({ table, order }: { table: Standing[]; order: string[] }) {
  const rows = table.length ? table : order.map((key) => ({ key, w: 0, l: 0, t: 0, pf: 0, pa: 0, optimal: 0, weeks: 0 }));
  return (
    <table>
      <thead>
        <tr><th>#</th><th>Manager</th><th>Runs on</th><th className="num">W-L</th><th className="num">Points for</th>
          <th className="num">Points against</th><th className="num" title="Points scored vs the best possible lineup from the same roster">Lineup IQ</th></tr>
      </thead>
      <tbody>
        {rows.map((r, i) => {
          const m = MANAGERS[r.key];
          return (
            <tr key={r.key} className={r.key === "glifan" ? "us" : ""}>
              <td className="standing-rank">{i + 1}</td>
              <td>
                <div className="standing-manager">
                  <span className="dot" style={{ background: m.color }} />
                  <Link href={`/teams/${r.key}/`} className="manager-link">{m.name}</Link>
                  <span className={`kind ${m.kind}`}>{m.kind === "ai" ? "AI" : "bot"}</span>
                </div>
              </td>
              <td className="meta">{m.how}</td>
              <td className="num">{r.w}-{r.l}{r.t ? `-${r.t}` : ""}</td>
              <td className="num">{r.pf.toFixed(1)}</td>
              <td className="num">{r.pa.toFixed(1)}</td>
              <td className="num">{r.optimal ? `${(r.pf / r.optimal * 100).toFixed(1)}%` : "–"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
