# Fight card: Otari Fight Night

**small-batches** beat the stock team by **+6.8 points**: net repair 47.7% vs 40.9% on 50 rows (63 messy, 88 problems), preset `medium`. Generated 2026-11-20T20:04:15+00:00.

Net repair = (dirty cells fixed - clean cells broken) / dirty cells. An untouched file scores 0. Removing duplicates and junk earns nothing (the referee can do that); keeping them costs.

## Machine

- OS: macOS 26.5.2 (arm64)
- CPU: Apple M2 Pro
- RAM: 16 GB
- GPU: Apple M2 Pro (unified memory)
- Ollama 0.40.2, Otari 0.54.0 at http://localhost:8000

## Stock vs your team

| | stock | yours |
|---|---|---|
| Team file | `teams/stock.yml` | `team.yml` |
| Models | `qwen2.5:3b` | `qwen2.5:3b` |
| Net repair | 40.9% | **47.7%** (+6.8) |
| Problems fixed | 54 / 88 | 57 / 88 |
| Clean cells broken | 18 | 15 |
| Cells exactly right (reference) | 80.4% | 82.3% |
| Duplicates kept | 0 | 0 |
| Real rows dropped | 0 | 0 |
| Junk rows kept | 3 | 2 |
| Rows a model lost or garbled (kept as-is) | 21 | 11 |
| Failed requests (timeouts, gateway errors) | 0 | 0 |
| Real rows a model tried to delete (refused) | 35 | 47 |
| Seconds | 129.7 | 124.1 |
| Requests | 14 | 26 |
| Model weights loaded | 1.93 GB | 1.93 GB |
| Net repair per GB | 21.2 | 24.7 |
| Requests served locally | 100% | 100% |

Repair rate per column, stock: date 83.3%, vendor 57.1%, amount 72.2%, category 31.6%, note 50.0%

Repair rate per column, yours: date 91.7%, vendor 38.1%, amount 88.9%, category 42.1%, note 50.0%

## Otari usage (from the gateway's own log, per team key)

| | stock | yours |
|---|---|---|
| Requests | 14 | 26 |
| Errors | 0 | 0 |
| Prompt tokens | 19875 | 30946 |
| Completion tokens | 7948 | 7148 |
| Avg gateway latency (ms) | 9212 | 4739 |
| Cost | $0.00 | $0.00 |

## Your team, stage by stage

| Stage | Model | Requests | Rows | Seconds | Rows lost or garbled | Failed requests |
|---|---|---|---|---|---|---|
| clean | qwen2.5:3b | 13 | 63 | 59.9 | 8 | 0 |
| check | qwen2.5:3b | 13 | 61 | 64.1 | 3 | 0 |

## Reproduce

`SEED=20261120 PRESET=medium ROWS=50 make fight`. Messy file sha256 `f244b6558da5`. Team file sha256 `ae6f6df082b8`, stock `13571dac3037`.
