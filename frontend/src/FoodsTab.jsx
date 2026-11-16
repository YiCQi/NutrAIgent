import { useEffect, useState } from "react";
import { api, todayISO } from "./api.js";

export default function FoodsTab({ onLogged }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [food, setFood] = useState(null);
  const [grams, setGrams] = useState(100);
  const [meal, setMeal] = useState("breakfast");
  const [date, setDate] = useState(todayISO());
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(() => api.searchFoods(q.trim()).then(setResults).catch((e) => setErr(e.message)), 250);
    return () => clearTimeout(t);
  }, [q]);

  const pick = async (id) => {
    setErr(""); setMsg("");
    try { setFood(await api.getFood(id)); setGrams(100); } catch (e) { setErr(e.message); }
  };

  const log = async () => {
    setErr(""); setMsg("");
    try {
      await api.addIntake({ log_date: date, food_id: food.id, grams: Number(grams), meal });
      setMsg(`Logged ${grams} g of ${food.name} on ${date}.`);
      onLogged?.();
    } catch (e) { setErr(e.message); }
  };

  return (
    <section>
      <h2>Foods</h2>
      <input className="search" placeholder="Search foods (min 2 letters), e.g. oats" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="cols">
        <ul className="list">
          {results.map((r) => (
            <li key={r.id} className={food?.id === r.id ? "sel" : ""} onClick={() => pick(r.id)}>
              {r.name} <small>[{r.source}{r.state !== "unknown" ? `, ${r.state}` : ""}]</small>
            </li>
          ))}
          {q.trim().length >= 2 && results.length === 0 && <li className="muted">No matches.</li>}
        </ul>
        {food && (
          <div className="detail">
            <h3>{food.name}</h3>
            <p className="muted">
              Source: {food.source_name} {food.source_version} · state: {food.state} · edible portion:{" "}
              {food.edible_portion_pct ?? "n/a"}{food.edible_portion_pct != null ? "%" : ""} · group: {food.food_group ?? "n/a"}
            </p>
            <div className="logrow">
              <label>Grams<input type="number" min="1" value={grams} onChange={(e) => setGrams(e.target.value)} /></label>
              {food.portions.length > 0 && (
                <label>Portion
                  <select value="" onChange={(e) => e.target.value && setGrams(e.target.value)}>
                    <option value="">pick…</option>
                    {food.portions.map((p) => <option key={p.id} value={p.grams}>{p.description} ({p.grams} g)</option>)}
                  </select>
                </label>
              )}
              <label>Meal
                <select value={meal} onChange={(e) => setMeal(e.target.value)}>
                  {["breakfast", "lunch", "dinner", "snack", "other"].map((m) => <option key={m}>{m}</option>)}
                </select>
              </label>
              <label>Date<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
              <button onClick={log} disabled={!(Number(grams) > 0)}>Log it</button>
            </div>
            <table>
              <thead><tr><th>Nutrient</th><th>Per 100 g</th><th>For {grams || 0} g</th></tr></thead>
              <tbody>
                {food.nutrients.map((n) => (
                  <tr key={n.code}>
                    <td>{n.name}</td>
                    <td>
                      {n.value === null
                        ? <span className="muted">{n.qualifier === "N" ? "present, amount unknown (N)" : "no data"}</span>
                        : <>{n.value} {n.unit}{n.qualifier === "trace" ? " (trace)" : ""}</>}
                    </td>
                    <td>{n.value === null ? "—" : `${Math.round(n.value * (grams || 0)) / 100} ${n.unit}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {msg && <p className="ok">{msg}</p>}
      {err && <p className="err">{err}</p>}
    </section>
  );
}
