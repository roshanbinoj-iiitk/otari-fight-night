"""Everything the referee says to Otari. Chat goes through the fighters' scoped keys;
roster setup and nothing else uses the admin key."""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx


@dataclass
class ChatResult:
    content: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    request_id: str | None
    provider: str = ""  # from the otari-provider header: who actually served it
    model: str = ""  # from the otari-model header


class OtariError(RuntimeError):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class Otari:
    def __init__(self, base_url: str, master_key: str = "", timeout: float = 60.0):
        self.base_url = base_url
        self.master_key = master_key
        self.http = httpx.Client(timeout=timeout)

    def _admin(self) -> dict[str, str]:
        if not self.master_key:
            raise OtariError("OTARI_MASTER_KEY is empty; the referee needs it to switch models on.")
        return {"Authorization": f"Bearer {self.master_key}"}

    def wait_healthy(self, seconds: float = 60.0) -> dict:
        deadline = time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            try:
                r = self.http.get(f"{self.base_url}/api/v1/health", timeout=3)
                if r.status_code == 200:
                    return r.json()
                last = f"HTTP {r.status_code}"
            except httpx.HTTPError as e:
                last = str(e)
            time.sleep(1)
        raise OtariError(f"Otari at {self.base_url} did not answer within {seconds:.0f}s ({last}). Is `docker compose up -d` running?")

    def version(self) -> str:
        """Otari prints its version in the compose logs; the API does not expose it. Best effort from headers."""
        try:
            r = self.http.get(f"{self.base_url}/api/v1/health", timeout=3)
            return r.headers.get("x-otari-version") or r.headers.get("server", "") or "unknown"
        except httpx.HTTPError:
            return "unknown"

    def ensure_models(self, provider: str, models: list[str]) -> list[str]:
        """Make sure each model is offered and switched on under the hosted provider, at $0.

        A hosted provider declared in otari.yml starts with an empty roster, so a
        request would get 424 until someone switches the model on. This is that someone.
        Returns a list of one-line notes about what it did.
        """
        notes = []
        h = self._admin()
        r = self.http.post(f"{self.base_url}/api/v1/hosted-providers/{provider}/models/refresh", headers=h, json={})
        if r.status_code >= 400:
            raise OtariError(f"refreshing {provider} models failed: HTTP {r.status_code} {r.text[:200]}")
        refreshed = r.json()
        if refreshed.get("error"):
            raise OtariError(f"Otari could not reach Ollama through the '{provider}' provider: {refreshed['error']}")
        if refreshed.get("added"):
            notes.append(f"Otari discovered {', '.join(refreshed['added'])} on {provider}")

        roster = {m["model"]: m for m in self._roster(provider)}
        zero = {"input_price_per_million": 0, "output_price_per_million": 0}
        for model in models:
            entry = roster.get(model)
            if entry is None:
                r = self.http.post(f"{self.base_url}/api/v1/hosted-providers/{provider}/models", headers=h, json={"model": model, **zero})
                if r.status_code >= 400:
                    raise OtariError(f"adding {model} to {provider} failed: HTTP {r.status_code} {r.text[:200]}")
                entry = r.json()
                notes.append(f"added {model} to the {provider} roster")
            if not entry.get("enabled") or entry.get("input_price_per_million") is None:
                r = self.http.patch(
                    f"{self.base_url}/api/v1/hosted-providers/{provider}/models/{entry['id']}",
                    headers=h,
                    json={"enabled": True, **zero},
                )
                if r.status_code >= 400:
                    raise OtariError(f"switching on {model} failed: HTTP {r.status_code} {r.text[:200]}")
                notes.append(f"switched on {model} at $0")
        return notes

    def ensure_otari_ai(self, api_key: str) -> str:
        """Store otari.ai as a hosted provider named 'otari-ai' so a team can point a stage at
        `otari-ai:<vendor>/<model>`. Returns a one-line note."""
        h = self._admin()
        try:
            r = self.http.get(f"{self.base_url}/api/v1/hosted-providers", headers=h)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OtariError(f"listing hosted providers failed: {e}") from e
        existing = next((p for p in r.json().get("data", []) if p["name"] == "otari-ai"), None)
        body = {"name": "otari-ai", "provider": "otari", "api_key": api_key}
        if existing is None:
            r = self.http.post(f"{self.base_url}/api/v1/hosted-providers", headers=h, json=body)
            if r.status_code >= 400:
                raise OtariError(f"adding the otari-ai provider failed: HTTP {r.status_code} {r.text[:200]}")
            r = self.http.post(f"{self.base_url}/api/v1/hosted-providers/otari-ai/models/refresh", headers=h, json={})
            n = len(r.json().get("added", [])) if r.status_code < 400 else 0
            return f"connected otari.ai as hosted provider otari-ai ({n} models listed)"
        r = self.http.patch(f"{self.base_url}/api/v1/hosted-providers/otari-ai", headers=h, json={"api_key": api_key})
        if r.status_code >= 400 and r.status_code != 409:
            raise OtariError(f"updating the otari-ai key failed: HTTP {r.status_code} {r.text[:200]}")
        return "otari.ai connected as hosted provider otari-ai"

    def _roster(self, provider: str) -> list[dict]:
        r = self.http.get(f"{self.base_url}/api/v1/hosted-providers/{provider}/models", headers=self._admin())
        r.raise_for_status()
        return r.json()["data"]

    def chat(self, api_key: str, alias: str, messages: list[dict], max_tokens: int, timeout: float) -> ChatResult:
        body = {"model": alias, "messages": messages, "max_tokens": max_tokens, "temperature": 0.1}
        t0 = time.perf_counter()
        r = self.http.post(
            f"{self.base_url}/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
            timeout=timeout,
        )
        seconds = time.perf_counter() - t0
        if r.status_code >= 400:
            detail = r.text[:300]
            raise OtariError(f"HTTP {r.status_code} from Otari for '{alias}': {detail}", r.status_code)
        data = r.json()
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""
        usage = data.get("usage") or {}
        return ChatResult(
            content=content,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            seconds=seconds,
            request_id=r.headers.get("otari-request-id"),
            provider=r.headers.get("otari-provider", ""),
            model=r.headers.get("otari-model", ""),
        )

    def key_usage(self, api_key: str, start_iso: str) -> dict:
        """What Otari logged for one team key since the run began. Empty dict if the gateway cannot say."""
        try:
            r = self.http.get(
                f"{self.base_url}/api/v1/key/usage/summary",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"start_date": start_iso, "dimensions": "model"},
            )
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError):
            return {}
