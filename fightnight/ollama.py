"""Talk to the Ollama that runs on the host. Only used to check and pull models."""

from __future__ import annotations

import json
import sys

import httpx


class OllamaError(RuntimeError):
    pass


def version(base_url: str) -> str:
    try:
        return httpx.get(f"{base_url}/api/version", timeout=3).json().get("version", "unknown")
    except httpx.HTTPError as e:
        raise OllamaError(
            f"Ollama is not answering at {base_url} ({e}). Start it with `ollama serve` "
            "(or open the Ollama app) and run `make fight` again."
        ) from e


def installed(base_url: str) -> set[str]:
    r = httpx.get(f"{base_url}/api/tags", timeout=10)
    r.raise_for_status()
    names = set()
    for m in r.json().get("models", []):
        names.add(m["name"])
        if m["name"].endswith(":latest"):
            names.add(m["name"].removesuffix(":latest"))
    return names


def pull(base_url: str, model: str) -> None:
    """Pull a model, printing one progress line that updates in place."""
    print(f"  pulling {model} (first time only) ...", flush=True)
    last = ""
    with httpx.stream("POST", f"{base_url}/api/pull", json={"name": model, "stream": True}, timeout=None) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            evt = json.loads(line)
            if "error" in evt:
                raise OllamaError(f"pulling {model}: {evt['error']}")
            total, done = evt.get("total"), evt.get("completed")
            if total and done:
                pct = 100 * done / total
                msg = f"  {model}: {evt.get('status','')} {pct:5.1f}% ({done/1e9:.2f}/{total/1e9:.2f} GB)"
            else:
                msg = f"  {model}: {evt.get('status','')}"
            if msg != last:
                sys.stdout.write("\r" + msg.ljust(90))
                sys.stdout.flush()
                last = msg
    sys.stdout.write("\n")


def ensure(base_url: str, models: list[str]) -> list[str]:
    have = installed(base_url)
    pulled = []
    for m in models:
        if m not in have:
            pull(base_url, m)
            pulled.append(m)
    return pulled


def sizes(base_url: str) -> dict[str, float]:
    """Model name -> size in GB, from Ollama's own listing. The pound-for-pound denominator."""
    r = httpx.get(f"{base_url}/api/tags", timeout=10)
    r.raise_for_status()
    out: dict[str, float] = {}
    for m in r.json().get("models", []):
        gb = round(m.get("size", 0) / 1e9, 2)
        out[m["name"]] = gb
        if m["name"].endswith(":latest"):
            out[m["name"].removesuffix(":latest")] = gb
    return out


def digests(base_url: str) -> dict[str, str]:
    """Model name -> Ollama digest (first 12 hex). `ollama cp` can put any weights under any
    name, so the card records what was really loaded and organizers publish the official ones."""
    r = httpx.get(f"{base_url}/api/tags", timeout=10)
    r.raise_for_status()
    out: dict[str, str] = {}
    for m in r.json().get("models", []):
        d = str(m.get("digest", ""))[:12]
        out[m["name"]] = d
        if m["name"].endswith(":latest"):
            out[m["name"].removesuffix(":latest")] = d
    return out
