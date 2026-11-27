"""Run a team file over rows. Four stage types, no code in the team file.

Rows flow through the stages in file order. A stage that a `route` names as a target is
owned by that route: it runs once, on its slice, and not again in the main sequence.
Models return rows as a JSON array; rows they lose or break stay as they were.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

import httpx

from .corrupt import COLUMNS
from .otari import ChatResult, OtariError
from .team import Stage, Team

PROVIDERS = {"ollama", "otari-ai"}
PRIVATE_KEYS = {"drop", "flag", "_pos"}
MAX_TOKENS_PER_ROW = 120
_ARRAY = re.compile(r"\[\s*\{.*?\}\s*\]", re.S)
_OBJECT = re.compile(r"\{.*\}", re.S)
RETRYABLE = {408, 429, 500, 502, 503, 504}

ChatFn = Callable[[str, list[dict], int], ChatResult]


@dataclass
class Call:
    stage: str
    model: str
    provider: str
    rows_in: int
    rows_out: int
    seconds: float
    prompt_tokens: int
    completion_tokens: int
    unparsed: int
    error: str = ""  # transport or gateway failure; the rows were kept as they were


@dataclass
class StageStats:
    name: str
    model: str
    requests: int = 0
    rows: int = 0
    seconds: float = 0.0
    unparsed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    local_requests: int = 0
    refused_drops: int = 0  # real rows a model wanted to delete that plain code kept
    failed_requests: int = 0  # timeouts and gateway errors; their rows count as unparsed
    provider_requests: dict[str, int] = field(default_factory=dict)


def qualify_model(model: str) -> str:
    """`qwen2.5:3b` -> `ollama:qwen2.5:3b`; a string that already names a provider is left alone."""
    head = model.split(":", 1)[0]
    return model if head in PROVIDERS else f"ollama:{model}"


def parse_rows(text: str) -> list[dict] | None:
    """The last JSON array of objects in a reply, fences and prose allowed. A lone object counts as one row."""
    candidates = _ARRAY.findall(text or "")
    if not candidates:
        return _salvage(text or "")
    for raw in reversed(candidates):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # greedy fallback: from this '[' to the last ']' in the text
            start = text.rfind(raw)
            end = text.rfind("]")
            try:
                data = json.loads(text[start:end + 1])
            except (json.JSONDecodeError, ValueError):
                continue
        if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
            return data
    return None


_FLAT_OBJECT = re.compile(r"\{[^{}]*\}", re.S)


def _salvage(text: str) -> list[dict] | None:
    """A reply cut off mid-array (token limit) or a lone object: keep every complete flat object."""
    start = text.rfind("[")
    rows = []
    for m in _FLAT_OBJECT.finditer(text[start:] if start >= 0 else text):
        try:
            data = json.loads(m.group())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows or None


def local_share(calls: list[Call]) -> float:
    """Share of answered requests that Otari says Ollama served. A failed request was served by
    nobody, so it is left out here and shows up in the failed-requests count instead; otherwise one
    timeout would drop a fully local team below 100%. An answer with no provider header is not local."""
    served = [c for c in calls if not c.error]
    return sum(1 for c in served if c.provider == "ollama") / len(served) if served else 1.0


def _sample_csv(sample: list[dict]) -> str:
    cols = [c for c in COLUMNS if c in (sample[0] if sample else {})] or COLUMNS
    lines = [",".join(cols)] + [",".join(str(r.get(c, "")) for c in cols) for r in sample]
    return "\n".join(lines)


def _public(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in PRIVATE_KEYS}


class Runner:
    def __init__(self, team: Team, sample: list[dict], chat: ChatFn, on_call: Callable[[Call], None]):
        self.team = team
        self.sample_text = _sample_csv(sample)
        self.chat = chat
        self.on_call = on_call
        self.stats: dict[str, StageStats] = {}
        self._prompts: dict[str, str] = {}
        self.remaining: Counter = Counter()  # copies of each id still present, across route slices

    def stat(self, stage: Stage) -> StageStats:
        return self.stats.setdefault(stage.name, StageStats(stage.name, ", ".join(stage.all_models())))

    def begin_stage(self, rows: list[dict]) -> None:
        self.remaining = Counter(str(r.get("id", "")).strip() for r in rows)
        self._initial = Counter(self.remaining)

    def prompt(self, stage: Stage) -> str:
        key = str(stage.prompt)
        if key not in self._prompts:
            self._prompts[key] = stage.prompt.read_text().replace("{sample}", self.sample_text).strip()
        return self._prompts[key]

    def ask(self, stage: Stage, model: str, system: str, rows: list[dict], extra: str = "") -> tuple[list[dict], list[bool]]:
        """One request. Returns (rows after the model, applied flag per row). Rows keep their order and count.
        A timeout or a gateway failure keeps every row as it was and counts the request as failed."""
        public = [_public(r) for r in rows]
        user = "Rows:\n" + json.dumps(public, ensure_ascii=False) + "\n\nReturn the corrected rows as a JSON array of objects with the same keys and every value as a string" + (extra or "") + "."
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        qualified = qualify_model(model)
        st = self.stat(stage)
        error = ""
        started = time.perf_counter()
        try:
            res = self.chat(qualified, messages, MAX_TOKENS_PER_ROW * len(rows) + 200)
        except httpx.HTTPError as e:
            error = f"{type(e).__name__}: {e}"[:200]
            res = None
        except OtariError as e:
            if getattr(e, "status", 0) not in RETRYABLE:
                raise
            error = str(e)[:200]
            res = None
        if res is None:
            seconds = time.perf_counter() - started
            applied = [False] * len(rows)
            st.requests += 1
            st.seconds += seconds
            st.provider_requests["unknown"] = st.provider_requests.get("unknown", 0) + 1
            st.failed_requests += 1
            st.unparsed += len(rows)
            self.on_call(Call(stage.name, model, "unknown", len(rows), 0, seconds, 0, 0, len(rows), error))
            return rows, applied
        parsed = parse_rows(res.content)
        merged, applied = _merge(rows, parsed)
        unparsed = applied.count(False)
        st.requests += 1
        st.seconds += res.seconds
        st.unparsed += unparsed
        st.prompt_tokens += res.prompt_tokens
        st.completion_tokens += res.completion_tokens
        provider = res.provider or "unknown"  # no header, no credit: locality is only ever claimed from Otari's own header
        st.provider_requests[provider] = st.provider_requests.get(provider, 0) + 1
        st.local_requests += 1 if provider == "ollama" else 0
        self.on_call(Call(stage.name, model, provider, len(rows), len(parsed) if parsed else 0, res.seconds, res.prompt_tokens, res.completion_tokens, unparsed))
        return merged, applied

    def run_stage(self, stage: Stage, rows: list[dict]) -> list[dict]:
        if stage.type == "map":
            return self._map(stage, rows)
        if stage.type == "vote":
            return self._vote(stage, rows)
        if stage.type == "verify":
            return self._verify(stage, rows)
        if stage.type == "route":
            return self._route(stage, rows)
        raise ValueError(stage.type)

    def _batches(self, stage: Stage, rows: list[dict]):
        for i in range(0, len(rows), stage.batch):
            yield rows[i:i + stage.batch]

    def _apply_drops(self, stage: Stage, rows: list[dict]) -> list[dict]:
        """Honor "drop": true only where plain code agrees: an empty id (junk) or an id another
        copy of which is still present (duplicate). The last remaining copy is always kept, across
        route slices too. A drop of a real row is refused and counted."""
        ids = [str(r.get("id", "")).strip() for r in rows]
        flagged = [_truthy(r.get("drop")) for r in rows]
        here = Counter(ids)
        for rid, n in here.items():
            if rid and n > 1 and self.remaining[rid] == n:
                idx = [i for i, x in enumerate(ids) if x == rid]
                if all(flagged[i] for i in idx):
                    flagged[idx[0]] = False  # all copies are in this slice and all flagged: keep the first
        kept: list[dict] = []
        refused = 0
        for r, rid, drop in zip(rows, ids, flagged):
            if drop:
                if rid == "":
                    continue
                if self.remaining[rid] > 1:
                    self.remaining[rid] -= 1
                    continue
                if here[rid] == 1 and self.remaining[rid] == 1 and sum(1 for x in ids if x == rid) == 1 and self._was_unique(rid):
                    refused += 1
            kept.append(_strip(r, {"drop"}))
        self.stat(stage).refused_drops += refused
        return kept

    def _was_unique(self, rid: str) -> bool:
        return self._initial.get(rid, 0) == 1

    def _map(self, stage: Stage, rows: list[dict]) -> list[dict]:
        out: list[dict] = []
        system = self.prompt(stage)
        for batch in self._batches(stage, rows):
            merged, _ = self.ask(stage, stage.model, system, batch, '. A junk row or a duplicate that should be removed gets "drop": true')
            out.extend(merged)
        self.stat(stage).rows += len(rows)
        return self._apply_drops(stage, out)

    def _vote(self, stage: Stage, rows: list[dict]) -> list[dict]:
        """Each voter sees the same original rows and may change only the vote column.
        Majority wins; ties go to the first voter that answered; a voter whose reply could not
        be read abstains for those rows."""
        system = self.prompt(stage)
        out: list[dict] = []
        for batch in self._batches(stage, rows):
            ballots: list[list[str | None]] = []
            for model in stage.models:
                copies = [dict(r) for r in batch]
                answered, applied = self.ask(stage, model, system, copies, f', changing only "{stage.column}"')
                ballots.append([str(r.get(stage.column, "")) if ok else None for r, ok in zip(answered, applied)])
            for i, row in enumerate(batch):
                votes = [b[i] for b in ballots if b[i] is not None]
                if votes:
                    counts = Counter(votes)
                    top = max(counts.values())
                    row[stage.column] = next(v for v in votes if counts[v] == top)
                out.append(row)
        self.stat(stage).rows += len(rows)
        return out

    def _verify(self, stage: Stage, rows: list[dict]) -> list[dict]:
        system = self.prompt(stage) + "\n\nReference sample of clean rows:\n" + self.sample_text
        extra = '. Fix what you can; a row you are unsure about gets "flag": true; a row that should be removed gets "drop": true'
        out: list[dict] = []
        for batch in self._batches(stage, rows):
            merged, _ = self.ask(stage, stage.model, system, batch, extra)
            out.extend(merged)
        for _ in range(stage.retry):
            flagged = [r for r in out if _truthy(r.get("flag"))]
            if not flagged:
                break
            for r in flagged:
                r.pop("flag", None)
            for batch in self._batches(stage, flagged):
                self.ask(stage, stage.model, system, batch, extra)  # mutates the row objects in place
        self.stat(stage).rows += len(rows)
        return [_strip(r, {"flag"}) for r in self._apply_drops(stage, out)]

    def _route(self, stage: Stage, rows: list[dict]) -> list[dict]:
        """Split rows by a column, run each target stage on its slice, merge back in original order."""
        slices: dict[str, list[dict]] = {}
        for i, row in enumerate(rows):
            row["_pos"] = i
            value = str(row.get(stage.by, "")).strip()
            target = stage.to.get(value) or stage.to.get("*") or ""
            slices.setdefault(target, []).append(row)
        merged: list[dict] = []
        for target, part in slices.items():
            merged.extend(part if target == "" else self.run_stage(self.team.stage(target), part))
        merged.sort(key=lambda r: r.get("_pos", 0))
        return [_strip(r, {"_pos"}) for r in merged]


def _truthy(v) -> bool:
    return v is True or str(v).strip().lower() in ("true", "yes", "1")


def _strip(row: dict, keys: set[str]) -> dict:
    return {k: v for k, v in row.items() if k not in keys}


def _merge(rows: list[dict], parsed: list[dict] | None) -> tuple[list[dict], list[bool]]:
    """Apply a model's answer to the rows it was sent. Returns the rows and an applied flag per row.

    Ids win: a sent row takes the answer that carries its id. Sent rows with no id (junk) take the
    answers with no id, in order. Only when the reply carries none of the ids it was sent, and has
    the same count, are rows matched by position (the model mangled every id). Anything else
    stays as it was and counts as unparsed. An answer never lands on a row it was not meant for.
    """
    if not parsed:
        return rows, [False] * len(rows)
    sent_ids = [str(r.get("id", "")).strip() for r in rows]
    by_id: dict[str, dict] = {}
    blanks: list[dict] = []
    for a in parsed:
        gid = str(a.get("id", "")).strip()
        if gid and gid in sent_ids:
            by_id.setdefault(gid, a)
        elif not gid:
            blanks.append(a)
    if not by_id and len(parsed) == len(rows) and any(sent_ids):
        for row, ans in zip(rows, parsed):
            _apply(row, ans)
        return rows, [True] * len(rows)
    applied = []
    blank_iter = iter(blanks)
    for row, rid in zip(rows, sent_ids):
        ans = by_id.get(rid) if rid else next(blank_iter, None)
        if ans is None:
            applied.append(False)
        else:
            _apply(row, ans)
            applied.append(True)
    return rows, applied


def _apply(row: dict, ans: dict) -> None:
    rid = row.get("id")
    for k, v in ans.items():
        row[k] = v if not isinstance(v, (dict, list)) else json.dumps(v)
    row["id"] = rid  # the id is never the model's to change


def run_team(team: Team, rows: list[dict], sample: list[dict], chat: ChatFn, on_call: Callable[[Call], None]) -> tuple[list[dict], list[StageStats]]:
    runner = Runner(team, sample, chat, on_call)
    owned = {target for s in team.stages if s.type == "route" for target in s.to.values()}
    current = rows
    for stage in team.stages:
        if stage.name in owned:
            continue
        runner.begin_stage(current)
        current = runner.run_stage(stage, current)
    for stage in team.stages:
        if stage.type != "route":
            runner.stat(stage)  # every model stage shows up in the card, even with zero requests
    order = [s.name for s in team.stages]
    stats = sorted(runner.stats.values(), key=lambda s: order.index(s.name))
    return [_strip(r, PRIVATE_KEYS) for r in current], stats
