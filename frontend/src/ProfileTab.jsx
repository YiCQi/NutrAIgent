import { useEffect, useState } from "react";
import { api } from "./api.js";

const EMPTY = { age: 30, sex: "male", height_cm: 175, weight_kg: 70, activity_level: "light", goal: "maintenance", dietary_preferences: [] };
const ACTIVITY = ["sedentary", "light", "moderate", "active", "very_active"];
const GOALS = ["fat_loss", "maintenance", "muscle_gain"];

export default function ProfileTab({ onSaved }) {
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
    e.preventDefault();
    setErr(""); setMsg("");
    try {
      await api.putProfile({ ...form, dietary_preferences: prefs.split(",").map((s) => s.trim()).filter(Boolean) });
      await loadTargets();
      setMsg("Saved.");
      onSaved?.();
    } catch (e2) {
      setErr(e2.message);
    }
  };

  return (
    <section>
      <h2>Profile</h2>
      <form onSubmit={save} className="grid">
        <label>Age<input type="number" value={form.age} onChange={set("age")} /></label>
        <label>Sex
          <select value={form.sex} onChange={set("sex")}><option>male</option><option>female</option></select>
        </label>
        <label>Height (cm)<input type="number" step="0.1" value={form.height_cm} onChange={set("height_cm")} /></label>
        <label>Weight (kg)<input type="number" step="0.1" value={form.weight_kg} onChange={set("weight_kg")} /></label>
        <label>Activity
          <select value={form.activity_level} onChange={set("activity_level")}>{ACTIVITY.map((a) => <option key={a}>{a}</option>)}</select>
        </label>
        <label>Goal
          <select value={form.goal} onChange={set("goal")}>{GOALS.map((a) => <option key={a}>{a}</option>)}</select>
        </label>
        <label className="wide">Dietary preferences (comma separated)
          <input value={prefs} onChange={(e) => setPrefs(e.target.value)} />
        </label>
        <button type="submit">Save profile</button>
      </form>
      {msg && <p className="ok">{msg}</p>}
      {err && <p className="err">{err}</p>}

      {targets && (
        <>
          <h3>Daily targets</h3>
          <table>
            <thead><tr><th>Nutrient</th><th>Value</th><th>Type</th></tr></thead>
            <tbody>
              {Object.entries(targets.targets).map(([k, t]) => (
                <tr key={k}><td>{k}</td><td>{t.value} {t.unit}</td><td>{t.kind === "max" ? "limit (max)" : "target"}</td></tr>
              ))}
            </tbody>
          </table>
          <details>
            <summary>How these were calculated</summary>
            <pre>{JSON.stringify(targets.trace, null, 2)}</pre>
          </details>
          {targets.trace.provisional && <p className="warn">Defaults are provisional (unreviewed reference standards).</p>}
        </>
      )}
    </section>
  );
}
