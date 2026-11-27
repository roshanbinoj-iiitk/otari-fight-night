"""Integrity signals for the fight card. None of these stop a determined cheat; the organizer's
rerun on a seed nobody has seen does that. They make the cheap tricks visible on the card."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import yaml
from pathlib import Path

from .team import Team

_DATASET_ID = re.compile(r"\bT\d{4}\b")  # golden ids; the shipped sample uses S0001.. on purpose
CODE_FILES = ("corrupt.py", "grade.py", "pipeline.py", "referee.py", "team.py", "card.py", "otari.py", "integrity.py")
HERE = Path(__file__).parent
REPO = HERE.parent
OFFICIAL_DIGESTS = {"qwen2.5:3b": "357c53fb659c"}  # the stock team's model, as Ollama reports it


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=10, cwd=REPO).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _digest(parts: list[tuple[str, bytes]]) -> str:
    d = hashlib.sha256()
    for name, data in parts:
        d.update(name.encode() + b"\0" + data + b"\0")
    return d.hexdigest()[:12]


def referee_fingerprint() -> dict:
    """sha256 over the referee's own source, plus the last commit that touched it. Organizers
    check that commit is on this repo's main (check-card), so main can keep changing and every
    card made from a clean checkout stays official; a fork that edits the grader is not on main,
    and an uncommitted edit shows as (modified)."""
    parts = [(name, (HERE / name).read_bytes()) for name in CODE_FILES if (HERE / name).exists()]
    git = "unknown"
    last = _git("log", "-1", "--format=%h", "--", "fightnight")
    if last:
        git = last + (" (modified)" if _git("status", "--porcelain", "--", "fightnight") else "")
    return {"code_sha256": _digest(parts), "git": git, "files": list(CODE_FILES)}


def fingerprint_at(commit: str) -> str:
    """The referee code sha256 as it was at a commit, read straight from git."""
    parts = []
    for name in CODE_FILES:
        out = subprocess.run(["git", "show", f"{commit}:fightnight/{name}"], capture_output=True, cwd=REPO, timeout=10)
        if out.returncode == 0:
            parts.append((name, out.stdout))
    return _digest(parts)


def stock_sha_at(commit: str) -> str:
    """The stock team sha256 (yml plus its prompts) as it was at a commit."""
    yml = subprocess.run(["git", "show", f"{commit}:teams/stock.yml"], capture_output=True, cwd=REPO, timeout=10).stdout
    d = hashlib.sha256(yml)
    for st in (yaml.safe_load(yml.decode()) or {}).get("stages", []):
        prompt = st.get("prompt")
        if prompt and st.get("type") in ("map", "vote", "verify"):
            rel = (Path("teams") / prompt).as_posix()
            data = subprocess.run(["git", "show", f"{commit}:{rel}"], capture_output=True, cwd=REPO, timeout=10).stdout
            d.update(b"\0" + Path(prompt).name.encode() + b"\0" + data)
    return d.hexdigest()[:12]


def verify_card(path: Path, upstream: str = "origin/main", official_digests: dict[str, str] | None = None, preset: str = "medium", rows: int = 50) -> tuple[bool, list[str]]:
    """The organizer's check of a submitted fight-card.json. Returns (ok, findings). It is what
    gates a rerun, not a substitute for it."""
    official_digests = OFFICIAL_DIGESTS if official_digests is None else official_digests
    card = json.loads(Path(path).read_text())
    findings: list[str] = []
    integ = (card.get("gateway") or {}).get("integrity") or {}
    ref = integ.get("referee") or {}
    git = str(ref.get("git", "unknown"))
    commit = git.split()[0] if git and git != "unknown" else ""
    if not commit:
        findings.append("referee commit unknown: card was not made from a git checkout")
    else:
        if "(modified)" in git:
            findings.append(f"referee code was modified in the working tree at commit {commit}")
        if upstream != "HEAD":
            _git("fetch", "-q", upstream.split("/")[0]) if "/" in upstream else None
        on_main = subprocess.run(["git", "merge-base", "--is-ancestor", commit, upstream], capture_output=True, cwd=REPO, timeout=10).returncode == 0
        if not on_main:
            findings.append(f"referee commit {commit} is not on {upstream}")
        else:
            if fingerprint_at(commit) != ref.get("code_sha256"):
                findings.append(f"referee code sha {ref.get('code_sha256')} does not match commit {commit}")
            if stock_sha_at(commit) != (card.get("stock") or {}).get("sha256"):
                findings.append(f"stock sha {(card.get('stock') or {}).get('sha256')} does not match the stock team at commit {commit}")
    for model, digest in official_digests.items():
        seen = (integ.get("model_digests") or {}).get(model)
        if seen is not None and seen != digest:
            findings.append(f"{model} digest {seen} is not the official {digest} (retagged weights?)")
    for who, notes in (integ.get("prompt_leaks") or {}).items():
        for n in notes:
            findings.append(f"answer-key flag on {who} prompts: {n}")
    team = card.get("team") or {}
    if team.get("local_requests_pct", 0) < 100:
        findings.append(f"only {team.get('local_requests_pct')}% of team requests served locally")
    for m in team.get("models", []):
        if "cloud" in str(m).lower() or str(m).startswith("otari-ai:"):
            findings.append(f"team uses a non-local model: {m}")
    d = card.get("dataset") or {}
    if d.get("preset") != preset or d.get("rows") != rows:
        findings.append(f"dataset was {d.get('rows')} rows at preset {d.get('preset')}, scored config is {rows} rows at {preset}")
    if (card.get("stock") or {}).get("failed_requests"):
        findings.append(f"stock team had {card['stock']['failed_requests']} failed request(s); its score may be depressed")
    return (not findings), findings


def prompt_leaks(team: Team, golden: list[dict]) -> list[str]:
    """Signs that a prompt carries the answer key: dataset ids, or a golden row's vendor, amount
    and category together on one line. Public knowledge (vendor to category, formats) is allowed
    and does not trip this."""
    notes: list[str] = []
    seen: set[Path] = set()
    rows = {(g["vendor"], g["amount"], g["category"]) for g in golden}
    for st in team.stages:
        if st.prompt is None or st.prompt in seen:
            continue
        seen.add(st.prompt)
        text = st.prompt.read_text(errors="replace")
        ids = sorted(set(_DATASET_ID.findall(text)))
        if ids:
            notes.append(f"{st.prompt.name}: mentions dataset id(s) {', '.join(ids[:5])}{'...' if len(ids) > 5 else ''}")
        hits = 0
        for line in text.splitlines():
            for vendor, amount, category in rows:
                if vendor in line and amount in line and category in line:
                    hits += 1
                    break
        if hits:
            notes.append(f"{st.prompt.name}: {hits} line(s) match a golden row of this dataset")
    return notes


def prompt_bytes(team: Team) -> int:
    return sum(st.prompt.stat().st_size for st in {s.prompt: s for s in team.stages if s.prompt}.values())
