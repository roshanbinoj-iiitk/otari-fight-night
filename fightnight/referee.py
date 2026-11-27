"""The referee: makes the messy file, runs stock then your team, grades both. Plain code."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .corrupt import COLUMNS, corrupt, make_golden, read_csv, write_csv
from .grade import Grade, grade
from .otari import ChatResult, Otari
from .pipeline import Call, StageStats, local_share, qualify_model, run_team
from .team import Team

DATA_DIR = Path("data")
SAMPLE_PATH = DATA_DIR / "sample.csv"


@dataclass
class TeamResult:
    team: Team
    grade: Grade
    stages: list[StageStats]
    seconds: float
    requests: int
    local_share: float
    weights_gb: float
    usage: dict


@dataclass
class FightResult:
    seed: int
    preset: str
    rows: int
    messy_rows: int
    dataset_sha: str
    stock: TeamResult
    team: TeamResult


def make_dataset(seed: int, rows: int, preset: str, out_dir: Path = DATA_DIR) -> tuple[list[dict], list[dict], str]:
    """Write data/messy.csv; return (golden, messy, sha of messy). The golden file is written
    only after both teams have run (write_golden), so nothing that runs during a fight can read it."""
    out_dir.mkdir(exist_ok=True)
    golden = make_golden(rows, random.Random(seed))
    messy = corrupt(golden, random.Random(seed + 1), preset)
    stale = out_dir / "golden.csv"
    if stale.exists():
        stale.unlink()
    write_csv(out_dir / "messy.csv", messy, COLUMNS)
    sha = hashlib.sha256((out_dir / "messy.csv").read_bytes()).hexdigest()[:12]
    return golden, messy, sha


def write_golden(golden: list[dict], out_dir: Path = DATA_DIR) -> None:
    write_csv(out_dir / "golden.csv", golden, COLUMNS)


def load_sample() -> list[dict]:
    return read_csv(SAMPLE_PATH) if SAMPLE_PATH.exists() else make_golden(20, random.Random(1))


def chat_via(otari: Otari, api_key: str, timeout: float) -> Callable[[str, list[dict], int], ChatResult]:
    def chat(model: str, messages: list[dict], max_tokens: int) -> ChatResult:
        return otari.chat(api_key, model, messages, max_tokens, timeout)

    return chat


def model_weights(team: Team, sizes: dict[str, float]) -> float:
    """GB of local model weights a team loads, from Ollama's listing. Hosted models weigh nothing here."""
    total = 0.0
    for m in team.models():
        head, _, rest = m.partition(":")
        if head == "ollama":
            m = rest
        elif head in ("otari-ai",):
            continue
        total += sizes.get(m, 0.0)
    return round(total, 2)


def run_one(team: Team, messy: list[dict], golden: list[dict], sample: list[dict], chat, log, sizes: dict[str, float], usage_fn=None, label: str = "") -> tuple[TeamResult, list[dict]]:
    calls: list[Call] = []
    t0 = datetime.now(timezone.utc)

    def on_call(c: Call) -> None:
        calls.append(c)
        log({"team": label or team.name, **asdict(c)})
        line = f"  {label or team.name}: {c.stage} {c.model} request {len(calls)}, {c.rows_in} rows, {c.seconds:.1f}s  (total {sum(x.seconds for x in calls):.0f}s)"
        if sys.stdout.isatty():
            print("\r" + line.ljust(100), end="", flush=True)
        else:
            print(line, flush=True)

    cleaned, stages = run_team(team, [dict(r) for r in messy], sample, chat, on_call)
    if sys.stdout.isatty():
        print()
    g = grade(golden, messy, cleaned) if golden else Grade(repair_pct=0.0)
    usage = usage_fn(t0.isoformat(timespec="seconds")) if usage_fn else {}
    return TeamResult(
        team=team,
        grade=g,
        stages=stages,
        seconds=round(sum(c.seconds for c in calls), 1),
        requests=len(calls),
        local_share=local_share(calls),
        weights_gb=model_weights(team, sizes),
        usage=usage,
    ), cleaned


def warm_up(otari: Otari, team: Team, api_key: str, timeout: float) -> None:
    """Reload a team's local models just before it runs, through Otari like every other call.

    The preflight loads every model before the stock team starts, but Ollama unloads a model after
    5 idle minutes and evicts one when memory runs short, so a model only your team uses can go cold
    while stock runs. The request goes on the stock key, whose usage has already been read, so it
    never lands in your team's numbers. Best effort: a failure here surfaces in the real run."""
    for m in team.models():
        if m.startswith("otari-ai:"):
            continue
        try:
            res = otari.chat(api_key, qualify_model(m), [{"role": "user", "content": "Reply with the single word OK."}], 5, timeout)
            print(f"  warm-up {m}: {res.seconds:.1f}s")
        except Exception as e:  # noqa: BLE001 - best effort, see docstring
            print(f"  warm-up {m} failed ({type(e).__name__}); continuing")


def run_fight(settings, otari: Otari, team: Team, stock: Team, sizes: dict[str, float], log_path: Path = Path("fight-log.jsonl"), out_dir: Path = DATA_DIR) -> FightResult:
    seed = settings.seed if settings.seed is not None else random.SystemRandom().randrange(1, 10**6)
    golden, messy, sha = make_dataset(seed, settings.rows, settings.preset, out_dir)
    sample = load_sample()
    if out_dir != DATA_DIR:
        write_csv(out_dir / "sample.csv", sample, COLUMNS)
        # The last fight's copy in data/ is the answer key on a replayed SEED; it must not exist
        # while this fight runs, same as the one in out_dir (make_dataset removed that).
        (DATA_DIR / "golden.csv").unlink(missing_ok=True)
    print(f"  dataset: {len(golden)} clean rows -> {len(messy)} messy rows, preset {settings.preset}, seed {seed}")
    with log_path.open("w") as f:
        def log(row: dict) -> None:
            f.write(json.dumps(row) + "\n")
            f.flush()  # the log is the forensic record; it must survive a crash or a Ctrl-C

        results = {}
        for label, t, key in (("stock", stock, settings.key_stock), ("team", team, settings.key_team)):
            if otari and label == "team":
                warm_up(otari, t, settings.key_stock, settings.timeout_seconds)
            usage_fn = (lambda since, k=key: otari.key_usage(k, since)) if otari else None
            r, cleaned = run_one(t, messy, golden, sample, chat_via(otari, key, settings.timeout_seconds), log, sizes, usage_fn, label=label)
            write_csv(out_dir / f"{label}.clean.csv", cleaned, COLUMNS)
            failed = sum(st.failed_requests for st in r.stages)
            print(f"  {label} ({t.name}): net repair {r.grade.repair_pct}% ({r.grade.fixed}/{r.grade.problems} fixed, {r.grade.broken} broken) in {r.seconds:.0f}s, {r.requests} requests" + (f", {failed} FAILED" if failed else "") + f", {r.weights_gb} GB of models, dup kept {r.grade.dup_kept}, dropped {r.grade.dropped}, junk kept {r.grade.junk_kept}")
            if failed:
                print(f"  warning: {failed} request(s) timed out or failed; those rows were left as they were. Raise TIMEOUT_SECONDS or lower batch sizes.")
            results[label] = r
        write_golden(golden, out_dir)  # only now: nothing that ran during the fight could have read it
    return FightResult(seed=seed, preset=settings.preset, rows=len(golden), messy_rows=len(messy), dataset_sha=sha, stock=results["stock"], team=results["team"])


def read_any_csv(path: Path) -> tuple[list[dict], list[str], str]:
    """Read a CSV someone exported from somewhere: BOM, comma or semicolon or tab, UTF-8 or Latin-1.
    Returns (rows, columns, delimiter). Ragged rows are an error naming the row."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.reader(text.splitlines())
    columns = next(reader, [])
    if delimiter != ",":
        reader = csv.reader(text.splitlines(), delimiter=delimiter)
        columns = next(reader, [])
    rows = []
    for n, cells in enumerate(reader, start=2):
        if len(cells) != len(columns):
            raise ValueError(f"{path.name} row {n} has {len(cells)} cells but the header has {len(columns)} columns; fix the file first")
        rows.append(dict(zip(columns, cells)))
    return rows, columns, delimiter


def clean_file(team: Team, path: Path, sample: list[dict], chat, on_call) -> Path:
    """Run a team on any CSV. Rows get an id for the pipeline and lose it again on the way out.

    Ids are what lets plain code honor a model's drop, so they are assigned with care: exact
    duplicate rows share one id (so one copy may go), and rows that are a repeated header or
    have no data at all get no id (so they may go as junk). Everything else is a real row.
    """
    rows, columns, delimiter = read_any_csv(path)
    had_id = "id" in columns
    if not had_id:
        seen: dict[tuple, str] = {}
        n = 0
        for r in rows:
            cells = tuple(str(r.get(c, "")).strip() for c in columns)
            if not any(cells) or cells == tuple(columns):
                r["id"] = ""
                continue
            if cells not in seen:
                n += 1
                seen[cells] = f"R{n:05d}"
            r["id"] = seen[cells]
    cleaned, _ = run_team(team, rows, sample, chat, on_call) if rows else ([], [])
    out = path.with_name(path.stem + ".clean.csv")
    out_columns = columns if had_id else [c for c in columns if c != "id"]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_columns, extrasaction="ignore", delimiter=delimiter)
        w.writeheader()
        for r in cleaned:
            w.writerow({c: r.get(c, "") for c in out_columns})
    return out
