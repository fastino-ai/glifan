import LineChart from "./components/LineChart";
import LineupCard from "./components/LineupCard";
import Standings from "./components/Standings";
import { getDraft, getMeta, getStandings, getWeek, MANAGERS } from "./lib/data";

export default function Home() {
  const meta = getMeta();
  const draft = getDraft();
  if (!meta || !draft) return <div className="hero"><h1>The league starts soon.</h1></div>;
  const table = getStandings();
  const shownWeek = meta.current_week && meta.weeks.includes(meta.current_week) ? meta.current_week : meta.weeks.at(-1);
  const week = shownWeek ? getWeek(shownWeek) : null;
  const matchups = shownWeek ? meta.schedule[String(shownWeek)] ?? [] : [];
  const graded = meta.weeks.map(getWeek).filter((w) => w?.results);
  const cumulative = (key: string) => {
    let run = 0;
    return graded.map((w) => (run += w!.results!.totals[key] ?? 0));
  };

  return (
    <>
      <div className="hero">
        <h1>Six managers. One league. <em>Which model plays fantasy best?</em></h1>
        <p>Three AI decision models and three classic manager strategies drafted from the same pool and set their own
          lineups every week of the {meta.season} NFL season. Lineups lock at kickoff, every move is committed to GitHub, and
          the scoring is standard PPR.</p>
        <span className="pill">{meta.season} season</span>
        <span className="pill">{shownWeek ? `Week ${shownWeek}` : "preseason"}</span>
        <span className="pill">updated {new Date(meta.updated_at).toUTCString().slice(5, 22)} UTC</span>
      </div>

      <section>
        <h2>Standings</h2>
        <Standings table={table} order={draft.order} />
        {graded.length > 1 && (
          <div style={{ marginTop: 14 }}>
            <LineChart title="Season points" labels={graded.map((w) => `W${w!.week}`)}
              series={draft.order.map((k) => ({ label: MANAGERS[k].name, color: MANAGERS[k].color, values: cumulative(k),
                dashed: MANAGERS[k].kind === "bot" }))} />
          </div>
        )}
      </section>

      {week && (
        <section>
          <h2>Week {week.week} matchups <small>{week.results ? "final" : "lineups lock at each game's kickoff"}</small></h2>
          <div className="matchups">
            {matchups.map(([a, b]) => (
              <div className="matchup" key={a + b}>
                {[a, b].map((k) => (
                  <LineupCard key={k} teamKey={k} team={week.teams[k]} slots={meta.slots}
                    total={week.results?.totals[k]} won={week.results?.matchups.find((m) => m.home === a)?.winner === k} />
                ))}
              </div>
            ))}
          </div>
          <p className="meta">Bars show each AI manager&apos;s start / flex / bench probabilities. Bots show the number they rank by.</p>
        </section>
      )}
    </>
  );
}
