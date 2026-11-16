async function req(method, url, body) {
  const r = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const j = await r.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {}
    const e = new Error(detail);
    e.status = r.status;
    throw e;
  }
  return r.status === 204 ? null : r.json();
}

export const api = {
  getProfile: () => req("GET", "/api/profile"),
  putProfile: (p) => req("PUT", "/api/profile", p),
  getTargets: () => req("GET", "/api/targets"),
  searchFoods: (q) => req("GET", `/api/foods?q=${encodeURIComponent(q)}&limit=40`),
  getFood: (id) => req("GET", `/api/foods/${id}`),
  addIntake: (e) => req("POST", "/api/intake", e),
  deleteIntake: (id) => req("DELETE", `/api/intake/${id}`),
  getAISettings: () => req("GET", "/api/ai/settings"),
  putAISettings: (s) => req("PUT", "/api/ai/settings", s),
  listConvs: () => req("GET", "/api/conversations"),
  createConv: () => req("POST", "/api/conversations"),
  getConv: (id) => req("GET", `/api/conversations/${id}`),
  deleteConv: (id) => req("DELETE", `/api/conversations/${id}`),
  setProposalStatus: (messageId, status) => req("PATCH", `/api/messages/${messageId}/status`, { status }),
  // Streams NDJSON progress events; resolves with the final 'done' event, rejects on 'error'.
  chatStream: async (convId, content, onEvent) => {
    const r = await fetch(`/api/conversations/${convId}/chat`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }),
    });
    if (!r.ok || !r.body) throw new Error(`request failed (${r.status})`);
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "", done = null;
    const handle = (line) => {
      if (!line.trim()) return;
      const ev = JSON.parse(line);
      if (ev.type === "error") throw new Error(ev.message);
      if (ev.type === "done") done = ev;
      onEvent(ev);
    };
    for (;;) {
      const { value, done: fin } = await reader.read();
      if (fin) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf(String.fromCharCode(10))) >= 0) { handle(buf.slice(0, i)); buf = buf.slice(i + 1); }
    }
    handle(buf);
    if (!done) throw new Error("connection closed before the reply finished");
    return done;
  },
  getIntake: (date) => req("GET", `/api/intake/${date}`),
};

export const todayISO = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
