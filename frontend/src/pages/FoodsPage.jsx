import { useEffect, useState } from "react";
import { api, todayISO } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { Icon } from "../ui.jsx";

const MEALS = ["breakfast", "lunch", "dinner", "snack", "other"];

export default function FoodsPage({ onLogged }) {
  const { t, nutrient } = useI18n();
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
    const id = setTimeout(() => api.searchFoods(q.trim()).then(setResults).catch((e) => setErr(e.message)), 250);
    return () => clearTimeout(id);
  }, [q]);

  const pick = async (id) => {
    setErr(""); setMsg("");
    try { setFood(await api.getFood(id)); setGrams(100); } catch (e) { setErr(e.message); }
  };
  const log = async () => {
    setErr(""); setMsg("");
    try {
      await api.addIntake({ log_date: date, food_id: food.id, grams: Number(grams), meal });
      setMsg(t("foods.logged", { n: grams, name: food.name })); onLogged?.();
    } catch (e) { setErr(e.message); }
  };

  return (
    <div className="stack">
      <div className="page-head"><h2>{t("foods.title")}</h2></div>
      <div className="searchbox">
        <Icon name="search" size={18} />
        <input placeholder={t("foods.placeholder")} value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
      </div>
      <small>{t("foods.hint")}</small>
      <div className="split">
        <div className="card" style={{ padding: 10 }}>
          <ul className="list">
            {results.map((r) => (
              <li key={r.id} className={food?.id === r.id ? "sel" : ""} onClick={() => pick(r.id)}>
                <span className="t">{r.name}</span>
                <small>{r.source}{r.state !== "unknown" ? ` · ${r.state}` : ""}</small>
              </li>
            ))}
            {q.trim().length >= 2 && results.length === 0 && <li className="muted">{t("foods.noMatch")}</li>}
          </ul>
        </div>
        <div className="card">
          {!food ? <div className="empty">{t("foods.pick")}</div> : (
            <div className="stack">
              <div>
                <h3>{food.name}</h3>
                <small>{t("foods.source")}: {food.source_name} {food.source_version} · {t("foods.state")}: {food.state} ·{" "}
                  {t("foods.edible")}: {food.edible_portion_pct == null ? "n/a" : `${food.edible_portion_pct}%`} · {t("foods.group")}: {food.food_group ?? "n/a"}</small>
              </div>
              <div className="form-grid">
                <label className="field">{t("common.grams")}<input type="number" min="1" value={grams} onChange={(e) => setGrams(e.target.value)} /></label>
                {food.portions.length > 0 && (
                  <label className="field">{t("foods.portion")}
                    <select value="" onChange={(e) => e.target.value && setGrams(e.target.value)}>
                      <option value="">{t("foods.pickPortion")}</option>
                      {food.portions.map((p) => <option key={p.id} value={p.grams}>{p.description} ({p.grams} g)</option>)}
                    </select>
                  </label>
                )}
                <label className="field">{t("common.meal")}
                  <select value={meal} onChange={(e) => setMeal(e.target.value)}>{MEALS.map((m) => <option key={m} value={m}>{t(`meal.${m}`)}</option>)}</select>
                </label>
                <label className="field">{t("common.date")}<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
              </div>
              <div className="row">
                <button className="btn" onClick={log} disabled={!(Number(grams) > 0)}><Icon name="plus" size={16} />{t("foods.log")}</button>
                {msg && <span className="ok-text">✓ {msg}</span>}
                {err && <span className="err">{err}</span>}
              </div>
              <table>
                <thead><tr><th /><th className="num">{t("foods.per100")}</th><th className="num">{t("foods.forN", { n: grams || 0 })}</th></tr></thead>
                <tbody>
                  {food.nutrients.map((n) => (
                    <tr key={n.code}>
                      <td>{nutrient(n.code)}</td>
                      <td className="num">{n.value === null
                        ? <span className="muted">{n.qualifier === "N" ? t("foods.present") : t("foods.noData")}</span>
                        : <>{n.value} {n.unit}{n.qualifier === "trace" ? <small> ({t("foods.trace")})</small> : null}</>}</td>
                      <td className="num">{n.value === null ? "—" : `${Math.round(n.value * (grams || 0)) / 100} ${n.unit}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
