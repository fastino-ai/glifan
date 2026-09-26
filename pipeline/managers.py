"""The six glifan league managers. Every manager ranks the same rostered players each week.

AI managers get the same pre-game text and the same start/flex/bench question. Nothing is self-hosted:
GLiNER models run on the Fastino API and Jev runs on Vercel AI Gateway.
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests

LABELS = ("start", "flex", "bench")
INSTRUCTIONS = ("Fantasy football, PPR scoring. Based on this player's pre-game situation, where will he finish at his "
                "position this week?")
CRITERIA = {
    "start": "a top-12 QB or TE, top-24 RB, or top-36 WR this week: start him",
    "flex": "the next tier down (QB/TE 13-18, RB 25-36, WR 37-48): a flex or bye-week fill-in",
    "bench": "below that, or not playing: keep him on the bench",
}


def decision_score(p):
    return p["start"] + 0.5 * p["flex"] - 0.5 * p["bench"]


RETRYABLE = {425, 429}


def _retry(fn, attempts=10):
    """Retries transient failures, including 425 model_warming on cold starts (honors Retry-After)."""
    for i in range(attempts):
        try:
            return fn()
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            resp = e.response if isinstance(e, requests.HTTPError) else None
            code = resp.status_code if resp is not None else 0
            if i == attempts - 1 or (code and code < 500 and code not in RETRYABLE):
                raise
            retry_after = resp.headers.get("retry-after") if resp is not None else None
            time.sleep(min(float(retry_after), 60) if retry_after and retry_after.isdigit() else min(2 ** i, 30))


class Manager:
    key = name = kind = model = params = ""

    def rank(self, rows):
        """rows: DataFrame of this week's rostered players. Returns {player_id: {"score": float, ...}}."""
        raise NotImplementedError


class AIManager(Manager):
    kind = "ai"

    def probs(self, text):
        raise NotImplementedError

    def rank(self, rows):
        with ThreadPoolExecutor(8) as ex:
            probs = list(ex.map(self.probs, rows.text.tolist()))
        return {pid: {"score": round(decision_score(p), 4), **{k: round(v, 4) for k, v in p.items()}}
                for pid, p in zip(rows.player_id, probs)}


class GlinerDecide(AIManager):
    def __init__(self, key, name, model):
        self.key, self.name, self.model, self.params = key, name, model, "340M"
        self.s = requests.Session()
        self.s.headers.update({"X-API-Key": os.environ["FASTINO_API_KEY"]})

    def probs(self, text):
        def call():
            r = self.s.post("https://api.fastino.ai/v1/chat/completions", timeout=60, json={
                "model": self.model, "messages": [{"role": "user", "content": text}], "include_confidence": True,
                "schema": {"classifications": [{"task": "decision", "labels": list(LABELS), "multi_label": True, "cls_threshold": 0.0}]}})
            r.raise_for_status()
            c = r.json()["choices"][0]["message"]["content"]
            c = json.loads(c) if isinstance(c, str) else c
            p = {d["label"]: float(d["confidence"]) for d in c["decision"]}
            total = sum(p.values()) or 1.0
            return {l: p.get(l, 0.0) / total for l in LABELS}
        return _retry(call)


class Jev(AIManager):
    key, name, model, params = "jev", "Jev", "typesafe-ai/jev", "undisclosed"

    def __init__(self):
        token = os.environ.get("AI_GATEWAY_API_KEY") or os.environ["VERCEL_OIDC_TOKEN"]
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}"})

    def probs(self, text):
        def call():
            r = self.s.post("https://ai-gateway.vercel.sh/v1/evaluate", timeout=60, json={
                "model": self.model, "state": text,
                "questions": {"decision": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": CRITERIA}}})
            r.raise_for_status()
            ans = r.json()["answers"]["decision"]
            p = ans.get("probabilities") or ({ans["choice"]: 1.0} if ans.get("choice") else {})
            total = sum(p.get(l, 0.0) for l in LABELS) or 1.0
            return {l: p.get(l, 0.0) / total for l in LABELS}
        return _retry(call)


class Experts(Manager):
    """FantasyPros weekly expert consensus: start whoever the experts project to score the most."""
    key, name, kind, model, params = "experts", "FantasyPros experts", "bot", "weekly expert consensus", "humans"

    def __init__(self, weekly):
        self.proj = dict(zip(weekly.gsis_id, weekly.r2p_pts))
        self.rank_ = dict(zip(weekly.gsis_id, weekly.pos_rank))

    def rank(self, rows):
        return {pid: {"score": float(self.proj.get(pid) or 0.0), "expert_rank": self.rank_.get(pid)} for pid in rows.player_id}


class SeasonAverage(Manager):
    key, name, kind, model, params = "season_avg", "Season-average manager", "bot", "season PPR average", "0"

    def rank(self, rows):
        return {r.player_id: {"score": float(r.baseline_avg)} for r in rows.itertuples()}


class HotHand(Manager):
    key, name, kind, model, params = "hot_hand", "Hot-hand manager", "bot", "last-3-games PPR average", "0"

    def rank(self, rows):
        return {r.player_id: {"score": float(r.baseline_hot)} for r in rows.itertuples()}


def league_managers(finetuned_model, weekly_ecr):
    return [
        GlinerDecide("glifan", "glifan (GLiNER Decide, fine-tuned)", finetuned_model),
        Jev(),
        GlinerDecide("decide_base", "GLiNER Decide (untrained)", "fastino/GLiNER-2.5-Decide"),
        Experts(weekly_ecr),
        SeasonAverage(),
        HotHand(),
    ]
