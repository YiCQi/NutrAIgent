import { useCallback, useEffect, useState } from "react";
import { api, todayISO } from "./api.js";

const STATUS_LABEL = {
  ok: "OK", low: "Low", deficient: "Deficient", excess: "Excess", unknown: "Unknown (data missing)", ok_incomplete: "OK so far (data missing)",
};

export default function LogTab({ refreshKey }) {
  const [date, setDate] = useState(todayISO());
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setErr("");
    api.getIntake(date).then(setData).catch((e) => setErr(e.message));
  }, [date]);
  useEffect(load, [load, refreshKey]);

  const del = async (id) => { await api.deleteIntake(id); load(); };

  return (
    <section>
      <h2>Daily log</h2>
      <label>Date <input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
      {err && <p className="err">{err}</p>}
      {data && (
        <>
          <h3>Entries</h3>
          {data.entries.length === 0 ? <p className="muted">Nothing logged.</p> : (
            <table>
              <thead><tr><th>Meal</th><th>Food</th><th>Grams</th><th /></tr></thead>
              <tbody>
                {data.entries.map((e) => (
                  <tr key={e.id}><td>{e.meal}</td><td>{e.name}</td><td>{e.grams}</td>
                    <td><button className="link" onClick={() => del(e.id)}>remove</button></td></tr>
                ))}
              </tbody>
            </table>
          )}
          <h3>Intake vs targets</h3>
          {data.comparison ? (
            <table>
              <thead><tr><th>Nutrient</th><th>Intake</th><th>Target</th><th>%</th><th>Status</th></tr></thead>
              <tbody>
                {data.comparison.map((c) => (
                  <tr key={c.nutrient} className={`st-${c.status}`}>
                    <td>{c.nutrient}{c.kind === "max" ? " (max)" : ""}</td>
                    <td>{c.intake} {c.unit}</td><td>{c.target} {c.unit}</td><td>{c.percent ?? "—"}</td>
                    <td>{STATUS_LABEL[c.status] ?? c.status}{c.incomplete_data && c.status !== "unknown" && c.status !== "ok_incomplete" ? " — some foods lack data" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">Save a profile to compare against targets.</p>}
          <details>
            <summary>All nutrient totals</summary>
            <table>
              <thead><tr><th>Nutrient</th><th>Total</th><th>Entries missing data</th></tr></thead>
              <tbody>
                {Object.entries(data.totals).map(([k, t]) => (
                  <tr key={k}><td>{k}</td><td>{t.value} {t.unit}</td><td>{t.missing_entries.length}</td></tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </section>
  );
}
