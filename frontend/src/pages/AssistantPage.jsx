import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { Icon } from "../ui.jsx";
import Proposals from "./Proposals.jsx";

const HINT = {
  anthropic: { model: "claude-sonnet-5-5", url: "https://api.anthropic.com" },
  openai_compatible: { model: "model name", url: "https://api.openai.com/v1  |  http://localhost:11434/v1" },
};

function Settings({ onChange }) {
  const { t } = useI18n();
  const [s, setS] = useState({ provider: "anthropic", model: "", base_url: "", has_key: false });
  const [key, setKey] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => { api.getAISettings().then((x) => { setS(x); onChange?.(x); }).catch((e) => setErr(e.message)); }, []);
  const body = (api_key) => ({ provider: s.provider, model: s.model, base_url: s.base_url, api_key });
  const save = async (e) => {
    e.preventDefault(); setErr(""); setMsg("");
    try { const x = await api.putAISettings(body(key === "" ? null : key)); setS(x); setKey(""); setMsg(t("assistant.settingsSaved")); onChange?.(x); }
    catch (e2) { setErr(e2.message); }
  };
  const clearKey = async () => { const x = await api.putAISettings(body("")); setS(x); onChange?.(x); setMsg(t("assistant.keyRemoved")); };

  return (
    <details className="card" open={!s.has_key || !s.model}>
      <summary>{t("assistant.settings")}</summary>
      <form onSubmit={save} className="stack" style={{ marginTop: 12 }}>
        <div className="form-grid">
          <label className="field">{t("assistant.provider")}
            <select value={s.provider} onChange={(e) => setS({ ...s, provider: e.target.value })}>
              <option value="anthropic">Anthropic</option><option value="openai_compatible">OpenAI-compatible</option>
            </select>
          </label>
          <label className="field">{t("assistant.model")}<input value={s.model} placeholder={HINT[s.provider].model} onChange={(e) => setS({ ...s, model: e.target.value })} /></label>
          <label className="field wide">{t("assistant.baseUrl")}<input value={s.base_url} placeholder={HINT[s.provider].url} onChange={(e) => setS({ ...s, base_url: e.target.value })} /></label>
          <label className="field wide">{t("assistant.apiKey")}{s.has_key && <small>({t("assistant.keySaved")})</small>}
            <input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder={s.has_key ? "••••••••" : ""} />
          </label>
        </div>
        <div className="row">
          <button className="btn" type="submit">{t("common.save")}</button>
          {s.has_key && <button className="btn ghost" type="button" onClick={clearKey}>{t("assistant.removeKey")}</button>}
          {msg && <span className="ok-text">✓ {msg}</span>}{err && <span className="err">{err}</span>}
        </div>
        <small>{t("assistant.privacy")}</small>
      </form>
    </details>
  );
}

function statusText(t, ev) {
  if (ev.key === "thinking") return ev.arg > 1 ? `${t("status.thinking")} (${ev.arg})` : t("status.thinking");
  return t(`status.${ev.key}`, { arg: ev.arg ?? "" });
}

function ChatPane({ convId, ready, onTitleChange, onLogged }) {
  const { t, lang } = useI18n();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [steps, setSteps] = useState([]);
  const [secs, setSecs] = useState(0);
  const [err, setErr] = useState("");
  const [resuming, setResuming] = useState(false);
  const end = useRef(null);

  useEffect(() => {
    setMessages([]); setErr(""); setSteps([]);
    if (convId == null) return;
    let timer = null, dead = false;
    const load = () => api.getConv(convId).then((c) => {
      if (dead) return;
      setMessages(c.messages);
      setResuming(!!c.pending);
      if (c.pending) timer = setTimeout(load, 2500);   // reply is still being produced server-side
    }).catch((e) => !dead && setErr(e.message));
    load();
    return () => { dead = true; clearTimeout(timer); };
  }, [convId]);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [messages, steps]);
  useEffect(() => {
    if (!busy) return;
    setSecs(0);
    const id = setInterval(() => setSecs((x) => x + 1), 1000);
    return () => clearInterval(id);
  }, [busy]);

  const send = async (text) => {
    text = text.trim();
    if (!text || busy || convId == null) return;
    setMessages((m) => [...m, { id: `tmp${Date.now()}`, role: "user", content: text, meta: {} }]);
    setInput(""); setBusy(true); setErr(""); setSteps([{ text: t("status.sending"), done: false }]);
    try {
      const done = await api.chatStream(convId, text, lang, (ev) => {
        if (ev.type === "status") setSteps((st) => [...st.map((x) => ({ ...x, done: true })), { text: statusText(t, ev), done: false }]);
      });
      setMessages((m) => [...m, done.message]);
      onTitleChange?.();
    } catch (e2) { setErr(e2.message); }
    setBusy(false); setSteps([]);
  };

  const body = (m) => (m.role === "assistant" && m.meta?.kind === "log" ? t("assistant.recognised", { n: m.meta.count }) : m.content);

  return (
    <div className="chatpane">
      <div className="chatlog">
        {messages.length === 0 && !busy && (
          <div className="empty">
            <strong>{t("assistant.title")}</strong>{t("assistant.hint")}
            <div className="suggest">
              {["try1", "try2", "try3"].map((k) => <button key={k} disabled={!ready} onClick={() => send(t(`assistant.${k}`))}>{t(`assistant.${k}`)}</button>)}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`bubble ${m.role}`}>
            {body(m)}
            {m.role === "assistant" && m.meta?.proposals?.length > 0 && <Proposals message={m} onSaved={onLogged} />}
          </div>
        ))}
        {busy && (
          <div className="bubble assistant progress">
            <div className="indet"><span /></div>
            <strong>{t("assistant.working", { s: secs })}</strong>
            <ul>{steps.map((x, i) => <li key={i} className={x.done ? "done" : ""}>{x.done ? "✓" : "…"} {x.text}</li>)}</ul>
          </div>
        )}
        {resuming && !busy && <div className="bubble assistant progress"><div className="indet"><span /></div>{t("assistant.resuming")}</div>}
        <div ref={end} />
      </div>
      {err && <p className="err">{err}</p>}
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} disabled={!ready || busy || resuming || convId == null}
               placeholder={ready ? t("assistant.placeholder") : t("assistant.notReady")} />
        <button className="btn" type="submit" disabled={!ready || busy || resuming || !input.trim() || convId == null}>↑</button>
      </form>
    </div>
  );
}

export default function AssistantPage({ onLogged }) {
  const { t } = useI18n();
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
    const empty = convs.find((c) => c.title === "New chat");
    if (empty) { setActive(empty.id); return; }
    const c = await api.createConv();
    await refresh(c.id);
  };
  const del = async (id) => {
    if (!window.confirm(t("assistant.confirmDelete"))) return;
    await api.deleteConv(id);
    const list = await refresh();
    if (id === active) {
      if (list.length) setActive(list[0].id);
      else { const c = await api.createConv(); await refresh(c.id); }
    }
  };
  const ready = cfg?.has_key || (cfg?.provider === "openai_compatible" && cfg?.model);

  return (
    <div className="stack">
      <div className="page-head"><h2>{t("assistant.title")}</h2></div>
      <Settings onChange={setCfg} />
      {err && <p className="err">{err}</p>}
      <div className="assist-layout">
        <aside className="card sessions">
          <button className="btn sm" style={{ width: "100%" }} onClick={newChat}><Icon name="plus" size={16} />{t("assistant.new")}</button>
          <ul>
            {convs.map((c) => (
              <li key={c.id} className={c.id === active ? "sel" : ""} onClick={() => setActive(c.id)}>
                <span className="t">{c.title === "New chat" ? t("assistant.new") : c.title}</span>
                <button className="icon-btn" onClick={(e) => { e.stopPropagation(); del(c.id); }}><Icon name="x" size={14} /></button>
              </li>
            ))}
          </ul>
        </aside>
        <div className="card chatpane-card">
          <ChatPane convId={active} ready={ready} onTitleChange={() => refresh()} onLogged={onLogged} />
        </div>
      </div>
    </div>
  );
}
