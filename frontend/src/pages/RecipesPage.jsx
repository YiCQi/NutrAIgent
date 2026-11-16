import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { Icon } from "../ui.jsx";

function IngredientPicker({ onPick }) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  useEffect(() => {
    if (q.trim().length < 2) { setRes([]); return; }
    const id = setTimeout(() => api.searchFoods(q.trim()).then((r) => setRes(r.filter((x) => x.source !== "user_recipe").slice(0, 12))), 250);
    return () => clearTimeout(id);
  }, [q]);
  return (
    <div>
      <div className="searchbox"><Icon name="search" size={16} />
        <input placeholder={t("recipes.searchIng")} value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {res.length > 0 && (
        <div className="dropdown">
          {res.map((r) => <div key={r.id} onClick={() => { onPick(r); setQ(""); setRes([]); }}>{r.name} <small>[{r.source}]</small></div>)}
        </div>
      )}
    </div>
  );
}

function Editor({ initial, onDone }) {
  const { t, nutrient } = useI18n();
  const [r, setR] = useState(initial);
  const [saved, setSaved] = useState(initial.nutrients_per_100g || null);
  const [err, setErr] = useState("");
  const raw = r.ingredients.reduce((a, i) => a + (Number(i.grams) || 0), 0);

  const setIng = (idx, patch) => setR({ ...r, ingredients: r.ingredients.map((x, j) => (j === idx ? { ...x, ...patch } : x)) });
  const save = async () => {
    setErr("");
    if (!r.ingredients.length) { setErr(t("recipes.noIng")); return; }
    const body = {
      name: r.name, notes: r.notes || "", yield_g: r.yield_g ? Number(r.yield_g) : null,
      ingredients: r.ingredients.map((i) => ({ food_id: i.food_id, grams: Number(i.grams) })),
    };
    try {
      const out = r.id ? await api.updateRecipe(r.id, body) : await api.createRecipe(body);
      setSaved(out.nutrients_per_100g);
      setR({ ...r, id: out.id });
      onDone(false);
    } catch (e) { setErr(e.message); }
  };
  const del = async () => {
    if (!window.confirm(t("recipes.confirmDelete"))) return;
    try { await api.deleteRecipe(r.id); onDone(true); } catch (e) { setErr(e.message); }
  };

  return (
    <div className="stack">
      <div className="page-head">
        <button className="btn ghost sm" onClick={() => onDone(true)}><Icon name="left" size={16} />{t("common.back")}</button>
        <div className="row">
          {r.id && <button className="btn danger sm" onClick={del}><Icon name="trash" size={16} />{t("common.delete")}</button>}
          <button className="btn" onClick={save} disabled={!r.name.trim()}>{t("recipes.save")}</button>
        </div>
      </div>
      {err && <p className="err">{err}</p>}
      <div className="card stack">
        <div className="form-grid">
          <label className="field wide">{t("recipes.name")}<input value={r.name} onChange={(e) => setR({ ...r, name: e.target.value })} /></label>
          <label className="field">{t("recipes.yield")}<input type="number" min="1" value={r.yield_g ?? ""} placeholder={String(Math.round(raw))} onChange={(e) => setR({ ...r, yield_g: e.target.value })} /></label>
          <label className="field"><span>{t("recipes.rawTotal")}</span><input disabled value={`${Math.round(raw)} g`} /></label>
        </div>
        <small>{t("recipes.yieldHint")}</small>
        <h3>{t("recipes.ingredients")}</h3>
        <div>
          {r.ingredients.map((i, idx) => (
            <div className="ing-row" key={`${i.food_id}-${idx}`}>
              <span>{i.food_name}</span>
              <input type="number" min="0.1" step="0.1" value={i.grams} onChange={(e) => setIng(idx, { grams: e.target.value })} />
              <button className="icon-btn" onClick={() => setR({ ...r, ingredients: r.ingredients.filter((_, j) => j !== idx) })}><Icon name="x" size={16} /></button>
            </div>
          ))}
        </div>
        <IngredientPicker onPick={(f) => setR({ ...r, ingredients: [...r.ingredients, { food_id: f.id, food_name: f.name, grams: 10 }] })} />
        <label className="field">{t("recipes.notes")}<textarea rows={2} value={r.notes || ""} onChange={(e) => setR({ ...r, notes: e.target.value })} /></label>
      </div>

      {saved && (
        <div className="card">
          <h3 style={{ marginBottom: 8 }}>{t("recipes.nutrition")}</h3>
          <table>
            <tbody>
              {saved.map((n) => (
                <tr key={n.code}><td>{nutrient(n.code)}</td><td className="num">{n.value == null ? "—" : `${Math.round(n.value * 10) / 10} ${n.unit}`}</td></tr>
              ))}
            </tbody>
          </table>
          <small>{t("recipes.missingNote")}</small>
        </div>
      )}
    </div>
  );
}

export default function RecipesPage() {
  const { t } = useI18n();
  const [list, setList] = useState([]);
  const [editing, setEditing] = useState(null);
  const [err, setErr] = useState("");
  const load = () => api.listRecipes().then(setList).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const open = async (id) => { const r = await api.getRecipe(id); setEditing({ ...r, ingredients: r.ingredients.map((i) => ({ ...i })), yield_g: r.yield_g === r.raw_total_g ? "" : r.yield_g }); };

  if (editing) return <Editor initial={editing} onDone={(close) => { load(); if (close) setEditing(null); }} />;
  return (
    <div className="stack">
      <div className="page-head">
        <h2>{t("recipes.title")}</h2>
        <button className="btn" onClick={() => setEditing({ name: "", notes: "", yield_g: "", ingredients: [] })}><Icon name="plus" size={16} />{t("recipes.new")}</button>
      </div>
      {err && <p className="err">{err}</p>}
      {list.length === 0 ? (
        <div className="card empty"><strong>{t("recipes.empty")}</strong>{t("recipes.emptyHint")}</div>
      ) : (
        <div className="recipe-grid">
          {list.map((r) => (
            <div key={r.id} className="card recipe-card" onClick={() => open(r.id)}>
              <h3>{r.name}</h3>
              <small>{t("recipes.nIng", { n: r.n_ingredients })} · {Math.round(r.yield_g)} g</small>
              <span className="chip ok" style={{ alignSelf: "flex-start" }}>{r.kcal_per_100g == null ? "—" : t("recipes.kcal100", { n: Math.round(r.kcal_per_100g) })}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
