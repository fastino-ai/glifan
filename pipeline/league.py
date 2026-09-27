"""glifan league: six managers, one draft, weekly lineups that lock at kickoff, head-to-head standings.

    python pipeline/league.py draft       # one-time: snake draft from FantasyPros redraft consensus
    python pipeline/league.py lineups     # set/refresh this week's lineups (players lock at their kickoff)
    python pipeline/league.py grade       # score finished weeks, update standings
    python pipeline/league.py publish     # write web/public/data/league/*.json

Env: FASTINO_API_KEY, GLIFAN_MODEL (fine-tuned model id), AI_GATEWAY_API_KEY or VERCEL_OIDC_TOKEN.
"""
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import build_dataset as bd
import managers as M

ROOT = Path(__file__).resolve().parent.parent
LEAGUE = Path(os.environ.get("GLIFAN_LEAGUE_DIR", ROOT / "league"))
WEB = Path(os.environ.get("GLIFAN_WEB_DIR", ROOT / "web" / "public" / "data" / "league"))
FP_TEAM = {"JAC": "JAX", "LAR": "LA", "WSH": "WAS"}
SLOTS = [("QB", ("QB",)), ("RB", ("RB",)), ("RB", ("RB",)), ("WR", ("WR",)), ("WR", ("WR",)), ("TE", ("TE",)),
         ("FLEX", ("RB", "WR", "TE"))]
LIMITS = {"QB": 2, "RB": 5, "WR": 5, "TE": 2}
MINIMUMS = {"QB": 1, "RB": 3, "WR": 3, "TE": 1}
ROUNDS = 13
REGULAR_WEEKS = range(4, 16)
PLAYOFF = {16: "semifinal", 17: "final"}
SEED = "glifan-2026"


def now():
    return datetime.fromisoformat(os.environ["GLIFAN_NOW"]) if os.environ.get("GLIFAN_NOW") else datetime.now(timezone.utc)


def season_dir(season):
    d = LEAGUE / str(season)
    d.mkdir(parents=True, exist_ok=True)
    return d


def read(p, default=None):
    return json.loads(p.read_text()) if p.exists() else default


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def games():
    g = pd.read_csv(bd.DATA / "games.csv")
    g = g[g.game_type == "REG"].copy()
    et = ZoneInfo("America/New_York")
    g["kickoff"] = [datetime.fromisoformat(f"{d}T{t}").replace(tzinfo=et).astimezone(timezone.utc)
                    for d, t in zip(g.gameday, g.gametime.fillna("13:00"))]
    return g


def current_week(g):
    season = int(g.season.max())
    open_ = g[(g.season == season) & g.home_score.isna()]
    return season, (int(open_.week.min()) if len(open_) else None)


def player_ids():
    ids = pd.read_csv(bd.DATA / "db_playerids.csv", low_memory=False)[["fantasypros_id", "gsis_id"]].dropna()
    ids["fantasypros_id"] = pd.to_numeric(ids.fantasypros_id, errors="coerce")
    return ids.dropna()


def weekly_ecr():
    w = pd.read_csv(bd.DATA / "fp_latest_weekly.csv")
    w = w[w.pos.isin(bd.POSITIONS)].merge(player_ids(), on="fantasypros_id", how="left")
    w["r2p_pts"] = pd.to_numeric(w.r2p_pts, errors="coerce")
    return w.dropna(subset=["gsis_id"])


# ---------------------------------------------------------------- schedule
def schedule(keys):
    """Round-robin for the regular season (circle method), repeated as needed."""
    teams = list(keys)
    rounds = []
    for _ in range(len(teams) - 1):
        rounds.append([(teams[i], teams[-1 - i]) for i in range(len(teams) // 2)])
        teams = [teams[0], teams[-1]] + teams[1:-1]
    return {w: rounds[i % len(rounds)] for i, w in enumerate(REGULAR_WEEKS)}


# ---------------------------------------------------------------- draft
def draft():
    season = int(games().season.max())
    path = season_dir(season) / "draft.json"
    if path.exists():
        sys.exit(f"draft already done: {path.relative_to(ROOT)}")
    e = pd.read_csv(bd.DATA / "db_fpecr_latest.csv")
    pool = e[(e.ecr_type == "ro") & e.pos.isin(bd.POSITIONS)].copy()
    pool["fantasypros_id"] = pd.to_numeric(pool.id, errors="coerce")
    pool = pool.merge(player_ids(), on="fantasypros_id", how="inner").sort_values("ecr")

    keys = ["glifan", "jev", "decide_base", "experts", "season_avg", "hot_hand"]
    order = keys[:]
    random.Random(SEED).shuffle(order)
    rosters = {k: [] for k in keys}
    picks, taken = [], set()
    for rnd in range(ROUNDS):
        for k in (order if rnd % 2 == 0 else order[::-1]):
            counts = pd.Series([p["pos"] for p in rosters[k]], dtype=object).value_counts()
            missing = {pos: n - counts.get(pos, 0) for pos, n in MINIMUMS.items() if counts.get(pos, 0) < n}
            must = set(missing) if ROUNDS - rnd <= sum(missing.values()) else None
            for p in pool.itertuples():
                if p.gsis_id not in taken and counts.get(p.pos, 0) < LIMITS[p.pos] and (must is None or p.pos in must):
                    taken.add(p.gsis_id)
                    entry = {"player_id": p.gsis_id, "name": p.player, "pos": p.pos, "team": FP_TEAM.get(p.team, p.team),
                             "ecr": float(p.ecr)}
                    rosters[k].append(entry)
                    picks.append({"round": rnd + 1, "pick": len(picks) + 1, "manager": k, **entry})
                    break
    write(path, {"season": season, "drafted_at": now().isoformat(), "method": "snake draft from FantasyPros redraft consensus "
                 f"(scraped {e.scrape_date.iloc[0]}), draft order shuffled with seed '{SEED}'",
                 "order": order, "rosters": rosters, "picks": picks, "league_start": now().isoformat()})
    print("draft order:", order)
    for k, r in rosters.items():
        print(f"  {k:12s}", ", ".join(p["name"] for p in r[:5]), "…")


# ---------------------------------------------------------------- lineups
def optimal(scores, roster_pos, fixed):
    """Fill SLOTS by descending score. `fixed` maps slot index -> player_id (locked) or None (locked empty)."""
    lineup = dict(fixed)
    used = {pid for pid in fixed.values() if pid}
    order = sorted(scores, key=lambda pid: -scores[pid])
    for i, (_, allowed) in enumerate(SLOTS):
        if i in lineup:
            continue
        lineup[i] = next((pid for pid in order if pid not in used and roster_pos[pid] in allowed), None)
        if lineup[i]:
            used.add(lineup[i])
    return [lineup[i] for i in range(len(SLOTS))]


def lineups():
    if not os.environ.get("GLIFAN_MODEL"):
        sys.exit("set GLIFAN_MODEL to the fine-tuned model id")
    g = games()
    season, week = current_week(g)
    dr = read(season_dir(season) / "draft.json")
    if not dr or week is None or week not in list(REGULAR_WEEKS) + list(PLAYOFF):
        print(f"nothing to do (season {season}, week {week}, drafted={bool(dr)})")
        return
    t = now()
    league_start = datetime.fromisoformat(dr["league_start"])
    kick = {}
    for r in g[(g.season == season) & (g.week == week)].itertuples():
        kick[r.home_team] = kick[r.away_team] = r.kickoff

    rostered = pd.DataFrame([p for r in dr["rosters"].values() for p in r])
    extra = rostered.rename(columns={"name": "player_display_name", "pos": "position"})[["player_id", "player_display_name", "position", "team"]]
    bd.build(upcoming=(season, week), include_ids=rostered.player_id, extra_players=extra)
    all_rows = pd.read_csv(bd.OUT / "upcoming_rows.csv")
    bl = all_rows.apply(lambda r: pd.Series(baselines(r), index=["baseline_avg", "baseline_hot"]), axis=1)
    all_rows = pd.concat([all_rows, bl], axis=1)
    all_rows["kickoff"] = all_rows.team.map(kick)
    all_rows["locked"] = all_rows.kickoff.map(lambda k: k is not None and k == k and k <= t)
    all_rows["pre_launch"] = all_rows.kickoff.map(lambda k: k is not None and k == k and k <= league_start)
    rows = all_rows[all_rows.player_id.isin(rostered.player_id)].copy()

    path = season_dir(season) / f"week{week:02d}.json"
    prev = read(path, {"teams": {}})
    ecr = weekly_ecr()
    out = {"season": season, "week": week, "updated_at": t.isoformat(), "model": os.environ["GLIFAN_MODEL"], "teams": {}}
    for m in M.league_managers(os.environ["GLIFAN_MODEL"], ecr):
        roster = dr["rosters"][m.key]
        pos = {p["player_id"]: p["pos"] for p in roster}
        mine = rows[rows.player_id.isin(pos)]
        before = prev["teams"].get(m.key, {})
        old_scores = before.get("scores", {})
        open_rows = mine[~mine.locked]
        try:
            fresh = m.rank(open_rows) if len(open_rows) else {}
        except Exception as e:  # one manager's outage must not block the others
            print(f"{m.name}: ranking failed ({str(e)[:120]}); keeping its previous lineup")
            out["teams"][m.key] = {**before, "name": m.name, "kind": m.kind, "model": m.model, "params": m.params,
                                   "lineup": before.get("lineup", [None] * len(SLOTS)), "scores": old_scores,
                                   "error": str(e)[:200], "error_at": t.isoformat()}
            continue
        scores = {**{pid: s for pid, s in old_scores.items() if pid in set(mine[mine.locked].player_id)}, **fresh}
        eligible = {pid: s["score"] for pid, s in scores.items()
                    if pid in set(mine[~mine.pre_launch].player_id) and "injury: out" not in mine.set_index("player_id").text.get(pid, "")}
        fixed = {}
        for i, pid in enumerate(before.get("lineup", [])):
            if pid and pid in set(mine[mine.locked].player_id):
                fixed[i] = pid
        for pid in set(mine[mine.locked].player_id) - set(fixed.values()):
            eligible.pop(pid, None)
        lineup = optimal(eligible, pos, fixed)
        fill_ins = before.get("fill_ins", {})
        empty = [i for i, pid in enumerate(lineup) if pid is None and i not in fixed]
        if empty:
            lineup, fill_ins = fill_from_free_agents(m, lineup, empty, rows, all_rows, rostered, fill_ins, scores, pos)
        out["teams"][m.key] = {"name": m.name, "kind": m.kind, "model": m.model, "params": m.params,
                               "lineup": lineup, "scores": scores, "fill_ins": fill_ins, "set_at": t.isoformat()}
        label = {p["player_id"]: p["name"] for p in roster} | {pid: f["name"] + " (FA)" for pid, f in fill_ins.items()}
        print(f"{m.name:36s} " + " | ".join(label.get(pid, "—") if pid else "—" for pid in lineup))
    write(path, out)


def fill_from_free_agents(m, lineup, empty, rows, all_rows, rostered, fill_ins, scores, pos, pool_size=8):
    """Emergency one-week pickup: for each empty starting slot, the manager ranks the top unrostered players at that
    position (by season average) with its own judgment and starts the best one."""
    taken = set(rostered.player_id) | {pid for pid in lineup if pid}
    for i in empty:
        allowed = SLOTS[i][1]
        pool = all_rows[all_rows.position.isin(allowed) & ~all_rows.player_id.isin(taken) & ~all_rows.locked
                        & ~all_rows.text.str.contains("injury: out|injury: doubtful", regex=True)]
        pool = pool.sort_values("baseline_avg", ascending=False).head(pool_size)
        if not len(pool):
            continue
        ranked = m.rank(pool)
        best = max(ranked, key=lambda pid: ranked[pid]["score"])
        lineup[i] = best
        taken.add(best)
        scores[best] = ranked[best]
        pos[best] = pool.set_index("player_id").position[best]
        r = pool.set_index("player_id").loc[best]
        fill_ins[best] = {"player_id": best, "name": r.player_display_name, "pos": r.position, "team": r.team, "slot": i}
        print(f"  {m.name}: free-agent fill-in {r.player_display_name} ({r.position}, {r.team}) for slot {SLOTS[i][0]}")
    return lineup, fill_ins


def baselines(r):
    avg = next((v for v in (r.season_avg_ppr, r.prev_season_ppr, r.last3_ppr) if v == v), 0.0)
    out = " injury: out" in f" {r.text}" or " injury: doubtful" in f" {r.text}"
    return (-99.0 if out else float(avg)), (-99.0 if out else float(r.last3_ppr if r.last3_ppr == r.last3_ppr else 0.0))


# ---------------------------------------------------------------- grading
def grade():
    g = games()
    season = int(g.season.max())
    dr = read(season_dir(season) / "draft.json")
    stats = pd.read_csv(bd.DATA / f"stats_player_week_{season}.csv", low_memory=False)
    stats = stats[stats.season_type == "REG"]
    finished = g[g.season == season].groupby("week").home_score.apply(lambda x: x.notna().all())
    sched = schedule(dr["order"])
    for week in [w for w, done in finished.items() if done]:
        path = season_dir(season) / f"week{week:02d}.json"
        wk = read(path)
        if not wk or wk.get("results"):
            continue
        pts = stats[stats.week == week].set_index("player_id").fantasy_points_ppr.to_dict()
        totals = {}
        for key, team in wk["teams"].items():
            team["points"] = [round(float(pts.get(pid, 0.0)), 2) if pid else 0.0 for pid in team["lineup"]]
            totals[key] = round(sum(team["points"]), 2)
            roster = [p["player_id"] for p in dr["rosters"][key]]
            best = optimal({pid: pts.get(pid, 0.0) for pid in roster}, {p["player_id"]: p["pos"] for p in dr["rosters"][key]}, {})
            team["optimal_points"] = round(sum(pts.get(pid, 0.0) for pid in best if pid), 2)
        matchups = []
        for a, b in sched.get(week, []):
            matchups.append({"home": a, "away": b, "home_pts": totals[a], "away_pts": totals[b],
                             "winner": a if totals[a] > totals[b] else b if totals[b] > totals[a] else None})
        wk["results"] = {"totals": totals, "matchups": matchups, "graded_at": now().isoformat()}
        write(path, wk)
        print(f"graded week {week}: " + ", ".join(f"{k} {v}" for k, v in sorted(totals.items(), key=lambda kv: -kv[1])))
    standings(season, dr)


def standings(season, dr):
    table = {k: {"w": 0, "l": 0, "t": 0, "pf": 0.0, "pa": 0.0, "optimal": 0.0, "weeks": 0} for k in dr["order"]}
    for w in REGULAR_WEEKS:
        wk = read(season_dir(season) / f"week{w:02d}.json")
        if not wk or not wk.get("results"):
            continue
        for k, team in wk["teams"].items():
            table[k]["optimal"] += team.get("optimal_points", 0.0)
            table[k]["weeks"] += 1
        for m in wk["results"]["matchups"]:
            for me, opp in (("home", "away"), ("away", "home")):
                row = table[m[me]]
                row["pf"] += m[f"{me}_pts"]
                row["pa"] += m[f"{opp}_pts"]
                row["w" if m["winner"] == m[me] else "t" if m["winner"] is None else "l"] += 1
    ranked = sorted(table.items(), key=lambda kv: (-(kv[1]["w"] + 0.5 * kv[1]["t"]), -kv[1]["pf"]))
    write(season_dir(season) / "standings.json", {"season": season, "updated_at": now().isoformat(),
          "table": [{"key": k, **{f: round(v, 2) if isinstance(v, float) else v for f, v in row.items()}} for k, row in ranked]})


# ---------------------------------------------------------------- publish
def publish():
    g = games()
    season, week = current_week(g)
    WEB.mkdir(parents=True, exist_ok=True)
    src = season_dir(season)
    dr = read(src / "draft.json")
    names = {p["player_id"]: p for r in dr["rosters"].values() for p in r}
    weeks = []
    for f in sorted(src.glob("week*.json")):
        wk = read(f)
        for team in wk["teams"].values():
            names.update({pid: {**p, "fill_in": True} for pid, p in team.get("fill_ins", {}).items()})
        for team in wk["teams"].values():
            team["players"] = [{**names.get(pid, {}), **team["scores"].get(pid, {})} if pid else None for pid in team["lineup"]]
        write(WEB / f.name, wk)
        weeks.append(wk["week"])
    write(WEB / "draft.json", dr)
    write(WEB / "standings.json", read(src / "standings.json", {"table": []}))
    write(WEB / "meta.json", {"season": season, "current_week": week, "weeks": weeks, "schedule": {str(k): v for k, v in schedule(dr["order"]).items()},
                              "playoffs": PLAYOFF, "slots": [s for s, _ in SLOTS], "updated_at": now().isoformat()})
    print(f"published league: weeks {weeks}")


if __name__ == "__main__":
    {"draft": draft, "lineups": lineups, "grade": grade, "publish": publish}[sys.argv[1]]()
