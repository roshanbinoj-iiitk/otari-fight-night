import json
from pathlib import Path

from fightnight.otari import ChatResult
from fightnight.pipeline import Call, local_share, parse_rows, qualify_model, run_team
from fightnight.team import load_team

ROWS = [{"id": f"T{i:04d}", "date": "2026-01-0%d" % (i % 9 + 1), "vendor": "V", "amount": "1.00", "category": "dining", "note": ""} for i in range(1, 11)]
SAMPLE = ROWS[:2]


def team_from(tmp_path: Path, text: str, prompts=("p",)):
    (tmp_path / "prompts").mkdir(exist_ok=True)
    for p in prompts:
        (tmp_path / "prompts" / f"{p}.md").write_text("Clean these rows. Sample:\n{sample}\n")
    f = tmp_path / "team.yml"
    f.write_text(text)
    return load_team(f)


class FakeChat:
    """Answers with a function of (model, batch rows). Records every call."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def __call__(self, model, messages, max_tokens):
        rows = json.loads(messages[-1]["content"].split("Rows:\n", 1)[1].split("\n\nReturn", 1)[0])
        self.calls.append((model, rows))
        text = self.answer(model, rows)
        provider = model.split(":")[0]
        return ChatResult(content=text, prompt_tokens=10, completion_tokens=5, seconds=0.1, request_id=None, provider=provider, model=model)


def echo(model, rows):
    return json.dumps(rows)


def test_parse_rows_from_fence_and_prose():
    rows = [{"id": "a", "x": "1"}]
    assert parse_rows("Here you go:\n```json\n" + json.dumps(rows) + "\n```\nDone.") == rows
    assert parse_rows("sure " + json.dumps(rows)) == rows
    assert parse_rows("[1, 2] and then " + json.dumps(rows)) == rows  # last array wins
    assert parse_rows("no json here") is None
    assert parse_rows("[1, 2, 3]") is None  # not objects


def test_qualify_model():
    assert qualify_model("qwen2.5:3b") == "ollama:qwen2.5:3b"
    assert qualify_model("llama3.2") == "ollama:llama3.2"
    assert qualify_model("otari-ai:openai/gpt-4o-mini") == "otari-ai:openai/gpt-4o-mini"
    assert qualify_model("ollama:qwen2.5:3b") == "ollama:qwen2.5:3b"


def test_map_batches_and_keeps_rows_on_bad_json(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 4, prompt: prompts/p.md}\n")
    calls = []

    def answer(model, rows):
        if rows[0]["id"] == "T0005":
            return "I cannot do that"
        return json.dumps([{**r, "vendor": "Fixed"} for r in rows])

    chat = FakeChat(answer)
    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, chat, calls.append)
    assert len(chat.calls) == 3
    assert [r["vendor"] for r in out] == ["Fixed"] * 4 + ["V"] * 4 + ["Fixed"] * 2
    assert [r["id"] for r in out] == [r["id"] for r in ROWS]
    assert stats[0].requests == 3 and stats[0].unparsed == 4 and stats[0].rows == 10
    assert len(calls) == 3 and isinstance(calls[0], Call) and calls[1].unparsed == 4
    assert "sample" not in chat.calls[0][0]  # prompt rendering happened in the system message
    assert "T0001" in chat.calls[0]  [1][0]["id"]


def test_map_prompt_gets_sample_and_rows_have_no_private_keys(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")
    seen = {}

    def answer(model, rows):
        seen["keys"] = set(rows[0])
        return json.dumps(rows)

    chat = FakeChat(answer)

    class Spy(FakeChat):
        def __call__(self, model, messages, max_tokens):
            seen["system"] = messages[0]["content"]
            return super().__call__(model, messages, max_tokens)

    run_team(team, [dict(r) for r in ROWS], SAMPLE, Spy(answer), lambda c: None)
    assert "T0001" in seen["system"] and "{sample}" not in seen["system"]
    assert seen["keys"] == set(ROWS[0])


def test_map_drop_on_real_row_is_refused_and_mangled_id_row_is_left_alone(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")

    def answer(model, rows):
        out = [dict(r) for r in rows]
        out[0]["drop"] = True
        out[1]["id"] = "GARBLED"  # the other nine ids are intact, so this answer lands nowhere
        out[1]["vendor"] = "Lost"
        return json.dumps(out)

    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(answer), lambda c: None)
    assert len(out) == 10, "a real row with a unique id is never deleted on a model's say-so"
    assert stats[0].refused_drops == 1
    assert out[1]["id"] == "T0002" and out[1]["vendor"] == "V" and stats[0].unparsed == 1
    assert all("drop" not in r for r in out)


def test_map_short_reply_matches_by_id(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")

    def answer(model, rows):
        return json.dumps([{**rows[3], "vendor": "OnlyThisOne"}])

    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(answer), lambda c: None)
    assert len(out) == 10
    assert out[3]["vendor"] == "OnlyThisOne" and out[0]["vendor"] == "V"
    assert stats[0].unparsed == 9


def test_route_splits_and_merges_in_original_order(tmp_path):
    team = team_from(tmp_path, """
stages:
  - {name: triage, type: map, model: t, batch: 10, prompt: prompts/p.md}
  - {name: route, type: route, by: tag, to: {odd: oddfix, "*": other}}
  - {name: oddfix, type: map, model: o, batch: 10, prompt: prompts/p.md}
  - {name: other, type: map, model: e, batch: 10, prompt: prompts/p.md}
""")

    def answer(model, rows):
        if model.endswith(":t"):
            return json.dumps([{**r, "tag": "odd" if int(r["id"][1:]) % 2 else "even"} for r in rows])
        return json.dumps([{**r, "vendor": model.split(":")[-1]} for r in rows])

    chat = FakeChat(answer)
    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, chat, lambda c: None)
    assert [r["id"] for r in out] == [r["id"] for r in ROWS]
    assert [r["vendor"] for r in out] == ["o", "e"] * 5
    models_called = [m for m, _ in chat.calls]
    assert models_called == ["ollama:t", "ollama:o", "ollama:e"], "route targets run once, on their slice only"
    assert [s.name for s in stats] == ["triage", "oddfix", "other"]
    assert stats[1].rows == 5 and stats[2].rows == 5


def test_vote_majority_and_tie_keeps_first(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: v, type: vote, models: [a, b, c], column: category, prompt: prompts/p.md}\n")
    votes = {"a": "dining", "b": "groceries", "c": "groceries"}

    def answer(model, rows):
        return json.dumps([{**r, "category": votes[model.split(":")[-1]]} for r in rows])

    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(answer), lambda c: None)
    assert all(r["category"] == "groceries" for r in out)
    assert stats[0].requests == 3 and stats[0].model == "a, b, c"

    votes.update({"a": "dining", "b": "groceries", "c": "rent"})  # three-way tie: first model wins
    out, _ = run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(answer), lambda c: None)
    assert all(r["category"] == "dining" for r in out)


def test_verify_retries_flagged_rows_once(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: chk, type: verify, model: a, batch: 10, prompt: prompts/p.md, retry: 1}\n")
    seen_batches = []

    def answer(model, rows):
        seen_batches.append([r["id"] for r in rows])
        out = []
        for r in rows:
            r = dict(r)
            if r["id"] in ("T0002", "T0007") and len(seen_batches) == 1:
                r["flag"] = True
            else:
                r["vendor"] = "Checked"
            out.append(r)
        return json.dumps(out)

    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(answer), lambda c: None)
    assert seen_batches[1] == ["T0002", "T0007"]
    assert all(r["vendor"] == "Checked" for r in out) and all("flag" not in r for r in out)
    assert stats[0].requests == 2


def test_local_share_counts_provider(tmp_path):
    team = team_from(tmp_path, """
stages:
  - {name: a, type: map, model: qwen2.5:3b, batch: 5, prompt: prompts/p.md}
  - {name: b, type: map, model: otari-ai:openai/gpt-4o-mini, batch: 5, prompt: prompts/p.md}
""")
    calls = []
    run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(echo), calls.append)
    assert local_share(calls) == 0.5
    assert calls[0].provider == "ollama" and calls[-1].provider == "otari-ai"


def test_drop_is_only_honored_for_junk_or_duplicates(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")
    rows = [dict(r) for r in ROWS[:4]]
    rows.append(dict(ROWS[0]))  # duplicate id T0001
    rows.append({"id": "", "date": "TOTAL", "vendor": "", "amount": "9", "category": "", "note": ""})  # junk

    def answer(model, rows):
        return json.dumps([{**r, "drop": True} for r in rows])  # model wants to delete everything

    out, stats = run_team(team, rows, SAMPLE, FakeChat(answer), lambda c: None)
    ids = [r["id"] for r in out]
    assert ids == ["T0001", "T0002", "T0003", "T0004"], "junk and one duplicate removed, real rows kept"
    assert stats[0].refused_drops == 3, "only real rows count as refused; the kept duplicate copy does not"


def test_verify_drop_guard_applies_too(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: v, type: verify, model: a, batch: 10, prompt: prompts/p.md}\n")

    def answer(model, rows):
        return json.dumps([{**r, "drop": True} for r in rows])

    out, _ = run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(answer), lambda c: None)
    assert len(out) == 10


def test_vote_voters_are_independent_and_only_touch_the_column(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: v, type: vote, models: [a, b, c], column: category, prompt: prompts/p.md}\n")

    def answer(model, rows):
        m = model.split(":")[-1]
        if m == "a":
            return json.dumps([{**r, "category": "rent", "vendor": "A-wrote-this"} for r in rows])
        if m == "b":
            return "I cannot help with that"  # unparsed: must not inherit a's answer as a vote
        return json.dumps([{**r, "category": r["category"]} for r in rows])  # c echoes what it was sent

    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(answer), lambda c: None)
    # c saw the original rows (dining), not a's rewrite; b abstained; so dining 1 vs rent 1, first valid voter (a) wins ties
    assert all(r["vendor"] == "V" for r in out), "non-vote columns are never changed by voters"
    assert all(r["category"] == "rent" for r in out)


def test_vote_abstentions_do_not_count(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: v, type: vote, models: [a, b, c], column: category, prompt: prompts/p.md}\n")

    def answer(model, rows):
        m = model.split(":")[-1]
        if m == "a":
            return json.dumps([{**r, "category": "rent"} for r in rows])
        return json.dumps([{**r, "category": "groceries"} for r in rows])

    out, _ = run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(answer), lambda c: None)
    assert all(r["category"] == "groceries" for r in out)


def test_duplicates_split_across_route_slices_are_still_deduped(tmp_path):
    team = team_from(tmp_path, """
stages:
  - {name: triage, type: map, model: t, batch: 20, prompt: prompts/p.md}
  - {name: route, type: route, by: tag, to: {x: fixx, "*": other}}
  - {name: fixx, type: map, model: o, batch: 20, prompt: prompts/p.md}
  - {name: other, type: map, model: e, batch: 20, prompt: prompts/p.md}
""")
    rows = [dict(r) for r in ROWS[:4]] + [dict(ROWS[0])]  # T0001 twice

    def answer(model, rows):
        if model.endswith(":t"):
            # the two copies of T0001 get different tags
            return json.dumps([{**r, "tag": "x" if i == 0 else "y"} for i, r in enumerate(rows)])
        return json.dumps([{**r, "drop": r["id"] == "T0001"} for r in rows])  # both slices flag their copy

    out, stats = run_team(team, rows, SAMPLE, FakeChat(answer), lambda c: None)
    assert sorted(r["id"] for r in out) == ["T0001", "T0002", "T0003", "T0004"], "exactly one copy of T0001 survives"
    assert sum(s.refused_drops for s in stats) == 0


def test_reordered_reply_with_intact_ids_matches_by_id(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")

    def answer(model, rows):
        return json.dumps([{**r, "vendor": "fixed-" + r["id"]} for r in reversed(rows)])

    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(answer), lambda c: None)
    assert [r["vendor"] for r in out] == ["fixed-" + r["id"] for r in ROWS]
    assert stats[0].unparsed == 0


def test_transport_error_keeps_rows_and_counts_failed_request(tmp_path):
    import httpx

    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 5, prompt: prompts/p.md}\n")
    n = [0]

    def chat(model, messages, max_tokens):
        n[0] += 1
        if n[0] == 1:
            raise httpx.ReadTimeout("slow")
        return ChatResult(json.dumps(json.loads(messages[-1]["content"].split("Rows:\n", 1)[1].split("\n\nReturn", 1)[0])), 1, 1, 0.1, None, "ollama", model)

    calls = []
    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, chat, calls.append)
    assert len(out) == 10
    assert stats[0].unparsed == 5 and stats[0].failed_requests == 1 and stats[0].requests == 2
    assert calls[0].error.startswith("ReadTimeout")


def test_failed_request_records_elapsed_time_and_unknown_provider(tmp_path, monkeypatch):
    import httpx
    from fightnight import pipeline

    ticks = iter([10.0, 12.5])
    monkeypatch.setattr(pipeline.time, "perf_counter", lambda: next(ticks))
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")

    def timeout(*args):
        raise httpx.ReadTimeout("slow")

    calls = []
    _, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, timeout, calls.append)
    assert calls[0].seconds == stats[0].seconds == 2.5
    assert calls[0].provider == "unknown"
    assert stats[0].provider_requests == {"unknown": 1}
    assert local_share(calls) == 1.0  # nothing was served, so nothing was served remotely


def test_empty_input_runs_without_error(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 5, prompt: prompts/p.md}\n  - {name: v, type: verify, model: a, batch: 5, prompt: prompts/p.md}\n")
    out, stats = run_team(team, [], SAMPLE, FakeChat(echo), lambda c: None)
    assert out == [] and [s.requests for s in stats] == [0, 0]


def test_parse_single_object_reply():
    assert parse_rows('{"id": "a", "x": "1"}') == [{"id": "a", "x": "1"}]


def test_route_target_that_is_a_route_is_rejected(tmp_path):
    import pytest

    from fightnight.team import TeamError

    with pytest.raises(TeamError, match="route"):
        team_from(tmp_path, """
stages:
  - {name: r1, type: route, by: tag, to: {"*": r2}}
  - {name: r2, type: route, by: tag, to: {"*": m}}
  - {name: m, type: map, model: a, batch: 5, prompt: prompts/p.md}
""")


def test_route_without_catch_all_passes_unmatched_rows_through(tmp_path):
    team = team_from(tmp_path, """
stages:
  - {name: triage, type: map, model: t, batch: 10, prompt: prompts/p.md}
  - {name: route, type: route, by: tag, to: {bad: fix}}
  - {name: fix, type: map, model: f, batch: 10, prompt: prompts/p.md}
""")

    def answer(model, rows):
        if model.endswith(":t"):
            return json.dumps([{**r, "tag": "bad" if i % 2 else "ok"} for i, r in enumerate(rows)])
        return json.dumps([{**r, "vendor": "fixed"} for r in rows])

    chat = FakeChat(answer)
    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, chat, lambda c: None)
    assert [r["vendor"] for r in out] == ["V", "fixed"] * 5
    assert [m for m, _ in chat.calls] == ["ollama:t", "ollama:f"]
    assert stats[1].rows == 5


def test_missing_provider_header_is_unknown_not_local(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")

    def chat(model, messages, max_tokens):
        return ChatResult("[]", 1, 1, 0.1, None, "", "")  # no otari-provider header

    calls = []
    run_team(team, [dict(r) for r in ROWS], SAMPLE, chat, calls.append)
    assert calls[0].provider == "unknown" and local_share(calls) == 0.0


def test_truncated_array_salvages_complete_rows():
    text = '[{"id": "a", "x": "1"}, {"id": "b", "x": "2"}, {"id": "c", "x'
    assert parse_rows(text) == [{"id": "a", "x": "1"}, {"id": "b", "x": "2"}]


def test_user_message_asks_for_string_values(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")
    seen = {}

    def chat(model, messages, max_tokens):
        seen["user"] = messages[-1]["content"]
        return ChatResult("[]", 1, 1, 0.1, None, "ollama", model)

    run_team(team, [dict(r) for r in ROWS], SAMPLE, chat, lambda c: None)
    assert "every value as a string" in seen["user"]


def test_same_count_but_substituted_row_never_contaminates_neighbors(tmp_path):
    """A model drops one real row and emits a junk row in its place: same count, so position
    matching would smear the junk onto a real id. Ids that overlap must win."""
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")

    def answer(model, rows):
        out = [{**r, "vendor": "Fixed"} for r in rows]
        out[3] = {"id": "", "date": "", "vendor": "TOTAL", "amount": "999", "category": "", "note": ""}
        return json.dumps(out[::-1])  # reordered too

    out, stats = run_team(team, [dict(r) for r in ROWS], SAMPLE, FakeChat(answer), lambda c: None)
    assert [r["id"] for r in out] == [r["id"] for r in ROWS]
    assert out[3]["vendor"] == "V" and all(r["vendor"] == "Fixed" for i, r in enumerate(out) if i != 3)
    assert stats[0].unparsed == 1
    assert not any(r["vendor"] == "TOTAL" for r in out)


def test_junk_rows_match_junk_rows_in_order(tmp_path):
    team = team_from(tmp_path, "stages:\n  - {name: m, type: map, model: a, batch: 10, prompt: prompts/p.md}\n")
    rows = [dict(ROWS[0]), {"id": "", "date": "", "vendor": "TOTAL", "amount": "1", "category": "", "note": ""}, dict(ROWS[1]), {"id": "", "date": "x", "vendor": "x", "amount": "x", "category": "x", "note": "x"}]

    def answer(model, rows):
        out = []
        for r in rows:
            r = dict(r)
            if r["id"] == "":
                r["drop"] = True
            else:
                r["vendor"] = "Fixed"
            out.append(r)
        return json.dumps(out)

    out, stats = run_team(team, rows, SAMPLE, FakeChat(answer), lambda c: None)
    assert [r["id"] for r in out] == ["T0001", "T0002"] and all(r["vendor"] == "Fixed" for r in out)
    assert stats[0].unparsed == 0


def test_local_share_leaves_out_failures_but_not_missing_headers():
    def call(provider, error=""):
        return Call("s", "m", provider, 1, 1, 0.1, 0, 0, 0, error)

    assert local_share([call("ollama"), call("unknown", "ReadTimeout")]) == 1.0
    assert local_share([call("ollama"), call("unknown")]) == 0.5  # answered without Otari's header: no credit
    assert local_share([call("ollama"), call("otari-ai")]) == 0.5
