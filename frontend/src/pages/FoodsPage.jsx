import { useEffect, useState } from "react";
import { api, todayISO } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { Icon } from "../ui.jsx";

const MEALS = ["breakfast", "lunch", "dinner", "snack", "other"];
const CATS = ["all", "staple", "protein", "dairy", "veg", "fruit", "fat"];
const COLS = [["energy_kcal", "col.kcal"], ["protein_g", "col.protein"], ["carbohydrate_g", "col.carbs"],
  ["fat_g", "col.fat"], ["fibre_g", "col.fibre"], ["sodium_mg", "col.sodium"]];
const fmt = (v) => (v === null || v === undefined ? "—" : Math.round(v * 10) / 10);

export default function FoodsPage({ onLogged }) {
  const { t, nutrient, lang } = useI18n();
  const [feat, setFeat] = useState([]);
  const [cat, setCat] = useState("all");
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [food, setFood] = useState(null);
  const [grams, setGrams] = useState(100);
  const [meal, setMeal] = useState("breakfast");
  const [date, setDate] = useState(todayISO());
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => { api.featuredFoods().then(setFeat).catch(() => {}); }, []);

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

  const detailCard = (
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
  );

  const searching = q.trim().length >= 2;
  const rows = feat.filter((r) => cat === "all" || r.category === cat);

  return (
    <div className="stack">
      <div className="page-head"><h2>{t("foods.title")}</h2></div>
      <div className="searchbox">
        <Icon name="search" size={18} />
        <input placeholder={t("foods.placeholder")} value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
      </div>
      <small>{t("foods.hint")}</small>
      {!searching && (
        <>
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <h3 style={{ margin: 0 }}>{t("foods.featured")}</h3>
              <div className="seg" role="group">
                {CATS.map((c) => <button key={c} className={cat === c ? "on" : ""} onClick={() => setCat(c)}>{t(`cat.${c}`)}</button>)}
              </div>
            </div>
            <small>{t("foods.featuredHint")}</small>
            <div style={{ overflowX: "auto", marginTop: 8 }}>
              <table className="featured">
                <thead><tr><th>{t("col.food")}</th>{COLS.map(([k, l]) => <th key={k} className="num">{t(l)}</th>)}</tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.food_id} className={`clickable ${food?.id === r.food_id ? "sel" : ""}`} onClick={() => pick(r.food_id)} title={r.food_name}>
                      <td>{lang === "zh" ? r.label_zh : r.label_en}</td>
                      {COLS.map(([k]) => <td key={k} className={`num ${r[k] === null ? "muted" : ""}`}>{fmt(r[k])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {food && detailCard}
        </>
      )}
      {searching && <div className="split">
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
        {detailCard}
      </div>}
    </div>
  );
}
