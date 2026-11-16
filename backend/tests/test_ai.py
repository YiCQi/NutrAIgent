import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db
from app.ai import agent, providers, tools
from app.main import app, get_conn, get_provider_factory


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    c.execute("INSERT INTO sources (code, name) VALUES ('test','Test')")
    c.execute("INSERT INTO foods (name, source_id, state) VALUES ('Egg, whole, raw', 1, 'raw')")
    ids = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM nutrients")}
    c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (1,?,143)", (ids["energy_kcal"],))
    c.execute("INSERT INTO portions (food_id, description, grams) VALUES (1,'1 large',50)")
    c.commit()
    return c


class Scripted(providers.Provider):
    """Replays scripted responses and records what it was sent."""
    def __init__(self, script):
        self.script, self.seen = list(script), []

    def complete(self, system, messages, tools_):
        self.seen.append(json.loads(json.dumps(messages)))
        return self.script.pop(0)


def tool_use(id_, name, **inp):
    return {"content": [{"type": "tool_use", "id": id_, "name": name, "input": inp}], "stop": "tool_use"}


def text(t):
    return {"content": [{"type": "text", "text": t}], "stop": "end"}


def test_agent_logs_via_tools_without_saving(conn):
    p = Scripted([
        tool_use("1", "search_foods", query="egg raw"),
        tool_use("2", "propose_log_entries", entries=[{"food_id": 1, "grams": 100, "meal": "breakfast"}]),
        text("Proposed 2 eggs."),
    ])
    ctx = tools.Context(conn=conn, today="2026-01-02")
    out = agent.run_chat(ctx, p, [{"role": "user", "content": "I ate an egg"}])
    assert out["reply"].startswith("Prepared 1 log entry")  # ends right after propose (no extra round trip)
    assert len(p.script) == 1
    assert out["proposals"] == [{"food_id": 1, "food_name": "Egg, whole, raw", "grams": 100.0,
                                 "meal": "breakfast", "log_date": "2026-01-02"}]
    assert conn.execute("SELECT COUNT(*) FROM intake_log").fetchone()[0] == 0  # never saved
    # tool result fed back to the model carries DB numbers
    fed = json.dumps(p.seen[1])
    assert "143" in fed and "Egg, whole, raw" in fed


def test_early_finish_uses_text_sent_with_propose(conn):
    first = {"content": [{"type": "text", "text": "Assumed 1 egg = 50 g"},
                         {"type": "tool_use", "id": "1", "name": "propose_log_entries",
                          "input": {"entries": [{"food_id": 1, "grams": 50}]}}], "stop": "tool_use"}
    out = agent.run_chat(tools.Context(conn=conn, today="2026-01-02"), Scripted([first]),
                         [{"role": "user", "content": "egg"}])
    assert out["reply"] == "Assumed 1 egg = 50 g" and len(out["proposals"]) == 1


def test_invalid_proposal_keeps_looping(conn):
    bad = tool_use("1", "propose_log_entries", entries=[{"food_id": 99, "grams": 5}])
    out = agent.run_chat(tools.Context(conn=conn, today="2026-01-02"), Scripted([bad, text("sorry")]),
                         [{"role": "user", "content": "x"}])
    assert out["reply"] == "sorry" and out["proposals"] == []


def test_stream_endpoint(client):
    fake = Scripted([tool_use("1", "get_targets"), text("done")])
    app.dependency_overrides[get_provider_factory] = lambda: (lambda cfg: fake)
    r = client.post("/api/ai/chat/stream", json={"messages": [{"role": "user", "content": "hi"}]})
    evs = [json.loads(line) for line in r.text.splitlines()]
    app.dependency_overrides.pop(get_provider_factory)
    assert [e["type"] for e in evs] == ["model", "tool", "tool_done", "model", "done"]
    assert evs[-1]["reply"] == "done"
    r = client.post("/api/ai/chat/stream", json={"messages": [{"role": "user", "content": "hi"}]})
    assert json.loads(r.text.splitlines()[0])["type"] == "error"  # no key


def test_tool_validation(conn):
    ctx = tools.Context(conn=conn, today="2026-01-02")
    r = tools.call(ctx, "propose_log_entries", {"entries": [
        {"food_id": 99, "grams": 10}, {"food_id": 1, "grams": -5}, {"food_id": 1, "grams": 10, "log_date": "x"}]})
    assert r["proposed"] == [] and len(r["errors"]) == 3
    assert tools.call(ctx, "get_targets", {}) == {"error": "profile not set"}
    assert "error" in tools.call(ctx, "get_food", {"food_id": 99})
    assert "error" in tools.call(ctx, "nope", {})
    assert "error" in tools.call(ctx, "get_daily_intake", {"date": "bad"})


def test_step_limit(conn):
    p = Scripted([tool_use(str(i), "get_targets") for i in range(agent.MAX_STEPS)])
    out = agent.run_chat(tools.Context(conn=conn, today="2026-01-02"), p, [{"role": "user", "content": "x"}])
    assert out["reply"].startswith("Stopped")


def test_openai_message_conversion():
    msgs = [{"role": "user", "content": "hi"},
            {"role": "assistant", "content": [{"type": "text", "text": "ok"},
                                              {"type": "tool_use", "id": "c1", "name": "get_targets", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "{}"}]}]
    out = providers.OpenAICompatProvider.to_openai_messages("SYS", msgs)
    assert out[0] == {"role": "system", "content": "SYS"}
    assert out[2]["tool_calls"][0]["function"] == {"name": "get_targets", "arguments": "{}"}
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": "{}"}


def test_anthropic_adapter_request_and_parse():
    seen = {}

    def handler(req):
        seen["url"], seen["key"] = str(req.url), req.headers.get("x-api-key")
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"content": [
            {"type": "text", "text": "hi"}, {"type": "tool_use", "id": "t1", "name": "get_targets", "input": {}}]})

    p = providers.make_provider(providers.ProviderConfig("anthropic", "m", "sk-test"),
                                transport=httpx.MockTransport(handler))
    r = p.complete("sys", [{"role": "user", "content": "q"}], tools.TOOL_SPECS)
    assert seen["url"] == "https://api.anthropic.com/v1/messages" and seen["key"] == "sk-test"
    assert seen["body"]["tools"][0]["input_schema"]["type"] == "object"
    assert r["stop"] == "tool_use" and r["content"][1]["name"] == "get_targets"


def test_openai_adapter_no_key_and_errors():
    def ok(req):
        assert "authorization" not in req.headers  # local servers (Ollama) need none
        return httpx.Response(200, json={"choices": [{"message": {"content": "yo"}}]})

    p = providers.make_provider(providers.ProviderConfig("openai_compatible", "m", "", "http://localhost:11434/v1"),
                                transport=httpx.MockTransport(ok))
    assert p.complete("s", [{"role": "user", "content": "q"}], [])["content"][0]["text"] == "yo"

    bad = providers.make_provider(providers.ProviderConfig("openai_compatible", "m", "sk-secret"),
                                  transport=httpx.MockTransport(lambda r: httpx.Response(401, text="nope")))
    with pytest.raises(providers.ProviderError) as e:
        bad.complete("s", [], [])
    assert "401" in str(e.value) and "sk-secret" not in str(e.value)


def test_make_provider_validation():
    with pytest.raises(providers.ProviderError):
        providers.make_provider(providers.ProviderConfig("anthropic", "m", ""))  # no key
    with pytest.raises(providers.ProviderError):
        providers.make_provider(providers.ProviderConfig("anthropic", "", "k"))  # no model


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_settings_never_return_key(client):
    r = client.put("/api/ai/settings", json={"provider": "anthropic", "model": "m", "api_key": "sk-secret"})
    assert r.json() == {"provider": "anthropic", "model": "m", "base_url": "", "has_key": True}
    assert "sk-secret" not in client.get("/api/ai/settings").text
    client.put("/api/ai/settings", json={"provider": "anthropic", "model": "m2"})  # key kept
    assert client.get("/api/ai/settings").json()["has_key"] is True
    client.put("/api/ai/settings", json={"provider": "anthropic", "model": "m2", "api_key": ""})
    assert client.get("/api/ai/settings").json()["has_key"] is False


def test_chat_endpoint(client):
    fake = Scripted([text("Hello")])
    app.dependency_overrides[get_provider_factory] = lambda: (lambda cfg: fake)
    r = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200 and r.json()["reply"] == "Hello"
    app.dependency_overrides.pop(get_provider_factory)
    r = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 502  # no key configured -> clear error
