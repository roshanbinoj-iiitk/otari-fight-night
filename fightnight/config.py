"""Settings come from .env (created by `make fight` on first run) and the environment."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

ENV_PATH = Path(".env")
EXAMPLE_PATH = Path(".env.example")


def read_env_file(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def new_otari_key() -> str:
    """Otari API keys are 'tk-' plus at least 47 url-safe characters."""
    return "tk-" + secrets.token_urlsafe(48)


def init_env(example: Path = EXAMPLE_PATH, target: Path = ENV_PATH) -> bool:
    """Write .env from .env.example with fresh keys. Returns False if .env already exists."""
    if target.exists():
        return False
    text = example.read_text()
    text = text.replace("OTARI_MASTER_KEY=__GENERATED__", f"OTARI_MASTER_KEY=sk-otari-admin-{secrets.token_urlsafe(24)}")
    text = text.replace("TEAM_KEY=__GENERATED__", f"TEAM_KEY={new_otari_key()}")
    text = text.replace("STOCK_KEY=__GENERATED__", f"STOCK_KEY={new_otari_key()}")
    target.write_text(text)
    return True


class ConfigError(ValueError):
    pass


def _int(env: dict, name: str, default: str) -> int:
    raw = env.get(name, default) or default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r} (check .env or your shell)") from None


@dataclass
class Settings:
    master_key: str
    key_team: str
    key_stock: str
    otari_ai_key: str
    otari_url: str
    ollama_url: str
    team_path: Path
    stock_path: Path
    rows: int
    preset: str
    seed: int | None
    timeout_seconds: float

    @classmethod
    def load(cls) -> "Settings":
        env = {**read_env_file(), **os.environ}

        def get(name: str, default: str = "") -> str:
            return env.get(name, default) or default

        from .corrupt import PRESETS

        preset = get("PRESET", "medium")
        if preset not in PRESETS:
            raise ConfigError(f"PRESET must be one of {', '.join(PRESETS)}, got {preset!r}")
        seed_raw = get("SEED")
        return cls(
            master_key=get("OTARI_MASTER_KEY"),
            key_team=get("TEAM_KEY"),
            key_stock=get("STOCK_KEY"),
            otari_ai_key=get("OTARI_AI_KEY"),
            otari_url=get("OTARI_URL", "http://localhost:8000").rstrip("/"),
            ollama_url=get("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
            team_path=Path(get("TEAM", "team.yml")),
            stock_path=Path("teams/stock.yml"),  # fixed on purpose: the baseline is not a knob
            rows=_int(env, "ROWS", "50"),
            preset=preset,
            seed=_int(env, "SEED", "0") if seed_raw else None,
            timeout_seconds=float(_int(env, "TIMEOUT_SECONDS", "120")),
        )
