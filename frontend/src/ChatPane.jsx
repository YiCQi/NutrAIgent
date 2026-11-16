import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const MEALS = ["breakfast", "lunch", "dinner", "snack", "other"];

function Proposals({ message, onSaved }) {
  const [rows, setRows] = useState(() => (message.meta.proposals || []).map((p) => ({ ...p, include: p.food_id != null })));
  const [status, setStatus] = useState(message.meta.status || "pending");
  const [err, setErr] = useState("");
  const upd = (i, patch) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const chosen = rows.filter((r) => r.include && r.food_id && r.grams > 0);

  const confirm = async () => {
    setErr("");
    try {
      for (const r of chosen) await api.addIntake({ log_date: r.log_date, food_id: r.food_id, grams: Number(r.grams), meal: r.meal });
      await api.setProposalStatus(message.id, "saved");
      setStatus("saved"); onSaved?.();
    } catch (e) { setErr(e.message); }
  };
  const discard = async () => { await api.setProposalStatus(message.id, "discarded"); setStatus("discarded"); };

  if (status === "saved") return <p className="ok">✓ Logged to your diary.</p>;
  if (status === "discarded") return <p className="muted">Discarded.</p>;
  return (
    <div className="card">
      <strong>Check before saving (nothing is saved yet)</strong>
      <table>
        <thead><tr><th /><th>You said</th><th>Matched food (change if wrong)</th><th>Grams</th><th>Meal</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td><input type="checkbox" checked={r.include} disabled={!r.food_id} onChange={(e) => upd(i, { include: e.target.checked })} /></td>
              <td>{r.label}</td>
              <td>
                {r.food_id ? (
                  <select value={r.food_id} onChange={(e) => { const a = r.alternatives.find((x) => x.food_id === Number(e.target.value)); upd(i, { food_id: a.food_id, food_name: a.food_name }); }}>
                    {r.alternatives.map((a) => <option key={a.food_id} value={a.food_id}>{a.food_name} [{a.source}]</option>)}
                  </select>
                ) : <span className="muted">no match found — add it from the Foods tab</span>}
                {r.food_id && <div><small>{r.grams_basis}</small></div>}
              </td>
              <td><input type="number" min="1" style={{ width: "5rem" }} value={r.grams ?? ""} disabled={!r.food_id} onChange={(e) => upd(i, { grams: Number(e.target.value) })} /></td>
              <td><select value={r.meal} onChange={(e) => upd(i, { meal: e.target.value })}>{MEALS.map((m) => <option key={m}>{m}</option>)}</select></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={confirm} disabled={chosen.length === 0}>Confirm and log ({chosen.length})</button>{" "}
      <button className="link" onClick={discard}>Discard</button>
      {err && <p className="err">{err}</p>}
    </div>
  );
}

export default function ChatPane({ convId, ready, onTitleChange, onLogged }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [steps, setSteps] = useState([]);
  const [secs, setSecs] = useState(0);
  const [err, setErr] = useState("");
  const end = useRef(null);

  useEffect(() => {
    setMessages([]); setErr(""); setSteps([]);
    if (convId == null) return;
    api.getConv(convId).then((c) => setMessages(c.messages)).catch((e) => setErr(e.message));
  }, [convId]);

  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [messages, steps]);
  useEffect(() => {
    if (!busy) return;
    setSecs(0);
    const t = setInterval(() => setSecs((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [busy]);

  const send = async (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy || convId == null) return;
    setMessages((m) => [...m, { id: `tmp${Date.now()}`, role: "user", content: text, meta: {} }]);
    setInput(""); setBusy(true); setErr(""); setSteps([{ text: "Sending…", done: false }]);
    try {
      const done = await api.chatStream(convId, text, (ev) => {
        if (ev.type === "status") setSteps((st) => [...st.map((x) => ({ ...x, done: true })), { text: ev.text, done: false }]);
      });
      setMessages((m) => [...m, done.message]);
      onTitleChange?.();
    } catch (e2) { setErr(e2.message); }
    setBusy(false); setSteps([]);
  };

  return (
    <div className="chatpane">
      <div className="chat">
        {messages.length === 0 && !busy && (
          <p className="muted">Try: “I had two eggs and a banana for breakfast” or “How is my protein today?”. Nutrient numbers come from the food database, not from the AI.</p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            {m.content}
            {m.role === "assistant" && m.meta?.proposals?.length > 0 && <Proposals message={m} onSaved={onLogged} />}
          </div>
        ))}
        {busy && (
          <div className="msg assistant progress">
            <div className="bar"><span /></div>
            <strong>Working… {secs}s</strong>
            <ul>{steps.map((x, i) => <li key={i} className={x.done ? "done" : ""}>{x.done ? "✓" : "…"} {x.text}</li>)}</ul>
          </div>
        )}
        <div ref={end} />
      </div>
      {err && <p className="err">{err}</p>}
      <form onSubmit={send} className="chatinput">
        <input value={input} onChange={(e) => setInput(e.target.value)} disabled={!ready || busy || convId == null}
               placeholder={ready ? "Ask or log food in plain language…" : "Configure a provider and key above first"} />
        <button type="submit" disabled={!ready || busy || !input.trim() || convId == null}>Send</button>
      </form>
    </div>
  );
}
