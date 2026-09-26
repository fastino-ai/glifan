import fs from "node:fs";
import path from "node:path";

const DATA = path.join(process.cwd(), "public", "data", "league");

export type Player = {
  player_id: string; name: string; pos: string; team: string; ecr?: number;
  score?: number; start?: number; flex?: number; bench?: number; expert_rank?: number | null; fill_in?: boolean;
};
export type Team = {
  name: string; kind: "ai" | "bot"; model: string; params: string; set_at: string;
  lineup: (string | null)[]; players: (Player | null)[]; points?: number[]; optimal_points?: number;
};
export type Matchup = { home: string; away: string; home_pts: number; away_pts: number; winner: string | null };
export type Week = {
  season: number; week: number; updated_at: string; model: string; teams: Record<string, Team>;
  results?: { totals: Record<string, number>; matchups: Matchup[]; graded_at: string };
};
export type Standing = { key: string; w: number; l: number; t: number; pf: number; pa: number; optimal: number; weeks: number };
export type Draft = {
  season: number; drafted_at: string; method: string; order: string[]; league_start: string;
  rosters: Record<string, Player[]>; picks: (Player & { round: number; pick: number; manager: string })[];
};
export type Meta = {
  season: number; current_week: number | null; weeks: number[]; schedule: Record<string, [string, string][]>;
  playoffs: Record<string, string>; slots: string[]; updated_at: string;
};

function read<T>(file: string): T | null {
  const p = path.join(DATA, file);
  return fs.existsSync(p) ? (JSON.parse(fs.readFileSync(p, "utf8")) as T) : null;
}

export const getMeta = () => read<Meta>("meta.json");
export const getDraft = () => read<Draft>("draft.json");
export const getStandings = () => read<{ table: Standing[]; updated_at: string }>("standings.json")?.table ?? [];
export const getWeek = (w: number) => read<Week>(`week${String(w).padStart(2, "0")}.json`);

export const MANAGERS: Record<string, { name: string; kind: "ai" | "bot"; color: string; blurb: string; how: string }> = {
  glifan: {
    name: "glifan", kind: "ai", color: "#7c9cff",
    blurb: "GLiNER2.5-Decide, fine-tuned on 14,481 real NFL start/sit outcomes. 340M parameters.",
    how: "Fastino API",
  },
  jev: {
    name: "Jev", kind: "ai", color: "#a78bfa",
    blurb: "TypeSafe's hosted System One decision model, zero-shot. Parameter count undisclosed.",
    how: "Vercel AI Gateway",
  },
  decide_base: {
    name: "Decide (untrained)", kind: "ai", color: "#38bdf8",
    blurb: "The same GLiNER2.5-Decide model as glifan, with no fantasy training. The control group.",
    how: "Fastino API",
  },
  experts: {
    name: "FantasyPros experts", kind: "bot", color: "#f59e0b",
    blurb: "Starts whoever the FantasyPros weekly expert consensus projects to score the most.",
    how: "Human consensus",
  },
  season_avg: {
    name: "Season average", kind: "bot", color: "#94a3b8",
    blurb: "Starts whoever has averaged the most PPR points this season, skipping anyone ruled out.",
    how: "Rule",
  },
  hot_hand: {
    name: "Hot hand", kind: "bot", color: "#f472b6",
    blurb: "Starts whoever scored the most over the last three games, skipping anyone ruled out.",
    how: "Rule",
  },
};
