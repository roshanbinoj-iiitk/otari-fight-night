"""team.yml: the one file an entrant edits. Roles, models, batch sizes, prompts, and how rows flow."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

STAGE_TYPES = ("map", "route", "vote", "verify")
KNOWN_KEYS = {"name", "type", "model", "models", "batch", "prompt", "by", "to", "column", "retry"}


class TeamError(ValueError):
    pass


@dataclass
class Stage:
    name: str
    type: str
    model: str | None = None
    models: list[str] = field(default_factory=list)
    batch: int = 10
    prompt: Path | None = None
    by: str | None = None
    to: dict[str, str] = field(default_factory=dict)
    column: str | None = None
    retry: int = 0

    def all_models(self) -> list[str]:
        return [self.model] if self.model else list(self.models)


@dataclass
class Team:
    name: str
    stages: list[Stage]
    path: Path
    sha256: str  # over the yml text and every prompt file it references, so a card ties to exact prompts

    def models(self) -> list[str]:
        seen: list[str] = []
        for s in self.stages:
            for m in s.all_models():
                if m not in seen:
                    seen.append(m)
        return seen

    def stage(self, name: str) -> Stage:
        return next(s for s in self.stages if s.name == name)


def _int(stage_name: str, raw: dict, key: str, default: int) -> int:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        try:
            return int(str(value))
        except ValueError:
            raise TeamError(f"stage '{stage_name}': '{key}' must be a whole number, got {value!r}") from None
    return value


def _need(stage_name: str, raw: dict, key: str):
    if key not in raw or raw[key] in (None, "", []):
        raise TeamError(f"stage '{stage_name}' needs '{key}'")
    return raw[key]


def load_team(path: Path) -> Team:
    path = Path(path)
    text = path.read_text()
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise TeamError(f"{path}: not valid YAML: {e}") from e
    if not isinstance(doc, dict) or not isinstance(doc.get("stages"), list) or not doc["stages"]:
        raise TeamError(f"{path}: needs a 'stages' list")
    base = path.parent
    stages: list[Stage] = []
    for raw in doc["stages"]:
        if not isinstance(raw, dict):
            raise TeamError(f"{path}: every stage must be a mapping")
        name = str(raw.get("name") or f"stage{len(stages) + 1}")
        if any(s.name == name for s in stages):
            raise TeamError(f"stage '{name}' is defined twice")
        kind = str(raw.get("type", ""))
        if kind not in STAGE_TYPES:
            raise TeamError(f"stage '{name}' has unknown type '{kind}'; use one of {', '.join(STAGE_TYPES)}")
        unknown = set(raw) - KNOWN_KEYS
        if unknown:
            raise TeamError(f"stage '{name}' has unknown key(s) {', '.join(sorted(unknown))}; allowed: {', '.join(sorted(KNOWN_KEYS))}")
        st = Stage(name=name, type=kind, batch=_int(name, raw, "batch", 10), retry=_int(name, raw, "retry", 0))
        if kind in ("map", "verify"):
            st.model = str(_need(name, raw, "model"))
        if kind == "vote":
            models = _need(name, raw, "models")
            if not isinstance(models, list):
                raise TeamError(f"stage '{name}': 'models' must be a list, like [qwen2.5:3b, llama3.2:3b]")
            st.models = [str(m) for m in models]
            st.column = str(_need(name, raw, "column"))
        if kind in ("map", "vote", "verify"):
            prompt = (base / str(_need(name, raw, "prompt"))).resolve()
            if prompt.suffix.lower() not in (".md", ".txt"):
                raise TeamError(f"stage '{name}': prompt must be a .md or .txt file, not {prompt.name} (a prompt goes into the system message verbatim)")
            if "data" in prompt.parts:
                raise TeamError(f"stage '{name}': prompt cannot live under data/")
            if not prompt.exists():
                raise TeamError(f"stage '{name}': prompt file {prompt.name} not found at {prompt}")
            st.prompt = prompt
        for m in st.all_models():
            if "cloud" in m.lower():
                raise TeamError(f"stage '{name}': model '{m}' looks like an Ollama cloud model; those run remotely and are not allowed")
        if kind == "route":
            st.by = str(_need(name, raw, "by"))
            to = _need(name, raw, "to")
            if not isinstance(to, dict):
                raise TeamError(f"stage '{name}': 'to' must map values to stage names")
            st.to = {str(k): str(v) for k, v in to.items()}
        if st.batch < 1:
            raise TeamError(f"stage '{name}': batch must be at least 1")
        stages.append(st)
    by_name = {s.name: s for s in stages}
    for s in stages:
        if s.type == "route":
            for value, target in s.to.items():
                if target not in by_name:
                    raise TeamError(f"stage '{s.name}' routes '{value}' to '{target}', which is not a stage")
                if by_name[target].type == "route":
                    raise TeamError(f"stage '{s.name}' routes '{value}' to '{target}', which is itself a route; route targets must be map, vote or verify stages")
    digest = hashlib.sha256(text.encode())
    for st in stages:
        if st.prompt is not None:
            digest.update(b"\0" + str(st.prompt.name).encode() + b"\0" + st.prompt.read_bytes())
    return Team(name=str(doc.get("name") or path.stem), stages=stages, path=path, sha256=digest.hexdigest()[:12])
