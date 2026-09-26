"""Turn nflverse data into pre-kickoff start/sit decisions for GLiNER2.5-Decide.

Every feature is something a fantasy manager could know before the game; the label comes
from how the player actually finished at his position that week (PPR scoring).
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "decide"
SEASONS = sorted({int(p.stem[-4:]) for p in DATA.glob("stats_player_week_*.csv")})
POSITIONS = ("QB", "RB", "WR", "TE")
LABELS = ("start", "flex", "bench")
START_CUTOFF = {"QB": 12, "RB": 24, "WR": 36, "TE": 12}
FLEX_CUTOFF = {"QB": 18, "RB": 36, "WR": 48, "TE": 18}
RELEVANT_PPR = 6.0
PRACTICE = {"Did Not Participate In Practice": "did not practice", "Limited Participation in Practice": "limited",
            "Full Participation in Practice": "full"}


def norm_name(s):
    return re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()))


def load(prefix):
    frames = [pd.read_csv(DATA / f"{prefix}_{y}.csv", low_memory=False) for y in SEASONS if (DATA / f"{prefix}_{y}.csv").exists()]
    return pd.concat(frames, ignore_index=True)


def player_weeks():
    s = load("stats_player_week")
    s = s[(s.season_type == "REG") & s.position.isin(POSITIONS)].copy()
    s["played"] = True

    inj = load("injuries")
    inj = inj[(inj.game_type == "REG") & inj.position.isin(POSITIONS)]
    inj = inj.rename(columns={"gsis_id": "player_id", "full_name": "player_display_name"})
    inj = inj.drop_duplicates(["season", "week", "player_id"], keep="last")

    # Players ruled out never appear in the stats file; add them as zero-point weeks so the
    # model learns what an "Out" tag means for a start/sit call.
    missing = inj[inj.report_status.isin(["Out", "Doubtful"])].merge(
        s[["season", "week", "player_id"]], how="left", indicator=True)
    missing = missing[missing._merge == "left_only"].drop(columns="_merge")
    games = pd.read_csv(DATA / "games.csv")
    reg = games[games.game_type == "REG"]
    sched = pd.concat([reg.rename(columns={"home_team": "team", "away_team": "opponent_team"}),
                       reg.rename(columns={"away_team": "team", "home_team": "opponent_team"})])
    missing = missing.merge(sched[["season", "week", "team", "opponent_team", "game_id"]], on=["season", "week", "team"])
    missing = missing.assign(played=False, fantasy_points_ppr=0.0)
    s = pd.concat([s, missing[["season", "week", "player_id", "player_display_name", "position", "team",
                               "opponent_team", "game_id", "played", "fantasy_points_ppr"]]], ignore_index=True)

    s = s.merge(inj[["season", "week", "player_id", "report_status", "report_primary_injury", "practice_status"]],
                on=["season", "week", "player_id"], how="left")
    return s, games


def add_history(s):
    s = s.sort_values(["player_id", "season", "week"]).reset_index(drop=True)
    for col in ("targets", "carries", "target_share", "fantasy_points_ppr"):
        s[col] = s[col].fillna(0.0)
    g = s.groupby("player_id")
    played_pts = s.fantasy_points_ppr.where(s.played)
    s["last3_ppr"] = played_pts.groupby(s.player_id).transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    s["last_ppr"] = played_pts.groupby(s.player_id).transform(lambda x: x.shift(1).ffill())
    for col in ("targets", "carries", "target_share"):
        s[f"{col}_l3"] = s[col].where(s.played).groupby(s.player_id).transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    s["season_avg_ppr"] = played_pts.groupby([s.player_id, s.season]).transform(lambda x: x.shift(1).expanding().mean())
    s["games_this_season"] = s.played.groupby([s.player_id, s.season]).transform(lambda x: x.shift(1).fillna(False).cumsum())
    prev = s[s.played].groupby(["player_id", "season"]).fantasy_points_ppr.mean().rename("prev_season_ppr").reset_index()
    prev["season"] += 1
    s = s.merge(prev, on=["player_id", "season"], how="left")
    s["missed_last_week"] = g.played.shift(1).eq(False)
    return s


def add_snaps(s):
    sc = load("snap_counts")
    sc = sc[sc.game_type == "REG"].assign(key=lambda d: d.player.map(norm_name))
    sc = sc.sort_values(["key", "team", "season", "week"])
    sc["snap_pct_l3"] = sc.groupby(["key", "team"]).offense_pct.transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    s["key"] = s.player_display_name.map(norm_name)
    s = s.merge(sc[["season", "week", "team", "key", "snap_pct_l3"]], on=["season", "week", "team", "key"], how="left")
    if "upcoming" in s and s.upcoming.any():
        # Unplayed weeks have no snap row of their own; use the last three games played before that week.
        hist = sc.assign(t=sc.season * 100 + sc.week).sort_values("t")
        hist["l3_incl"] = hist.groupby(["key", "team"]).offense_pct.transform(lambda x: x.rolling(3, min_periods=1).mean())
        up = s[s.upcoming].assign(t=lambda d: d.season * 100 + d.week).sort_values("t")
        filled = pd.merge_asof(up.reset_index(), hist[["t", "key", "team", "l3_incl"]], on="t", by=["key", "team"],
                               allow_exact_matches=False).set_index("index")
        s.loc[filled.index, "snap_pct_l3"] = s.loc[filled.index, "snap_pct_l3"].fillna(filled.l3_incl)
    return s


def add_defense(s):
    """Points each defense allowed to each position before this week (prior-season value early on)."""
    allowed = (s[s.played].groupby(["season", "week", "opponent_team", "position"]).fantasy_points_ppr.sum()
               .rename("allowed").reset_index().sort_values(["opponent_team", "position", "season", "week"]))
    allowed["allowed_avg"] = allowed.groupby(["opponent_team", "position", "season"]).allowed.transform(
        lambda x: x.shift(1).expanding().mean())
    full = allowed.groupby(["opponent_team", "position", "season"]).allowed.mean().rename("prev_allowed").reset_index()
    full["season"] += 1
    allowed = allowed.merge(full, on=["opponent_team", "position", "season"], how="left")
    w = (allowed.week.clip(upper=6) - 1) / 5
    allowed["def_score"] = np.where(allowed.allowed_avg.isna(), allowed.prev_allowed,
                                    w * allowed.allowed_avg + (1 - w) * allowed.prev_allowed.fillna(allowed.allowed_avg))
    allowed["def_rank"] = allowed.groupby(["season", "week", "position"]).def_score.rank(ascending=False, method="min")
    return s.merge(allowed[["season", "week", "opponent_team", "position", "def_rank"]],
                   on=["season", "week", "opponent_team", "position"], how="left")


def add_game(s, games):
    g = games[games.game_type == "REG"]
    home = g.assign(team=g.home_team, is_home=True, implied=(g.total_line + g.spread_line) / 2, team_spread=-g.spread_line)
    away = g.assign(team=g.away_team, is_home=False, implied=(g.total_line - g.spread_line) / 2, team_spread=g.spread_line)
    cols = ["season", "week", "team", "is_home", "implied", "team_spread", "total_line", "roof", "wind", "temp", "gameday"]
    return s.merge(pd.concat([home, away])[cols], on=["season", "week", "team"], how="left")


def add_labels(s):
    s["pos_rank"] = s.groupby(["season", "week", "position"]).fantasy_points_ppr.rank(ascending=False, method="first")
    s["label"] = np.select([s.pos_rank <= s.position.map(START_CUTOFF), s.pos_rank <= s.position.map(FLEX_CUTOFF)],
                           ["start", "flex"], "bench")
    s.loc[~s.played, "label"] = "bench"
    return s


def fmt(v, spec="{:.1f}", none="none"):
    return none if v is None or (isinstance(v, float) and np.isnan(v)) else spec.format(v)


def serialize(r):
    def_rank = r.def_rank
    matchup = "none" if np.isnan(def_rank) else f"{int(def_rank)} of 32 ({'easy' if def_rank <= 8 else 'tough' if def_rank >= 25 else 'average'})"
    trend = "none"
    if not np.isnan(r.last_ppr) and not np.isnan(r.last3_ppr) and r.last3_ppr > 0:
        ratio = r.last_ppr / r.last3_ppr
        trend = "up" if ratio > 1.25 else "down" if ratio < 0.75 else "flat"
    inj = "healthy" if pd.isna(r.report_status) else f"{str(r.report_status).lower()} ({str(r.report_primary_injury).lower()})"
    practice = PRACTICE.get(r.practice_status, "full") if not pd.isna(r.practice_status) else "full"
    if r.roof in ("dome", "closed"):
        weather = "dome"
    elif np.isnan(r.wind) and np.isnan(r.temp):
        weather = "outdoors"
    else:
        weather = f"outdoors, wind {fmt(r.wind, '{:.0f}', '?')} mph, {fmt(r.temp, '{:.0f}', '?')}F"
    return " | ".join([
        f"position: {r.position}", f"week: {int(r.week)}", f"home: {'yes' if r.is_home else 'no'}",
        f"last3_ppr: {fmt(r.last3_ppr)}", f"last_game_ppr: {fmt(r.last_ppr)}", f"trend: {trend}",
        f"season_avg_ppr: {fmt(r.season_avg_ppr)}", f"games_this_season: {int(r.games_this_season or 0)}",
        f"prev_season_avg_ppr: {fmt(r.prev_season_ppr)}", f"targets_l3: {fmt(r.targets_l3)}",
        f"target_share_l3: {fmt(r.target_share_l3 * 100 if not np.isnan(r.target_share_l3) else np.nan, '{:.0f}%')}",
        f"carries_l3: {fmt(r.carries_l3)}", f"snap_pct_l3: {fmt(r.snap_pct_l3 * 100 if not np.isnan(r.snap_pct_l3) else np.nan, '{:.0f}%')}",
        f"missed_last_week: {'yes' if r.missed_last_week is True else 'no'}",
        f"matchup_rank: {matchup}", f"implied_team_total: {fmt(r.implied)}", f"spread: {fmt(r.team_spread, '{:+.1f}')}",
        f"game_total: {fmt(r.total_line)}", f"injury: {inj}", f"practice: {practice}", f"weather: {weather}",
    ])


def upcoming_rows(s, games, season, week, extra_players=None):
    """Placeholder rows for a week that hasn't been played, so history features roll forward into it.
    extra_players (player_id, player_display_name, position, team) adds players with no games yet this season."""
    s = s[~((s.season == season) & (s.week >= week))]
    active = s[(s.season == season) & (s.week < week) & s.played].sort_values("week").groupby("player_id").last().reset_index()
    if extra_players is not None and len(extra_players):
        new = extra_players[~extra_players.player_id.isin(active.player_id)]
        active = pd.concat([active, new], ignore_index=True)
    reg = games[(games.game_type == "REG") & (games.season == season) & (games.week == week)]
    opp = pd.concat([reg[["home_team", "away_team", "game_id"]].set_axis(["team", "opponent_team", "game_id"], axis=1),
                     reg[["away_team", "home_team", "game_id"]].set_axis(["team", "opponent_team", "game_id"], axis=1)])
    up = active[["player_id", "player_display_name", "position", "team"]].merge(opp, on="team")
    up = up.assign(season=season, week=week, played=True, fantasy_points_ppr=np.nan, upcoming=True)
    inj = load("injuries")
    inj = inj[(inj.season == season) & (inj.week == week)].rename(columns={"gsis_id": "player_id"})
    up = up.merge(inj[["player_id", "report_status", "report_primary_injury", "practice_status"]].drop_duplicates("player_id", keep="last"),
                  on="player_id", how="left")
    print(f"upcoming {season} week {week}: {len(up)} players, {len(reg)} games, {up.report_status.notna().sum()} on injury report")
    return pd.concat([s, up], ignore_index=True)


def build(upcoming=None, include_ids=(), extra_players=None):
    s, games = player_weeks()
    if upcoming:
        s = upcoming_rows(s, games, *upcoming, extra_players=extra_players)
    else:
        s["upcoming"] = False
    s["upcoming"] = s["upcoming"].fillna(False).astype(bool)
    s = add_history(s)
    s = add_snaps(s)
    s = add_defense(s)
    s = add_game(s, games)
    s = add_labels(s)
    relevant = (s.last3_ppr.fillna(0) >= RELEVANT_PPR) | (s.prev_season_ppr.fillna(0) >= RELEVANT_PPR + 2) | \
               (s.season_avg_ppr.fillna(0) >= RELEVANT_PPR) | s.player_id.isin(set(include_ids))
    s = s[relevant].copy()
    s["text"] = s.apply(serialize, axis=1)
    OUT.mkdir(parents=True, exist_ok=True)
    keep = ["season", "week", "player_id", "player_display_name", "position", "team", "opponent_team", "played",
            "fantasy_points_ppr", "pos_rank", "label", "text", "last3_ppr", "season_avg_ppr", "prev_season_ppr", "implied"]
    if upcoming:
        up = s[s.upcoming].assign(label=None, pos_rank=None)
        up[keep].to_csv(OUT / "upcoming_rows.csv", index=False)
        print(f"wrote {len(up)} upcoming rows; example:\n{up.iloc[0].player_display_name}: {up.iloc[0].text}")
        return
    s[keep].to_csv(OUT / "all_rows.csv", index=False)

    splits = {"train": s[s.season <= 2024], "test": s[s.season == 2025]}
    for name, df in splits.items():
        with open(OUT / f"{name}_hosted.jsonl", "w") as f:
            for r in df.itertuples():
                f.write(json.dumps({"text": r.text, "label": r.label}) + "\n")
        with open(OUT / f"{name}_gliner2.jsonl", "w") as f:
            for r in df.itertuples():
                f.write(json.dumps({"input": r.text, "output": {"classifications": [
                    {"task": "fantasy_decision", "labels": list(LABELS), "true_label": [r.label]}]}}) + "\n")
        print(f"{name}: {len(df):,} rows  {df.label.value_counts().to_dict()}")
    print(f"2026 rows (live season, weeks {sorted(s[s.season == 2026].week.unique())}): {len(s[s.season == 2026]):,}")
    print("\nexample:\n", s[s.season == 2025].iloc[100].text, "->", s[s.season == 2025].iloc[100].label)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "--upcoming":
        build(upcoming=(int(sys.argv[2]), int(sys.argv[3])))
    else:
        build()
