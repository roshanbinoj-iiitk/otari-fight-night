"""Preserve experiments and compare results without contacting a model or gateway."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import card as cardmod
from .team import Team


def snapshot_team(team: Team, target: Path) -> None:
    """Keep the original YAML and a portable copy with relative prompt paths."""
    target.mkdir(parents=True)
    original = team.path.read_text()
    (target / "original.yml").write_text(original)
    doc = yaml.safe_load(original)
    for i, (raw, stage) in enumerate(zip(doc["stages"], team.stages)):
        if stage.prompt is None:
            continue
        relative = Path("prompts") / str(i) / stage.prompt.name
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(stage.prompt.read_bytes())
        raw["prompt"] = relative.as_posix()
    (target / "team.yml").write_text(yaml.safe_dump(doc, sort_keys=False))
    (target / "source.json").write_text(json.dumps({
        "file": str(team.path), "sha256": team.sha256,
        "note": "original.yml retains the scored YAML; team.yml rewrites prompt paths for replay and has a different hash.",
    }, indent=2) + "\n")


def start_run(team: Team, stock: Team, root: Path = Path("runs")) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir()
    snapshot_team(team, run_dir / "team")
    snapshot_team(stock, run_dir / "stock")
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        revision, dirty = "unknown", "unknown"
    (run_dir / "run.json").write_text(json.dumps({
        "revision": revision, "working_tree_dirty": bool(dirty), "status": "started",
    }, indent=2) + "\n")
    return run_dir


def finish_run(run_dir: Path, card: dict, latest: Path = Path(".")) -> None:
    cardmod.write(card, run_dir / "fight-card.md", run_dir / "fight-card.json")
    manifest = json.loads((run_dir / "run.json").read_text())
    manifest["status"] = "complete"
    (run_dir / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # Preserve the existing convenience paths. Historical runs never read from these.
    for name in ("fight-card.md", "fight-card.json", "fight-log.jsonl"):
        shutil.copyfile(run_dir / name, latest / name)
    (latest / "data").mkdir(exist_ok=True)
    for name in ("golden.csv", "messy.csv", "stock.clean.csv", "team.clean.csv"):
        shutil.copyfile(run_dir / "data" / name, latest / "data" / name)


def read_card(path: Path) -> dict:
    file = path / "fight-card.json" if path.is_dir() else path
    try:
        card = json.loads(file.read_text())
        # Access the fields the comparison needs here, so partial runs fail clearly.
        for key in ("sha256", "seed", "preset", "rows"):
            card["dataset"][key]
        for key in ("repair_pct", "fixed", "broken", "problems", "seconds", "requests", "models", "sha256", "otari_usage"):
            card["team"][key]
        return card
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(f"Cannot compare {file}: needs a completed fight-card.json ({e})") from e


def _tokens(side: dict, key: str) -> int | None:
    stages = side.get("stages", [])
    if not stages or any(key not in stage for stage in stages):
        return None  # Older cards did not preserve stage token counts.
    return sum(stage[key] for stage in stages)


def compare(before: dict, after: dict) -> str:
    for key in ("sha256", "seed", "preset", "rows"):
        if before["dataset"][key] != after["dataset"][key]:
            raise ValueError(f"Datasets differ ({key}); rerun with the same SEED, PRESET and ROWS before comparing.")
    b, a = before["team"], after["team"]
    if a["problems"] != b["problems"]:
        raise ValueError("Problem counts differ; these cards use incompatible grading or datasets.")
    lines = ["# Experiment comparison", "", "After minus before, on the same messy dataset. Positive resource deltas mean more work.", "",
             "| Metric | Before | After | Change |", "|---|---|---|---|"]
    fields = [("Net repair (points)", "repair_pct"), ("Dirty cells fixed", "fixed"),
              ("Broken-cell penalties (includes junk)", "broken"), ("Request seconds", "seconds"),
              ("Requests", "requests"), ("Failed requests", "failed_requests")]
    for label, key in fields:
        bv, av = b.get(key), a.get(key)
        change = f"{av - bv:+.1f}" if isinstance(av, (float, int)) and isinstance(bv, (float, int)) else "n/a"
        lines.append(f"| {label} | {bv if bv is not None else 'n/a'} | {av if av is not None else 'n/a'} | {change} |")
    # Use runner tokens, not gateway totals whose time windows may contain other calls.
    for label, key in (("Prompt tokens", "prompt_tokens"), ("Completion tokens", "completion_tokens")):
        bv, av = _tokens(b, key), _tokens(a, key)
        change = f"{av - bv:+d}" if bv is not None and av is not None else "n/a"
        lines.append(f"| {label} | {bv if bv is not None else 'n/a'} | {av if av is not None else 'n/a'} | {change} |")
    bv, av = b["otari_usage"].get("cost_usd"), a["otari_usage"].get("cost_usd")
    change = f"{av - bv:+.4f}" if bv is not None and av is not None else "n/a"
    lines.append(f"| Gateway-reported cost (USD) | {cardmod._usd(bv)} | {cardmod._usd(av)} | {change} |")
    lines += ["", f"Models: {', '.join(b['models'])} → {', '.join(a['models'])}.",
              f"Team and prompt hash: `{b['sha256']}` → `{a['sha256']}`."]
    if before.get("machine") != after.get("machine"):
        lines.append("Machine differs; this is not a controlled comparison of the team change alone.")
    # Only versions: the gateway block also carries per-team integrity data, which differs by design.
    versions = ("otari_version", "ollama_version")
    if any((before.get("gateway") or {}).get(k) != (after.get("gateway") or {}).get(k) for k in versions):
        lines.append("Gateway or model-server version differs; this is not a controlled comparison of the team change alone.")
    if before.get("request_timing") != after.get("request_timing"):
        lines.append("Timing definitions differ; older cards omit failed-request duration.")
    lines += ["", "These are whole-team results, not proof of any individual stage's contribution. Change one thing, repeat the run, and check another seed before drawing a conclusion.", ""]
    return "\n".join(lines)
