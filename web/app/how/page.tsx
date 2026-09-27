import { MANAGERS } from "../lib/data";

export const metadata = { title: "How it works · glifan" };

export default function How() {
  return (
    <div className="prose">
      <div className="hero">
        <h1>How the league works</h1>
        <p>A season-long, 6-team PPR league where every manager is either a decision model or a fixed strategy. Nobody gets
          human help after the draft.</p>
      </div>

      <section>
        <h2>The managers</h2>
        <table>
          <thead><tr><th>Manager</th><th>What it is</th><th>Runs on</th></tr></thead>
          <tbody>
            {Object.entries(MANAGERS).map(([k, m]) => (
              <tr key={k}><td><span className="dot" style={{ background: m.color }} />{m.name}</td><td>{m.blurb}</td><td className="meta">{m.how}</td></tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Keeping it fair</h2>
        <ul>
          <li><b>Same draft rules.</b> All six teams snake-draft from FantasyPros redraft consensus in a seeded random order,
            so rosters are comparable and the contest is weekly lineup decisions.</li>
          <li><b>Same information.</b> The AI managers see the identical pre-game description of each player and answer the
            identical question: will he finish as a start, a flex, or a bench player at his position this week?</li>
          <li><b>Locked at kickoff.</b> Lineups refresh with injury news until each game starts, then freeze. Every lineup is
            committed to <a href="https://github.com/fastino-ai/glifan">GitHub</a> before kickoff.</li>
          <li><b>Standard scoring.</b> PPR, one QB, two RB, two WR, one TE and one RB/WR/TE flex, head-to-head matchups,
            weeks 4&ndash;15 regular season, top four make the playoffs in weeks 16&ndash;17.</li>
        </ul>
        <p className="note">One known difference: Jev receives a short description with each label (for example what counts as a
          &quot;start&quot;), while the two GLiNER managers receive the label names only, because the Fastino API doesn&apos;t yet accept
          label descriptions. glifan learned what the labels mean from its training data; the untrained Decide control did not.</p>
      </section>

      <section>
        <h2>What the AI managers see</h2>
        <p>One line of text per player, built from <a href="https://github.com/nflverse">nflverse</a> data. Names are never shown,
          so the models judge situations, not reputations:</p>
        <pre className="note" style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>position: WR | week: 3 | home: yes | last3_ppr: 17.4 | trend: up | season_avg_ppr: 25.3 | targets_l3: 6.0 | target_share_l3: 20% | snap_pct_l3: 67% | matchup_rank: 8 of 32 (easy) | implied_team_total: 25.0 | spread: +3.5 | game_total: 53.5 | injury: healthy | practice: full | weather: outdoors</pre>
        <p>A manager&apos;s lineup is its highest-ranked players by <code>P(start) + ½·P(flex) − ½·P(bench)</code>, filled into
          QB, RB, RB, WR, WR, TE and FLEX. Players ruled out on the injury report are never started.</p>
      </section>

      <section>
        <h2>Before the season: a 2025 replay</h2>
        <p>We replayed the 2025 season, which glifan never trained on, as a 12-team league with the same draft for everyone,
          putting one manager in each draft seat against eleven season-average managers:</p>
        <table>
          <thead><tr><th>Manager</th><th className="num">Avg wins (of 14)</th><th className="num">Playoffs</th>
            <th className="num">Titles</th><th className="num">Share of perfect points</th></tr></thead>
          <tbody>
            <tr className="us"><td>glifan (fine-tuned)</td><td className="num">7.7</td><td className="num">7 / 12</td><td className="num">3 / 12</td><td className="num">86.9%</td></tr>
            <tr><td>Hot hand</td><td className="num">7.2</td><td className="num">6 / 12</td><td className="num">2 / 12</td><td className="num">88.1%</td></tr>
            <tr><td>Season average</td><td className="num">&ndash;</td><td className="num">&ndash;</td><td className="num">&ndash;</td><td className="num">87.8%</td></tr>
            <tr><td>Decide (untrained)</td><td className="num">5.5</td><td className="num">3 / 12</td><td className="num">1 / 12</td><td className="num">79.7%</td></tr>
          </tbody>
        </table>
        <p className="meta">Fine-tuning lifted Decide from 41.5% to 59.3% of weekly start/flex/bench tiers right. glifan won the
          most head-to-head, though it scored slightly fewer total points than the simple rules, so this season is a real contest.</p>
      </section>

      <section>
        <h2>How glifan was trained</h2>
        <p>glifan is GLiNER2.5-Decide fine-tuned with LoRA on 14,481 player-weeks from the 2021&ndash;2024 regular seasons, labeled
          by how each player actually finished. It took one dataset upload and one training call on the Fastino API.</p>
        <p className="note">If your product makes the same kind of decision thousands of times a day (routing, triage, approvals,
          moderation), you can fine-tune the same model on your own examples at{" "}
          <a href="https://agent.fastino.ai">agent.fastino.ai</a>.</p>
      </section>
    </div>
  );
}
