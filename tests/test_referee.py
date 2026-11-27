from pathlib import Path

from fightnight.otari import ChatResult
from fightnight.referee import model_weights, warm_up
from fightnight.team import Stage, Team


def test_model_weights_strip_provider_prefix_and_ignore_hosted():
    team = Team("t", [Stage("a", "map", model="ollama:qwen2.5:3b", prompt=Path("p")), Stage("b", "map", model="llama3.2:3b", prompt=Path("p")), Stage("c", "map", model="otari-ai:openai/gpt-oss-120b", prompt=Path("p"))], Path("t.yml"), "x")
    assert model_weights(team, {"qwen2.5:3b": 1.9, "llama3.2:3b": 2.0}) == 3.9


class _FakeOtari:
    def __init__(self, fail: bool = False):
        self.calls: list[tuple[str, str]] = []
        self.fail = fail

    def chat(self, api_key, alias, messages, max_tokens, timeout):
        self.calls.append((api_key, alias))
        if self.fail:
            raise RuntimeError("down")
        return ChatResult(content="OK", prompt_tokens=1, completion_tokens=1, seconds=0.1, request_id=None, provider="ollama")


def _team(*models: str) -> Team:
    stages = [Stage(name=f"s{i}", type="map", model=m) for i, m in enumerate(models)]
    return Team(name="t", stages=stages, path=Path("team.yml"), sha256="x")


def test_warm_up_loads_each_local_model_once_on_the_given_key(capsys):
    fake = _FakeOtari()
    warm_up(fake, _team("qwen2.5:3b", "llama3.2:3b", "qwen2.5:3b", "otari-ai:openai/gpt-oss-120b"), "stock-key", 30)
    assert fake.calls == [("stock-key", "ollama:qwen2.5:3b"), ("stock-key", "ollama:llama3.2:3b")]
    assert "failed" not in capsys.readouterr().out


def test_warm_up_failure_does_not_stop_the_fight():
    warm_up(_FakeOtari(fail=True), _team("qwen2.5:3b"), "stock-key", 30)


def test_golden_is_not_on_disk_while_teams_run(tmp_path, monkeypatch):
    """A prompt or a fake model server could read data/golden.csv; it is written only after grading."""
    import fightnight.referee as ref

    monkeypatch.chdir(tmp_path)
    golden, messy, sha = ref.make_dataset(3, 10, "medium", Path("data"))
    assert (Path("data") / "messy.csv").exists()
    assert not (Path("data") / "golden.csv").exists()
    ref.write_golden(golden, Path("data"))
    assert (Path("data") / "golden.csv").exists()
