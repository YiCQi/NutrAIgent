import { useEffect, useRef, useState } from "react";
import { api, todayISO } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { Bar, Icon } from "../ui.jsx";

const MEALS = ["breakfast", "lunch", "dinner", "snack"];

function FoodPicker({ onPick }) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  useEffect(() => {
    if (q.trim().length < 2) { setRes([]); return; }
    const id = setTimeout(() => api.searchFoods(q.trim()).then((r) => setRes(r.slice(0, 10))), 250);
    return () => clearTimeout(id);
  }, [q]);
  return (
    <div>
      <input autoFocus placeholder={t("plan.searchFood")} value={q} onChange={(e) => setQ(e.target.value)} />
      {res.length > 0 && <div className="dropdown">{res.map((r) => <div key={r.id} onClick={() => onPick(r)}>{r.name} <small>[{r.source}]</small></div>)}</div>}
    </div>
  );
}

function GramsInput({ value, onCommit }) {
  const [v, setV] = useState(String(value));
  useEffect(() => setV(String(value)), [value]);
  const commit = () => { const n = Number(v); if (n > 0 && n !== value) onCommit(n); else setV(String(value)); };
  return <input type="number" min="0.5" step="0.5" style={{ width: "5.2rem", padding: "5px 8px" }} value={v}
                onChange={(e) => setV(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />;
}

function DayCard({ plan, day, reload, onLogged, disabled, regenerate }) {
  const { t, lang } = useI18n();
  const [adding, setAdding] = useState(null); // meal name while the picker is open
  const [msg, setMsg] = useState("");
  const tg = plan.targets;
  const kcal = day.totals.energy_kcal ?? 0;
  const label = new Date(day.date + "T12:00:00").toLocaleDateString(lang === "zh" ? "zh-CN" : "en-GB", { weekday: "long", month: "short", day: "numeric" });

  const log = async (meal) => {
    const r = await api.logPlan(plan.id, { plan_date: day.date, meal: meal || null });
    setMsg(t("plan.logged", { n: r.logged, date: day.date })); onLogged?.();
  };
  const present = new Set(day.meals.map((m) => m.meal));
  const allMeals = MEALS.filter((m) => present.has(m) || adding === m);

  return (
    <div className="card stack">
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h3>{label}</h3>
          <small>{Math.round(kcal)} / {tg ? Math.round(tg.energy_kcal.value) : "—"} {t("plan.kcal")}
            {day.totals.protein_g != null && ` · ${t("plan.p")} ${Math.round(day.totals.protein_g)}g`}
            {day.totals.carbohydrate_g != null && ` · ${t("plan.c")} ${Math.round(day.totals.carbohydrate_g)}g`}
            {day.totals.fat_g != null && ` · ${t("plan.f")} ${Math.round(day.totals.fat_g)}g`}
            {day.totals.fibre_g != null && ` · ${t("n.fibre_g")} ${Math.round(day.totals.fibre_g)}g`}
            {day.totals.sodium_mg != null && <span className={tg && day.totals.sodium_mg > tg.sodium_mg.value ? "warn" : ""}>{` · ${t("n.sodium_mg")} ${Math.round(day.totals.sodium_mg)}mg`}{tg && day.totals.sodium_mg > tg.sodium_mg.value ? " ⚠" : ""}</span>}</small>
        </div>
        <div className="row">
          <button className="btn sm ghost" disabled={disabled} onClick={() => regenerate(day.date)}>{t("plan.regen")}</button>
          <button className="btn sm" onClick={() => log(null)}>{t("plan.logDay")}</button>
        </div>
      </div>
      {tg && <Bar value={kcal} max={tg.energy_kcal.value} color={kcal > tg.energy_kcal.value * 1.1 ? "var(--danger)" : "var(--accent)"} />}
      {allMeals.map((m) => {
        const meal = day.meals.find((x) => x.meal === m);
        return (
          <div key={m}>
            <div className="meal-head">
              <h3>{t(`meal.${m}`)} <small>{Math.round((meal?.items || []).reduce((a, i) => a + (i.nutrients.energy_kcal ?? 0), 0))} {t("plan.kcal")}</small></h3>
              <div className="row">
                <button className="btn sm ghost" onClick={() => setAdding(adding === m ? null : m)}><Icon name="plus" size={14} />{t("plan.addItem")}</button>
                {meal && <button className="btn sm ghost" onClick={() => log(m)}>{t("plan.logMeal")}</button>}
              </div>
            </div>
            {(meal?.items || []).map((i) => (
              <div className="entry" key={i.id}>
                <span className="name" title={i.food_name}>{i.label}<small> · {i.food_name}</small></span>
                <GramsInput value={i.grams} onCommit={async (g) => { await api.patchPlanItem(plan.id, i.id, { grams: g }); reload(); }} />
                <small>g</small>
                <span className="kcal">{i.nutrients.energy_kcal == null ? "—" : Math.round(i.nutrients.energy_kcal)} <small>kcal</small></span>
                <button className="icon-btn" onClick={async () => { await api.deletePlanItem(plan.id, i.id); reload(); }}><Icon name="x" size={16} /></button>
              </div>
            ))}
            {adding === m && (
              <FoodPicker onPick={async (f) => { await api.addPlanItem(plan.id, { plan_date: day.date, meal: m, food_id: f.id, grams: 100 }); setAdding(null); reload(); }} />
            )}
          </div>
        );
      })}
      {msg && <small className="ok-text">✓ {msg}</small>}
    </div>
  );
}

export default function PlanPage({ onLogged, go }) {
  const { t, lang } = useI18n();
  const [plans, setPlans] = useState([]);
  const [planId, setPlanId] = useState(null);
  const [plan, setPlan] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ start_date: todayISO(), days: 7, meals: ["breakfast", "lunch", "dinner"], notes: "" });
  const [busy, setBusy] = useState(false);
  const [steps, setSteps] = useState([]);
  const [secs, setSecs] = useState(0);
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [ready, setReady] = useState({ profile: true, ai: true });
  const poll = useRef(null);

  const loadList = () => api.listPlans().then((l) => { setPlans(l); return l; });
  const loadPlan = (id) => api.getPlan(id).then((p) => { setPlan(p); return p; }).catch((e) => setErr(e.message));

  useEffect(() => {
    loadList().then((l) => { if (l.length) setPlanId(l[0].id); });
    Promise.all([api.getProfile().then(() => true).catch(() => false), api.getAISettings().then((s) => !!(s.has_key || (s.provider === "openai_compatible" && s.model))).catch(() => false)])
      .then(([profile, ai]) => setReady({ profile, ai }));
  }, []);
  useEffect(() => { setPlan(null); if (planId != null) loadPlan(planId); }, [planId]);
  useEffect(() => {  // a plan generated in the background (e.g. after a reload): poll until finished
    clearInterval(poll.current);
    if (plan?.pending) poll.current = setInterval(() => loadPlan(plan.id), 3000);
    return () => clearInterval(poll.current);
  }, [plan?.pending, plan?.id]);
  useEffect(() => {
    if (!busy) return;
    setSecs(0);
    const id = setInterval(() => setSecs((x) => x + 1), 1000);
    return () => clearInterval(id);
  }, [busy]);

  const run = async (start) => {
    setBusy(true); setErr(""); setInfo(""); setSteps([{ text: t("status.sending"), done: false }]);
    let pid = null;
    try {
      const done = await start((ev) => {
        if (ev.type === "plan") pid = ev.plan_id;
        if (ev.type === "status") setSteps((st) => [...st.map((x) => ({ ...x, done: true })), { text: t(`status.${ev.key}`, { arg: ev.arg ?? "" }), done: false }]);
      });
      const l = await loadList();
      if (done.plan_id && done.plan_id !== planId) setPlanId(done.plan_id); else loadPlan(done.plan_id ?? planId);
      if (done.dropped) setInfo(t("plan.dropped", { n: done.dropped }));
      setShowForm(false);
      return l;
    } catch (e) {
      setErr(e.message);
      await loadList();
      if (pid) setPlanId(pid);
    } finally { setBusy(false); setSteps([]); }
  };

  const generate = () => run((on) => api.generatePlan({ ...form, days: Number(form.days), lang }, on));
  const regenerate = (date) => run((on) => api.regenerateDay(plan.id, date, { lang }, on));
  const del = async () => {
    if (!window.confirm(t("plan.confirmDelete"))) return;
    await api.deletePlan(plan.id);
    const l = await loadList(); setPlan(null); setPlanId(l.length ? l[0].id : null);
  };
  const toggleMeal = (m) => setForm({ ...form, meals: form.meals.includes(m) ? form.meals.filter((x) => x !== m) : [...form.meals, m] });
  const canGenerate = ready.profile && ready.ai && form.meals.length > 0 && !busy;

  return (
    <div className="stack">
      <div className="page-head">
        <h2>{t("plan.title")}</h2>
        <div className="row">
          {plans.length > 0 && (
            <select value={planId ?? ""} onChange={(e) => setPlanId(Number(e.target.value))} style={{ width: "auto" }}>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
          )}
          {plan && <button className="btn danger sm" onClick={del}><Icon name="trash" size={16} />{t("plan.delete")}</button>}
          <button className="btn" onClick={() => setShowForm(!showForm)}><Icon name="plus" size={16} />{t("plan.generate")}</button>
        </div>
      </div>

      {!ready.profile && <div className="banner"><span>{t("plan.needProfile")}</span><button className="btn sm" onClick={() => go("profile")}>{t("today.setProfile")}</button></div>}
      {ready.profile && !ready.ai && <div className="banner"><span>{t("plan.needAi")}</span><button className="btn sm" onClick={() => go("assistant")}>{t("nav.assistant")}</button></div>}

      {showForm && (
        <div className="card stack">
          <div className="form-grid">
            <label className="field">{t("plan.start")}<input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></label>
            <label className="field">{t("plan.days")}
              <select value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })}>{[1, 2, 3, 4, 5, 6, 7].map((n) => <option key={n}>{n}</option>)}</select>
            </label>
            <div className="field"><span>{t("plan.meals")}</span>
              <div className="row" style={{ paddingTop: 6 }}>
                {MEALS.map((m) => <label key={m} className="row" style={{ gap: 4 }}><input type="checkbox" checked={form.meals.includes(m)} onChange={() => toggleMeal(m)} />{t(`meal.${m}`)}</label>)}
              </div>
            </div>
            <label className="field wide">{t("plan.notes")}<textarea rows={2} placeholder={t("plan.notesPh")} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
          </div>
          <div className="row"><button className="btn" disabled={!canGenerate} onClick={generate}>{t("plan.go")}</button></div>
        </div>
      )}

      {busy && (
        <div className="card progress">
          <div className="indet"><span /></div>
          <strong>{t("plan.working", { s: secs })}</strong>
          <ul>{steps.map((x, i) => <li key={i} className={x.done ? "done" : ""}>{x.done ? "✓" : "…"} {x.text}</li>)}</ul>
        </div>
      )}
      {err && <p className="err">{err}</p>}
      {info && <p className="warn">{info}</p>}
      {plan?.pending && !busy && <div className="banner">{t("plan.pending")}</div>}

      {!plan && !busy && plans.length === 0 && (
        <div className="card empty"><strong>{t("plan.empty")}</strong>{t("plan.emptyHint")}</div>
      )}
      {plan && (
        <>
          <small>{t("plan.hint")}</small>
          {plan.days.map((d) => <DayCard key={d.date} plan={plan} day={d} disabled={busy || plan.pending}
                                         reload={() => loadPlan(plan.id)} onLogged={onLogged} regenerate={regenerate} />)}
        </>
      )}
    </div>
  );
}
