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

// POSTs JSON and reads an NDJSON event stream. Resolves with the final 'done' event; rejects on an 'error' event.
async function streamPost(url, body, onEvent) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok || !r.body) {
    let detail = `request failed (${r.status})`;
    try { const j = await r.json(); if (typeof j.detail === "string") detail = j.detail; } catch {}
    const e = new Error(detail);
    e.status = r.status;
    throw e;
  }
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
  if (!done) { const e = new Error("connection interrupted"); e.interrupted = true; throw e; }
  return done;
}

export const api = {
  getProfile: () => req("GET", "/api/profile"),
  putProfile: (p) => req("PUT", "/api/profile", p),
  getTargets: () => req("GET", "/api/targets"),
  searchFoods: (q) => req("GET", `/api/foods?q=${encodeURIComponent(q)}&limit=40`),
  featuredFoods: () => req("GET", "/api/foods/featured"),
  getFood: (id) => req("GET", `/api/foods/${id}`),
  addIntake: (e) => req("POST", "/api/intake", e),
  deleteIntake: (id) => req("DELETE", `/api/intake/${id}`),
  editIntake: (id, grams) => req("PATCH", `/api/intake/${id}`, { grams }),
  estimateIntake: (date) => req("POST", `/api/intake/${date}/estimate`),
  getAISettings: () => req("GET", "/api/ai/settings"),
  putAISettings: (s) => req("PUT", "/api/ai/settings", s),
  listConvs: () => req("GET", "/api/conversations"),
  createConv: () => req("POST", "/api/conversations"),
  getConv: (id) => req("GET", `/api/conversations/${id}`),
  deleteConv: (id) => req("DELETE", `/api/conversations/${id}`),
  setProposalStatus: (messageId, status) => req("PATCH", `/api/messages/${messageId}/status`, { status }),
  chatStream: (convId, content, lang, onEvent) => streamPost(`/api/conversations/${convId}/chat`, { content, lang }, onEvent),
  listPlans: () => req("GET", "/api/plans"),
  getPlan: (id) => req("GET", `/api/plans/${id}`),
  deletePlan: (id) => req("DELETE", `/api/plans/${id}`),
  generatePlan: (body, onEvent) => streamPost("/api/plans/generate", body, onEvent),
  regenerateDay: (id, date, body, onEvent) => streamPost(`/api/plans/${id}/days/${date}/regenerate`, body, onEvent),
  addPlanItem: (id, item) => req("POST", `/api/plans/${id}/items`, item),
  patchPlanItem: (id, itemId, patch) => req("PATCH", `/api/plans/${id}/items/${itemId}`, patch),
  deletePlanItem: (id, itemId) => req("DELETE", `/api/plans/${id}/items/${itemId}`),
  logPlan: (id, body) => req("POST", `/api/plans/${id}/log`, body),
  getRecommendation: (date) => req("GET", `/api/recommendations/${date}`),
  generateRecommendation: (date, lang, onEvent) => streamPost(`/api/recommendations/${date}/generate`, { lang }, onEvent),
  listRecipes: () => req("GET", "/api/recipes"),
  getRecipe: (id) => req("GET", `/api/recipes/${id}`),
  createRecipe: (r) => req("POST", "/api/recipes", r),
  updateRecipe: (id, r) => req("PUT", `/api/recipes/${id}`, r),
  deleteRecipe: (id) => req("DELETE", `/api/recipes/${id}`),
  getIntake: (date) => req("GET", `/api/intake/${date}`),
};

export const todayISO = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
