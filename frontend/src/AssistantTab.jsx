import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const label = (ev) => {
  const i = ev.input || {};
  switch (ev.tool) {
    case "search_foods": return `Searching foods: ${i.query ?? ""}`;
    case "get_food": return "Reading food details";
    case "get_targets": return "Reading your targets";
    case "get_daily_intake": return `Reading intake for ${i.date ?? "the day"}`;
    case "propose_log_entries": return "Preparing log entries";
    default: return ev.tool;
  }
};

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
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [proposals, setProposals] = useState([]);
  const [trace, setTrace] = useState([]);
  const [saved, setSaved] = useState("");
  const [secs, setSecs] = useState(0);
  const [steps, setSteps] = useState([]); // {text, done}
  const end = useRef(null);
  useEffect(() => {
    if (!busy) return;
    setSecs(0);
    const t = setInterval(() => setSecs((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [busy]);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [history, proposals]);

  const ready = cfg?.has_key || (cfg?.provider === "openai_compatible" && cfg?.model);

  const send = async (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    const next = [...history, { role: "user", content: text }];
    setHistory(next); setInput(""); setBusy(true); setErr(""); setSaved("");
    try {
      setSteps([{ text: "Sending to the model…", done: false }]);
      const r = await api.chatStream(next, (ev) => {
        setSteps((st) => {
          if (ev.type === "model") return [...st.map((x) => ({ ...x, done: true })), { text: ev.step === 1 ? "Model is reading your message…" : `Model is thinking (round ${ev.step})…`, done: false }];
          if (ev.type === "tool") return [...st.map((x) => (x.text.startsWith("Model") ? { ...x, done: true } : x)), { text: label(ev), done: false, tool: ev.tool }];
          if (ev.type === "tool_done") { let hit = false; return st.map((x) => { if (!hit && !x.done && x.tool === ev.tool) { hit = true; return { ...x, done: true, error: ev.error }; } return x; }); }
          return st;
        });
      });
      setHistory([...next, { role: "assistant", content: r.reply }]);
      setProposals(r.proposals); setTrace(r.trace);
    } catch (e2) { setErr(e2.message); }
    setBusy(false);
  };

  const confirm = async () => {
    setErr("");
    try {
      for (const p of proposals) await api.addIntake({ log_date: p.log_date, food_id: p.food_id, grams: p.grams, meal: p.meal });
      setSaved(`Logged ${proposals.length} entr${proposals.length === 1 ? "y" : "ies"}.`);
      setProposals([]); onLogged?.();
    } catch (e2) { setErr(e2.message); }
  };

  return (
    <section>
      <h2>Assistant</h2>
      <Settings onChange={setCfg} />
      <p className="muted">Try: “I had two eggs and a banana for breakfast” or “How is my protein today?”. Nutrient numbers come from the food database, not from the AI.</p>
      <div className="chat">
        {history.map((m, i) => <div key={i} className={`msg ${m.role}`}>{m.content}</div>)}
        {busy && (
          <div className="msg assistant progress">
            <div className="bar"><span /></div>
            <strong>Working… {secs}s</strong>
            <ul>{steps.map((x, i) => <li key={i} className={x.done ? "done" : ""}>{x.error ? "⚠" : x.done ? "✓" : "…"} {x.text}{x.error ? ` (${x.error})` : ""}</li>)}</ul>
            <small>Each model round trip can take several seconds. Nothing is saved until you confirm.</small>
          </div>
        )}
        {proposals.length > 0 && (
          <div className="card">
            <strong>Proposed log entries (not saved yet)</strong>
            <table>
              <thead><tr><th>Food</th><th>Grams</th><th>Meal</th><th>Date</th></tr></thead>
              <tbody>{proposals.map((p, i) => <tr key={i}><td>{p.food_name}</td><td><input type="number" min="1" style={{ width: "5rem" }} value={p.grams} onChange={(e) => setProposals(proposals.map((q, j) => (j === i ? { ...q, grams: Number(e.target.value) } : q)))} /></td><td>{p.meal}</td><td>{p.log_date}</td></tr>)}</tbody>
            </table>
            <button onClick={confirm} disabled={proposals.some((p) => !(p.grams > 0))}>Confirm and log</button>{" "}
            <button className="link" onClick={() => setProposals([])}>Discard</button>
          </div>
        )}
        {saved && <p className="ok">{saved}</p>}
        <div ref={end} />
      </div>
      {err && <p className="err">{err}</p>}
      <form onSubmit={send} className="chatinput">
        <input value={input} onChange={(e) => setInput(e.target.value)} disabled={!ready || busy}
               placeholder={ready ? "Ask or log food in plain language…" : "Configure a provider and key above first"} />
        <button type="submit" disabled={!ready || busy || !input.trim()}>Send</button>
      </form>
      {trace.length > 0 && (
        <details>
          <summary>Tools used for last reply ({trace.length})</summary>
          <div className="tools">{trace.map((t, i) => <div key={i}>{t.tool}({JSON.stringify(t.input)}){t.error ? ` → error: ${t.error}` : ""}</div>)}</div>
        </details>
      )}
    </section>
  );
}
