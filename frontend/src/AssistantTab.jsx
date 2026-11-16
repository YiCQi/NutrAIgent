import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import ChatPane from "./ChatPane.jsx";

const HINT = {
  anthropic: { model: "e.g. claude-sonnet-5-5", url: "optional (default https://api.anthropic.com)" },
  openai_compatible: { model: "model name from your provider", url: "e.g. https://api.openai.com/v1 or http://localhost:11434/v1 (Ollama)" },
};

function Settings({ onChange }) {
  const [s, setS] = useState({ provider: "anthropic", model: "", base_url: "", has_key: false });
  const [key, setKey] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => { api.getAISettings().then((x) => { setS(x); onChange?.(x); }).catch((e) => setErr(e.message)); }, []);

  const save = async (e) => {
    e.preventDefault(); setErr(""); setMsg("");
    try {
      const x = await api.putAISettings({ provider: s.provider, model: s.model, base_url: s.base_url, api_key: key === "" ? null : key });
      setS(x); setKey(""); setMsg("Saved."); onChange?.(x);
    } catch (e2) { setErr(e2.message); }
  };
  const clearKey = async () => {
    const x = await api.putAISettings({ provider: s.provider, model: s.model, base_url: s.base_url, api_key: "" });
    setS(x); onChange?.(x); setMsg("Key removed.");
  };

  return (
    <details open={!s.has_key || !s.model}>
      <summary>AI provider settings (bring your own key)</summary>
      <form onSubmit={save} className="grid">
        <label>Provider
          <select value={s.provider} onChange={(e) => setS({ ...s, provider: e.target.value })}>
            <option value="anthropic">Anthropic</option>
            <option value="openai_compatible">OpenAI-compatible</option>
          </select>
        </label>
        <label>Model<input value={s.model} placeholder={HINT[s.provider].model} onChange={(e) => setS({ ...s, model: e.target.value })} /></label>
        <label className="wide">Base URL<input value={s.base_url} placeholder={HINT[s.provider].url} onChange={(e) => setS({ ...s, base_url: e.target.value })} /></label>
        <label className="wide">API key {s.has_key && <small>(a key is saved; leave blank to keep it)</small>}
          <input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder={s.has_key ? "••••••••" : "paste key"} />
        </label>
        <button type="submit">Save</button>
        {s.has_key && <button type="button" onClick={clearKey}>Remove key</button>}
      </form>
      <p className="muted">
        The key is stored only in your local database file and sent only to the provider above. Your chat messages and the
        food/intake data the assistant looks up are sent to that provider. Nothing else leaves this machine.
      </p>
      {msg && <p className="ok">{msg}</p>}
      {err && <p className="err">{err}</p>}
    </details>
  );
}

export default function AssistantTab({ onLogged }) {
  const [cfg, setCfg] = useState(null);
  const [convs, setConvs] = useState([]);
  const [active, setActive] = useState(null);
  const [err, setErr] = useState("");

  const refresh = async (selectId) => {
    const list = await api.listConvs();
    setConvs(list);
    if (selectId !== undefined) setActive(selectId);
    return list;
  };

  useEffect(() => {
    refresh().then(async (list) => {
      if (list.length) setActive(list[0].id);
      else { const c = await api.createConv(); await refresh(c.id); }
    }).catch((e) => setErr(e.message));
  }, []);

  const newChat = async () => {
    const empty = convs.find((c) => c.title === "New chat");  // reuse an unused empty chat
    if (empty) { setActive(empty.id); return; }
    const c = await api.createConv();
    await refresh(c.id);
  };
  const del = async (id) => {
    if (!window.confirm("Delete this conversation?")) return;
    await api.deleteConv(id);
    const list = await refresh();
    if (id === active) {
      if (list.length) setActive(list[0].id);
      else { const c = await api.createConv(); await refresh(c.id); }
    }
  };

  const ready = cfg?.has_key || (cfg?.provider === "openai_compatible" && cfg?.model);

  return (
    <section>
      <h2>Assistant</h2>
      <Settings onChange={setCfg} />
      {err && <p className="err">{err}</p>}
      <div className="sessions">
        <aside>
          <button onClick={newChat}>+ New chat</button>
          <ul>
            {convs.map((c) => (
              <li key={c.id} className={c.id === active ? "sel" : ""} onClick={() => setActive(c.id)}>
                <span className="t">{c.title}</span>
                <button className="link" title="Delete" onClick={(e) => { e.stopPropagation(); del(c.id); }}>×</button>
              </li>
            ))}
          </ul>
        </aside>
        <ChatPane convId={active} ready={ready} onTitleChange={() => refresh()} onLogged={onLogged} />
      </div>
    </section>
  );
}
