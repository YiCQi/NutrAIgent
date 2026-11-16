import { useState } from "react";
import { api } from "../api.js";
import { basisLabel, useI18n } from "../i18n.jsx";

const MEALS = ["breakfast", "lunch", "dinner", "snack", "other"];

function FoodSelect({ row, onChange }) {
  const { t } = useI18n();
  if (!row.food_id) return <span className="muted">{t("assistant.noMatch")}</span>;
  return (
    <>
      <select value={row.food_id} onChange={(e) => {
        const a = row.alternatives.find((x) => x.food_id === Number(e.target.value));
        onChange({ food_id: a.food_id, food_name: a.food_name });
      }}>
        {row.alternatives.map((a) => <option key={a.food_id} value={a.food_id}>{a.food_name} [{a.source}]</option>)}
      </select>
      <span className="basis">{basisLabel(t, row.grams_basis)}</span>
    </>
  );
}

function MealSelect({ value, onChange }) {
  const { t } = useI18n();
  return <select value={value} onChange={(e) => onChange(e.target.value)}>{MEALS.map((m) => <option key={m} value={m}>{t(`meal.${m}`)}</option>)}</select>;
}

export default function Proposals({ message, onSaved }) {
  const { t } = useI18n();
  const [items, setItems] = useState(() => (message.meta.proposals || []).map((p) => ({
    ...p, include: p.kind === "recipe" ? true : p.food_id != null, done: false,
    ingredients: p.ingredients?.map((i) => ({ ...i, include: i.food_id != null })),
  })));
  const [status, setStatus] = useState(message.meta.status || "pending");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const upd = (i, patch) => setItems((xs) => xs.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const updIng = (i, k, patch) => setItems((xs) => xs.map((x, j) => (j !== i ? x : { ...x, ingredients: x.ingredients.map((g, m) => (m === k ? { ...g, ...patch } : g)) })));

  const usableIngs = (p) => p.ingredients.filter((g) => g.include && g.food_id && g.grams > 0);
  const count = items.filter((p) => p.include && (p.kind === "recipe" ? usableIngs(p).length > 0 : p.food_id && p.grams > 0)).length;

  const confirm = async () => {
    setErr(""); setBusy(true);
    try {
      for (let i = 0; i < items.length; i++) {
        const p = items[i];
        if (!p.include || p.done) continue;
        if (p.kind === "recipe") {
          const ings = usableIngs(p);
          if (!ings.length) continue;
          if (p.save) {
            const rec = await api.createRecipe({
              name: p.name.trim(), yield_g: p.yield_g ? Number(p.yield_g) : null,
              ingredients: ings.map((g) => ({ food_id: g.food_id, grams: Number(g.grams) })),
            });
            await api.addIntake({ log_date: p.log_date, food_id: rec.id, grams: Number(p.eat_g), meal: p.meal });
          } else {
            for (const g of ings) await api.addIntake({ log_date: p.log_date, food_id: g.food_id, grams: Number(g.grams), meal: p.meal });
          }
        } else if (p.food_id && p.grams > 0) {
          await api.addIntake({ log_date: p.log_date, food_id: p.food_id, grams: Number(p.grams), meal: p.meal });
        }
        upd(i, { done: true });
        p.done = true;
      }
      await api.setProposalStatus(message.id, "saved");
      setStatus("saved"); onSaved?.();
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const discard = async () => { await api.setProposalStatus(message.id, "discarded"); setStatus("discarded"); };

  if (status === "saved") return <p className="ok-text" style={{ margin: "8px 0 0" }}>✓ {t("assistant.logged")}</p>;
  if (status === "discarded") return <p className="muted" style={{ margin: "8px 0 0" }}>{t("assistant.discarded")}</p>;

  return (
    <div>
      <small style={{ display: "block", marginTop: 8 }}>{t("assistant.check")}</small>
      {items.map((p, i) => p.kind === "recipe" ? (
        <div className="proposal" key={i} style={{ opacity: p.done ? .55 : 1 }}>
          <div className="dish-head">
            <input type="checkbox" checked={p.include} onChange={(e) => upd(i, { include: e.target.checked })} />
            <label className="field">{t("assistant.recipeName")}<input value={p.name} onChange={(e) => upd(i, { name: e.target.value })} disabled={!p.save} /></label>
            <label className="field">{t("assistant.yield")}<input type="number" min="1" value={p.yield_g ?? ""} onChange={(e) => upd(i, { yield_g: e.target.value })} /></label>
            <label className="field">{t("assistant.eat")}<input type="number" min="1" value={p.eat_g ?? ""} onChange={(e) => upd(i, { eat_g: e.target.value })} /></label>
            <label className="field">{t("common.meal")}<MealSelect value={p.meal} onChange={(v) => upd(i, { meal: v })} /></label>
          </div>
          <label className="row" style={{ margin: "4px 0 8px", fontSize: ".9rem" }}>
            <input type="checkbox" checked={p.save} onChange={(e) => upd(i, { save: e.target.checked })} /> {t("assistant.saveRecipe")}
          </label>
          <table>
            <thead><tr><th /><th>{t("assistant.youSaid")}</th><th>{t("assistant.matched")}</th><th>{t("common.grams")}</th></tr></thead>
            <tbody>
              {p.ingredients.map((g, k) => (
                <tr key={k}>
                  <td><input type="checkbox" checked={g.include} disabled={!g.food_id} onChange={(e) => updIng(i, k, { include: e.target.checked })} /></td>
                  <td>{g.label}</td>
                  <td><FoodSelect row={g} onChange={(patch) => updIng(i, k, patch)} /></td>
                  <td><input type="number" min="0.1" step="0.1" style={{ width: "5.2rem" }} value={g.grams ?? ""} disabled={!g.food_id} onChange={(e) => updIng(i, k, { grams: Number(e.target.value) })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="proposal" key={i} style={{ opacity: p.done ? .55 : 1 }}>
          <table>
            <thead><tr><th /><th>{t("assistant.youSaid")}</th><th>{t("assistant.matched")}</th><th>{t("common.grams")}</th><th>{t("common.meal")}</th></tr></thead>
            <tbody>
              <tr>
                <td><input type="checkbox" checked={p.include} disabled={!p.food_id} onChange={(e) => upd(i, { include: e.target.checked })} /></td>
                <td>{p.label}</td>
                <td><FoodSelect row={p} onChange={(patch) => upd(i, patch)} /></td>
                <td><input type="number" min="1" style={{ width: "5.2rem" }} value={p.grams ?? ""} disabled={!p.food_id} onChange={(e) => upd(i, { grams: Number(e.target.value) })} /></td>
                <td><MealSelect value={p.meal} onChange={(v) => upd(i, { meal: v })} /></td>
              </tr>
            </tbody>
          </table>
        </div>
      ))}
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn" onClick={confirm} disabled={busy || count === 0}>{t("assistant.confirm", { n: count })}</button>
        <button className="btn ghost" onClick={discard} disabled={busy}>{t("assistant.discard")}</button>
      </div>
      {err && <p className="err" style={{ margin: "8px 0 0" }}>{err}</p>}
    </div>
  );
}
