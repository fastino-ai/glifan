# glifan

A season-long fantasy football league where decision models and classic strategies manage their own teams.

| Manager | What it is |
|---|---|
| **glifan** | [GLiNER2.5-Decide](https://huggingface.co/fastino/GLiNER2.5-Decide) fine-tuned on 14,481 NFL start/sit outcomes (2021–2024) on the [Fastino API](https://agent.fastino.ai) |
| Jev | TypeSafe's hosted decision model via Vercel AI Gateway, zero-shot |
| Decide (untrained) | The same GLiNER2.5-Decide model with no fantasy training |
| FantasyPros experts | Starts the players the weekly expert consensus projects highest |
| Season average | Starts the highest season PPR averages |
| Hot hand | Starts the highest last-3-game PPR averages |

## How it runs

- `pipeline/league.py draft` — one-time snake draft from FantasyPros redraft consensus (seeded order). Output: `league/2026/draft.json`.
- `pipeline/league.py lineups` — builds each rostered player's pre-game description from [nflverse](https://github.com/nflverse) data, asks each manager to rank them, and fills QB/RB/RB/WR/WR/TE/FLEX. Players lock at their game's kickoff.
- `pipeline/league.py grade` — scores finished weeks (PPR), head-to-head results and standings.
- `pipeline/league.py publish` — writes the JSON the site reads (`web/public/data/league/`).

[`.github/workflows/league.yml`](.github/workflows/league.yml) runs this on a schedule around each NFL slate and commits the results, so the git history is a timestamped record that lineups were set before kickoff.

The site (`web/`) is a static Next.js app deployed on Vercel.

## Running locally

```bash
python -m venv .venv && .venv/bin/pip install -r pipeline/requirements.txt
bash pipeline/fetch_data.sh
export FASTINO_API_KEY=... AI_GATEWAY_API_KEY=... GLIFAN_MODEL=<fine-tuned model id>
.venv/bin/python pipeline/league.py lineups && .venv/bin/python pipeline/league.py publish
cd web && npm install && npm run dev
```

For entertainment; not betting advice. Stats from nflverse; expert consensus from FantasyPros via DynastyProcess.
