#!/usr/bin/env bash
# Download the nflverse files the pipeline needs (public GitHub release assets, no auth).
set -euo pipefail
cd "$(dirname "$0")/../data" 2>/dev/null || { mkdir -p "$(dirname "$0")/../data"; cd "$(dirname "$0")/../data"; }
BASE=https://github.com/nflverse/nflverse-data/releases/download
FIRST=${FIRST_SEASON:-2021}
LAST=${LAST_SEASON:-$(date +%Y)}

curl -fsSL -o games.csv "$BASE/schedules/games.csv"
for y in $(seq "$FIRST" "$LAST"); do
  for pair in stats_player:stats_player_week injuries:injuries snap_counts:snap_counts; do
    tag=${pair%%:*}; prefix=${pair##*:}
    curl -fsSL -o "${prefix}_${y}.csv" "$BASE/$tag/${prefix}_${y}.csv" || echo "missing ${prefix}_${y}.csv (ok early in a season)"
  done
done
DP=https://github.com/dynastyprocess/data/raw/master/files
for f in fp_latest_weekly.csv db_fpecr_latest.csv db_playerids.csv; do
  curl -fsSL -o "$f" "$DP/$f"
done
ls -la
