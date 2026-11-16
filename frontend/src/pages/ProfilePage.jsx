import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { Bar } from "../ui.jsx";

const EMPTY = { age: 30, sex: "male", height_cm: 175, weight_kg: 70, activity_level: "light", goal: "maintenance", dietary_preferences: [] };
const ACTIVITY = ["sedentary", "light", "moderate", "active", "very_active"];
const GOALS = ["fat_loss", "maintenance", "muscle_gain"];

export default function ProfilePage({ onSaved }) {
  const { t, nutrient } = useI18n();
  const [form, setForm] = useState(EMPTY);
  const [prefs, setPrefs] = useState("");
  const [targets, setTargets] = useState(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const loadTargets = () => api.getTargets().then(setTargets).catch(() => setTargets(null));
  useEffect(() => {
    api.getProfile()
      .then((p) => { setForm(p); setPrefs(p.dietary_preferences.join(", ")); loadTargets(); })
      .catch((e) => { if (e.status !== 404) setErr(e.message); });
  }, []);

  const set = (k) => (e) => {
    const v = e.target.value;
    setForm((f) => ({ ...f, [k]: ["age", "height_cm", "weight_kg"].includes(k) ? (v === "" ? "" : Number(v)) : v }));
  };
  const save = async (e) => {
    e.preventDefault(); setErr(""); setMsg("");
    try {
      await api.putProfile({ ...form, dietary_preferences: prefs.split(/[,，]/).map((s) => s.trim()).filter(Boolean) });
      await loadTargets(); setMsg(t("profile.saved")); onSaved?.();
    } catch (e2) { setErr(e2.message); }
  };

  return (
    <div className="stack">
      <div className="page-head"><h2>{t("profile.title")}</h2></div>
      <form className="card stack" onSubmit={save}>
        <div className="form-grid">
          <label className="field">{t("profile.age")}<input type="number" value={form.age} onChange={set("age")} /></label>
          <label className="field">{t("profile.sex")}
            <select value={form.sex} onChange={set("sex")}><option value="male">{t("profile.male")}</option><option value="female">{t("profile.female")}</option></select>
          </label>
          <label className="field">{t("profile.height")}<input type="number" step="0.1" value={form.height_cm} onChange={set("height_cm")} /></label>
          <label className="field">{t("profile.weight")}<input type="number" step="0.1" value={form.weight_kg} onChange={set("weight_kg")} /></label>
          <label className="field">{t("profile.activity")}
            <select value={form.activity_level} onChange={set("activity_level")}>{ACTIVITY.map((a) => <option key={a} value={a}>{t(`act.${a}`)}</option>)}</select>
          </label>
          <label className="field">{t("profile.goal")}
            <select value={form.goal} onChange={set("goal")}>{GOALS.map((a) => <option key={a} value={a}>{t(`goal.${a}`)}</option>)}</select>
          </label>
          <label className="field wide">{t("profile.prefs")}<input value={prefs} onChange={(e) => setPrefs(e.target.value)} /></label>
        </div>
        <div className="row">
          <button className="btn" type="submit">{t("profile.save")}</button>
          {msg && <span className="ok-text">✓ {msg}</span>}
          {err && <span className="err">{err}</span>}
        </div>
      </form>

      {targets && (
        <div className="card stack">
          <h3>{t("profile.targets")}</h3>
          <div className="form-grid">
            {Object.entries(targets.targets).map(([k, v]) => (
              <div key={k} className="card flat" style={{ padding: 14 }}>
                <small>{nutrient(k)} · {v.kind === "max" ? t("profile.limit") : t("profile.aim")}</small>
                <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{v.value} <small>{v.unit}</small></div>
              </div>
            ))}
          </div>
          {targets.trace.provisional && <p className="warn" style={{ margin: 0 }}>{t("profile.provisional")}</p>}
          <details><summary>{t("profile.how")}</summary><pre>{JSON.stringify(targets.trace, null, 2)}</pre></details>
        </div>
      )}
    </div>
  );
}
