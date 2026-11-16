import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db
from app.ai import agent, nllog, providers, tools
from app.main import app, get_conn, get_provider_factory


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    c.execute("INSERT INTO sources (code, name) VALUES ('test','Test')")
    c.execute("INSERT INTO foods (name, source_id, state) VALUES ('Egg, whole, raw', 1, 'raw')")
    c.execute("INSERT INTO foods (name, source_id, state) VALUES ('Rice, white, cooked', 1, 'cooked')")
    c.execute("INSERT INTO foods (name, source_id, state) VALUES ('Rice, white, raw', 1, 'raw')")
    ids = {r["code"]: r["id"] for r in c.execute("SELECT id, code FROM nutrients")}
    c.execute("INSERT INTO food_nutrients (food_id, nutrient_id, value_per_100g) VALUES (1,?,143)", (ids["energy_kcal"],))
    c.execute("INSERT INTO portions (food_id, description, grams) VALUES (1,'1 large',50)")
    c.execute("INSERT INTO portions (food_id, description, grams) VALUES (2,'1 cup',186)")
    c.execute("INSERT INTO portions (food_id, description, grams) VALUES (2,'2 tablespoon',30)")
    c.commit()
    return c


class Scripted(providers.Provider):
    """Replays scripted responses and records what it was sent."""
    def __init__(self, script):
        self.script, self.seen = list(script), []

    def complete(self, system, messages, tools_):
        self.seen.append((system, json.loads(json.dumps(messages)), tools_))
        return self.script.pop(0)


def tool_use(id_, name, **inp):
    return {"content": [{"type": "tool_use", "id": id_, "name": name, "input": inp}], "stop": "tool_use"}


def text(t):
    return {"content": [{"type": "text", "text": t}], "stop": "end"}


PARSED = {"intent": "log", "items": [
    {"label": "鸡蛋", "search_terms": ["egg whole raw"], "state": "raw", "quantity": 2, "unit": "piece",
     "grams_estimate": 100, "meal": "breakfast", "date": None},
    {"label": "米饭", "search_terms": ["rice white cooked", "rice"], "state": "cooked", "quantity": 1,
     "unit": "bowl", "grams_estimate": 200, "meal": "breakfast", "date": None},
    {"label": "mystery", "search_terms": ["zzzz nothing"], "quantity": None, "unit": None,
     "grams_estimate": None, "meal": "x", "date": "bad-date"}]}


# ------------------------------------------------------------------ parsing + matching
def test_parse_extracts_json_and_falls_back():
    p = Scripted([text("Sure!\n```json\n" + json.dumps(PARSED) + "\n```")])
    assert nllog.parse(p, [{"role": "user", "content": "x"}], "2026-01-02")["intent"] == "log"
    assert p.seen[0][2] == []  # no tools sent: single plain call
    assert nllog.parse(Scripted([text("not json")]), [{"role": "user", "content": "x"}], "d") == {"intent": "chat"}
    assert nllog.parse(Scripted([text('{"intent":"chat"}')]), [{"role": "user", "content": "x"}], "d") == {"intent": "chat"}


def test_build_proposals_deterministic(conn):
    events = list(nllog.build_proposals(conn, PARSED, "2026-01-02"))
    assert [e[0] for e in events] == ["match", "match", "match", "done"]
    egg, rice, none = events[-1][1]
    assert egg["food_name"] == "Egg, whole, raw" and egg["grams"] == 100.0  # 2 x '1 large' (50 g) from DB portion
    assert "database portion" in egg["grams_basis"]
    assert rice["food_name"] == "Rice, white, cooked" and rice["grams"] == 186.0  # bowl ~ cup portion
    assert [a["food_name"] for a in rice["alternatives"]][0] == "Rice, white, cooked"  # state preferred
    assert none["food_id"] is None and none["meal"] == "other" and none["log_date"] == "2026-01-02"
    assert egg["meal"] == "breakfast" and egg["log_date"] == "2026-01-02"


def test_resolve_grams_rules(conn):
    r = nllog.resolve_grams
    assert r(conn, 1, 150, "g", None)[0] == 150
    assert r(conn, 1, 200, "ml", None)[0] == 200
    assert r(conn, 1, None, None, 80) == (80.0, "typical weight estimated by the AI (please check)")
    assert r(conn, 1, None, None, None)[0] == 100.0
    assert r(conn, 2, 2, "tbsp", None)[0] == 30.0  # '2 tablespoon' = 30 g -> 2 tbsp = 30 g


def test_progressive_term_fallback(conn):
    # first term has no match; shortened version 'rice white' does
    events = list(nllog.build_proposals(conn, {"items": [{"label": "r", "search_terms": ["rice white zzz"]}]}, "d"))
    assert events[-1][1][0]["food_id"] is not None


# ------------------------------------------------------------------ agent (questions)
def test_agent_answers_with_tools(conn):
    p = Scripted([tool_use("1", "get_food", food_id=1), text("It has 143 kcal per 100 g.")])
    out = list(agent.iter_chat(tools.Context(conn=conn, today="2026-01-02"), p, [{"role": "user", "content": "egg?"}]))
    assert out[-1]["reply"].startswith("It has 143") and out[-1]["trace"][0]["tool"] == "get_food"
    assert "143" in json.dumps(p.seen[1][1])  # DB numbers fed back to the model


def test_tool_validation(conn):
    ctx = tools.Context(conn=conn, today="2026-01-02")
    assert tools.call(ctx, "get_targets", {}) == {"error": "profile not set"}
    assert "error" in tools.call(ctx, "get_food", {"food_id": 99})
    assert "error" in tools.call(ctx, "propose_log_entries", {})  # removed tool
    assert "error" in tools.call(ctx, "get_daily_intake", {"date": "bad"})
    assert tools.call(ctx, "search_foods", {"query": "egg"})["results"][0]["portions"][0]["grams"] == 50


def test_step_limit(conn):
    p = Scripted([tool_use(str(i), "get_targets") for i in range(agent.MAX_STEPS)])
    out = list(agent.iter_chat(tools.Context(conn=conn, today="d"), p, [{"role": "user", "content": "x"}]))
    assert out[-1]["reply"].startswith("Stopped")


# ------------------------------------------------------------------ providers
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
    p.complete("sys", [{"role": "user", "content": "q"}], [])
    assert "tools" not in seen["body"]


def test_openai_adapter_no_key_empty_tools_and_errors():
    seen = {}

    def ok(req):
        seen["body"] = json.loads(req.content)
        assert "authorization" not in req.headers  # local servers (Ollama) need none
        return httpx.Response(200, json={"choices": [{"message": {"content": "yo"}}]})

    p = providers.make_provider(providers.ProviderConfig("openai_compatible", "m", "", "http://localhost:11434/v1"),
                                transport=httpx.MockTransport(ok))
    assert p.complete("s", [{"role": "user", "content": "q"}], [])["content"][0]["text"] == "yo"
    assert "tools" not in seen["body"]  # some servers reject an empty array

    bad = providers.make_provider(providers.ProviderConfig("openai_compatible", "m", "sk-secret"),
                                  transport=httpx.MockTransport(lambda r: httpx.Response(401, text="nope")))
    with pytest.raises(providers.ProviderError) as e:
        bad.complete("s", [], [])
    assert "401" in str(e.value) and "sk-secret" not in str(e.value)


def test_make_provider_validation():
    with pytest.raises(providers.ProviderError):
        providers.make_provider(providers.ProviderConfig("anthropic", "m", ""))
    with pytest.raises(providers.ProviderError):
        providers.make_provider(providers.ProviderConfig("anthropic", "", "k"))


# ------------------------------------------------------------------ API: settings + sessions
@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def events(resp):
    return [json.loads(line) for line in resp.text.splitlines() if line]


def test_settings_never_return_key(client):
    r = client.put("/api/ai/settings", json={"provider": "anthropic", "model": "m", "api_key": "sk-secret"})
    assert r.json() == {"provider": "anthropic", "model": "m", "base_url": "", "has_key": True}
    assert "sk-secret" not in client.get("/api/ai/settings").text
    client.put("/api/ai/settings", json={"provider": "anthropic", "model": "m2"})
    assert client.get("/api/ai/settings").json()["has_key"] is True
    client.put("/api/ai/settings", json={"provider": "anthropic", "model": "m2", "api_key": ""})
    assert client.get("/api/ai/settings").json()["has_key"] is False


def test_sessions_persist_and_log_flow(client, conn):
    cid = client.post("/api/conversations").json()["id"]
    fake = Scripted([text(json.dumps(PARSED))])
    app.dependency_overrides[get_provider_factory] = lambda: (lambda cfg: fake)
    r = client.post(f"/api/conversations/{cid}/chat", json={"content": "我吃了两个鸡蛋和一碗米饭"})
    app.dependency_overrides.pop(get_provider_factory)
    evs = events(r)
    assert evs[0]["type"] == "status" and evs[-1]["type"] == "done" and len(fake.script) == 0  # ONE model call
    msg = evs[-1]["message"]
    assert msg["content"].startswith("Recognised 3 items")
    assert msg["role"] == "assistant" and msg["meta"]["status"] == "pending" and len(msg["meta"]["proposals"]) == 3
    assert conn.execute("SELECT COUNT(*) FROM intake_log").fetchone()[0] == 0  # nothing saved by the AI

    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["title"].startswith("我吃了两个鸡蛋")
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert client.get("/api/conversations").json()[0]["id"] == cid

    assert client.patch(f"/api/messages/{msg['id']}/status", json={"status": "saved"}).status_code == 200
    again = client.get(f"/api/conversations/{cid}").json()["messages"][1]
    assert again["meta"]["status"] == "saved" and len(again["meta"]["proposals"]) == 3

    assert client.delete(f"/api/conversations/{cid}").status_code == 204
    assert client.get(f"/api/conversations/{cid}").status_code == 404
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0  # cascade


def test_chat_intent_uses_tool_agent_with_history(client):
    cid = client.post("/api/conversations").json()["id"]
    fake = Scripted([text('{"intent":"chat"}'), text("Protein builds muscle."),
                     text('{"intent":"chat"}'), text("Yes, again.")])
    app.dependency_overrides[get_provider_factory] = lambda: (lambda cfg: fake)
    client.post(f"/api/conversations/{cid}/chat", json={"content": "what is protein?"})
    r = client.post(f"/api/conversations/{cid}/chat", json={"content": "and again?"})
    app.dependency_overrides.pop(get_provider_factory)
    assert events(r)[-1]["message"]["content"] == "Yes, again."
    sent = fake.seen[2][1]  # second turn's parse call carries earlier turns
    assert [m["content"] for m in sent][:3] == ["what is protein?", "Protein builds muscle.", "and again?"]


def test_chat_errors(client):
    cid = client.post("/api/conversations").json()["id"]
    r = client.post(f"/api/conversations/{cid}/chat", json={"content": "hi"})  # no key configured
    assert events(r)[0] == {"type": "error", "message": "model not set"}
    assert client.post("/api/conversations/999/chat", json={"content": "hi"}).status_code == 404
