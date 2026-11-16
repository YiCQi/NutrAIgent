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
  chat: (messages) => req("POST", "/api/ai/chat", { messages }),
  getIntake: (date) => req("GET", `/api/intake/${date}`),
};

export const todayISO = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
