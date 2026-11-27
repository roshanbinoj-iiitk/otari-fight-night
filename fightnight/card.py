"""Build the fight card: stock vs your team on the same messy file, same machine."""

from __future__ import annotations

import json
import shlex
from datetime import datetime, timezone
from pathlib import Path

from .referee import FightResult, TeamResult


def _side(r: TeamResult) -> dict:
    totals = r.usage.get("totals", {}) if r.usage else {}
    score = r.grade.repair_pct
    tokens = sum(s.prompt_tokens + s.completion_tokens for s in r.stages)
    return {
        "name": r.team.name,
        "file": str(r.team.path),
        "sha256": r.team.sha256,
        "models": r.team.models(),
        "repair_pct": score,
        "problems": r.grade.problems,
        "fixed": r.grade.fixed,
        "broken": r.grade.broken,
        "accuracy_pct": round(r.grade.accuracy * 100, 1),
        "per_column_repair_pct": dict(r.grade.per_column),
        "dup_kept": r.grade.dup_kept,
        "dropped": r.grade.dropped,
        "junk_kept": r.grade.junk_kept,
        "rows_out": r.grade.rows_out,
        "seconds": r.seconds,
        "requests": r.requests,
        "unparsed_rows": sum(s.unparsed for s in r.stages),
        "failed_requests": sum(s.failed_requests for s in r.stages),
        "refused_drops": sum(s.refused_drops for s in r.stages),
        "weights_gb": r.weights_gb,
        "repair_per_gb": round(score / r.weights_gb, 1) if r.weights_gb else None,
        "local_requests_pct": round(r.local_share * 100, 1),
        "otari_usage": {
            "requests": totals.get("request_count"),
            "errors": totals.get("error_count"),
            "prompt_tokens": totals.get("prompt_tokens"),
            "completion_tokens": totals.get("completion_tokens"),
            "avg_gateway_latency_ms": round(totals["avg_latency_ms"]) if totals.get("avg_latency_ms") is not None else None,
            "cost_usd": totals.get("cost"),
        },
        "stages": [{
            "name": s.name, "model": s.model, "requests": s.requests, "rows": s.rows,
            "seconds": round(s.seconds, 1), "unparsed": s.unparsed,
            "failed_requests": s.failed_requests, "local_requests": s.local_requests,
            "prompt_tokens": s.prompt_tokens, "completion_tokens": s.completion_tokens,
            "token_share_pct": round((s.prompt_tokens + s.completion_tokens) / tokens * 100, 1) if tokens else 0,
            "time_share_pct": round(s.seconds / r.seconds * 100, 1) if r.seconds else 0,
            "provider_requests": dict(s.provider_requests),
        } for s in r.stages],
    }


def build(result: FightResult, specs: dict, gateway: dict) -> dict:
    team, stock = _side(result.team), _side(result.stock)
    delta = round(team["repair_pct"] - stock["repair_pct"], 1)
    return {
        "schema_version": 2,
        "request_timing": "includes_failed_requests",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {"seed": result.seed, "preset": result.preset, "rows": result.rows, "messy_rows": result.messy_rows, "sha256": result.dataset_sha},
        "machine": specs,
        "gateway": gateway,
        "stock": stock,
        "team": team,
        "result": {"delta_points": delta, "winner": team["name"] if delta > 0 else (stock["name"] if delta < 0 else "draw")},
    }


def _na(v):
    return "n/a" if v is None else v


def _pct(v):
    return "n/a" if v is None else f"{v:.0f}%"


def _usd(v) -> str:
    if v is None:
        return "n/a"
    return f"${v:.2f}" if v == 0 or v >= 0.01 else f"${v:.4f}"


def render_md(card: dict) -> str:
    t, s, m, d, gw = card["team"], card["stock"], card["machine"], card["dataset"], card["gateway"]
    delta = card["result"]["delta_points"]
    sign = "+" if delta >= 0 else ""
    headline = f"**{t['name']}** beat the stock team by **{sign}{delta} points**" if delta > 0 else (f"The **stock** team won by **{delta} points**" if delta < 0 else "A **draw**")
    gpu = m.get("gpu", "") + (f" ({m['gpu_note']})" if m.get("gpu_note") else "")
    lines = [
        "# Fight card: Otari Fight Night",
        "",
        f"{headline}: net repair {t['repair_pct']}% vs {s['repair_pct']}% on {d['rows']} rows ({d['messy_rows']} messy, {t['problems']} problems), preset `{d['preset']}`. Generated {card['generated_at']}.",
        "",
        "Net repair = (dirty cells fixed - clean cells broken) / dirty cells. An untouched file scores 0. Removing duplicates and junk earns nothing (the referee can do that); keeping them costs.",
        "",
        "## Machine",
        "",
        f"- OS: {m.get('os')} ({m.get('arch')})",
        f"- CPU: {m.get('cpu')}",
        f"- RAM: {m.get('ram_gb')} GB",
        f"- GPU: {gpu}",
        f"- Ollama {gw.get('ollama_version')}, Otari {gw.get('otari_version')} at {gw.get('otari_url')}",
        "",
        "## Stock vs your team",
        "",
        "| | stock | yours |",
        "|---|---|---|",
        f"| Team file | `{s['file']}` | `{t['file']}` |",
        f"| Models | {', '.join(f'`{x}`' for x in s['models'])} | {', '.join(f'`{x}`' for x in t['models'])} |",
        f"| Net repair | {s['repair_pct']}% | **{t['repair_pct']}%** ({sign}{delta}) |",
        f"| Problems fixed | {s['fixed']} / {s['problems']} | {t['fixed']} / {t['problems']} |",
        f"| Clean cells broken | {s['broken']} | {t['broken']} |",
        f"| Cells exactly right (reference) | {s['accuracy_pct']}% | {t['accuracy_pct']}% |",
        f"| Duplicates kept | {s['dup_kept']} | {t['dup_kept']} |",
        f"| Real rows dropped | {s['dropped']} | {t['dropped']} |",
        f"| Junk rows kept | {s['junk_kept']} | {t['junk_kept']} |",
        f"| Rows a model lost or garbled (kept as-is) | {s['unparsed_rows']} | {t['unparsed_rows']} |",
        f"| Failed requests (timeouts, gateway errors) | {s['failed_requests']} | {t['failed_requests']} |",
        f"| Real rows a model tried to delete (refused) | {s['refused_drops']} | {t['refused_drops']} |",
        f"| Request seconds (including failures) | {s['seconds']} | {t['seconds']} |",
        f"| Requests | {s['requests']} | {t['requests']} |",
        f"| Model weights loaded | {s['weights_gb']} GB | {t['weights_gb']} GB |",
        f"| Net repair per GB | {_na(s['repair_per_gb'])} | {_na(t['repair_per_gb'])} |",
        f"| Requests served locally | {_pct(s['local_requests_pct'])} | {_pct(t['local_requests_pct'])} |",
        "",
        "Repair rate per column, stock: " + ", ".join(f"{k} {v}%" for k, v in s["per_column_repair_pct"].items()),
        "",
        "Repair rate per column, yours: " + ", ".join(f"{k} {v}%" for k, v in t["per_column_repair_pct"].items()),
        "",
        "## Otari usage (from the gateway's own log, per team key)",
        "",
        "| | stock | yours |",
        "|---|---|---|",
    ]
    for label, key in (("Requests", "requests"), ("Errors", "errors"), ("Prompt tokens", "prompt_tokens"), ("Completion tokens", "completion_tokens"), ("Avg gateway latency (ms)", "avg_gateway_latency_ms")):
        lines.append(f"| {label} | {_na(s['otari_usage'][key])} | {_na(t['otari_usage'][key])} |")
    lines.append(f"| Cost | {_usd(s['otari_usage']['cost_usd'])} | {_usd(t['otari_usage']['cost_usd'])} |")
    lines += [
        "",
        "## Your team, stage by stage",
        "",
        "| Stage | Model | Requests | Rows | Seconds | Rows lost or garbled | Failed requests |",
        "|---|---|---|---|---|---|---|",
    ]
    for st in t["stages"]:
        lines.append(f"| {st['name']} | {st['model']} | {st['requests']} | {st['rows']} | {st['seconds']} | {st['unparsed']} | {st['failed_requests']} |")
    lines += [
        "",
        "### Where the work went",
        "",
        "| Stage | Prompt tokens | Completion tokens | Token share | Request time share | Providers (requests) |",
        "|---|---|---|---|---|---|",
    ]
    for st in t["stages"]:
        providers = ", ".join(f"{p}: {n}" for p, n in sorted(st["provider_requests"].items())) or "n/a"
        lines.append(f"| {st['name']} | {st['prompt_tokens']} | {st['completion_tokens']} | {st['token_share_pct']}% | {st['time_share_pct']}% | {providers} |")
    active = [st for st in t["stages"] if st["requests"]]
    if active:
        slowest = max(active, key=lambda st: st["seconds"])
        most_tokens = max(active, key=lambda st: st["prompt_tokens"] + st["completion_tokens"])
        lines += ["", f"Most request time: **{slowest['name']}** ({slowest['time_share_pct']}%). Most tokens: **{most_tokens['name']}** ({most_tokens['token_share_pct']}%)."]
    lines += [
        "",
        "These shares measure cost, not quality: to see whether a stage earns its place, remove or swap it and rerun on the same seed. "
        "Request time sums model calls, failed ones included; it is not wall-clock time. Providers come from Otari's response headers; a failed request has none and shows as unknown.",
    ]
    integ = gw.get("integrity") or {}
    if integ:
        ref = integ.get("referee", {})
        lines += [
            "",
            "## Integrity (what the organizers check against the rerun)",
            "",
            f"- Referee code sha256 `{ref.get('code_sha256', 'unknown')}`, git `{ref.get('git', 'unknown')}`",
            "- Model digests from Ollama: " + ", ".join(f"`{m}` {d}" for m, d in integ.get("model_digests", {}).items()),
            f"- Otari reached Ollama at `{gw.get('ollama_url_from_docker') or 'unknown'}`",
            f"- Prompt bytes: stock {integ.get('prompt_bytes', {}).get('stock')}, yours {integ.get('prompt_bytes', {}).get('team')}",
        ]
        leaks = integ.get("prompt_leaks", {})
        flagged = [f"{who}: {n}" for who, notes in leaks.items() for n in notes]
        lines.append("- Answer-key check: " + ("**FLAGGED** " + "; ".join(flagged) if flagged else "no dataset ids or golden rows found in prompts"))
    lines += [
        "",
        "## Reproduce",
        "",
        f"`TEAM={shlex.quote(t['file'])} SEED={d['seed']} PRESET={d['preset']} ROWS={d['rows']} make fight`. Messy file sha256 `{d['sha256']}`. Team file sha256 `{t['sha256']}`, stock `{s['sha256']}`.",
        "",
    ]
    return "\n".join(lines)


def write(card: dict, md_path: Path = Path("fight-card.md"), json_path: Path = Path("fight-card.json")) -> None:
    md_path.write_text(render_md(card))
    json_path.write_text(json.dumps(card, indent=2) + "\n")
