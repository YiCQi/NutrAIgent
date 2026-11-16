import { useCallback, useEffect, useState } from "react";
import { api, todayISO } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { Bar, Icon, Ring } from "../ui.jsx";
import RecommendCard from "./RecommendCard.jsx";

const MEALS = ["breakfast", "lunch", "dinner", "snack", "other"];
const MACROS = [["protein_g", "var(--protein)"], ["carbohydrate_g", "var(--carbs)"], ["fat_g", "var(--fat)"]];

const shiftDate = (iso, days) => {
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() + days);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

export default function TodayPage({ refreshKey, go }) {
  const { t, lang, nutrient } = useI18n();
  const [date, setDate] = useState(todayISO());
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setErr("");
    api.getIntake(date).then(setData).catch((e) => setErr(e.message));
  }, [date]);
  useEffect(load, [load, refreshKey]);

  const del = async (id) => { await api.deleteIntake(id); load(); };
  const cmp = {};
  (data?.comparison || []).forEach((c) => { cmp[c.nutrient] = c; });
  const eaten = data?.totals?.energy_kcal?.value ?? 0;
  const target = cmp.energy_kcal?.target;
  const heading = new Date(date + "T12:00:00").toLocaleDateString(lang === "zh" ? "zh-CN" : "en-GB",
    { weekday: "long", month: "long", day: "numeric" });

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h2>{date === todayISO() ? t("common.today") : heading}</h2>
          {date === todayISO() && <small>{heading}</small>}
        </div>
        <div className="date-nav">
          <button className="icon-btn" onClick={() => setDate(shiftDate(date, -1))}><Icon name="left" /></button>
          <input type="date" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} />
          <button className="icon-btn" onClick={() => setDate(shiftDate(date, 1))}><Icon name="right" /></button>
        </div>
      </div>

      {err && <p className="err">{err}</p>}
      {data && !data.comparison && (
        <div className="banner"><span>{t("today.needProfile")}</span>
          <button className="btn sm" onClick={() => go("profile")}>{t("today.setProfile")}</button></div>
      )}

      {data && (
        <>
          <div className="card hero">
            <Ring value={eaten} max={target || 0}>
              <div className="big">{Math.round(eaten)}</div>
              <small>{t("today.eaten")} · kcal</small>
            </Ring>
            <div className="macros">
              {target ? (
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <strong>{t("today.target")}: {Math.round(target)} kcal</strong>
                  <span className={eaten > target ? "err" : "muted"}>
                    {eaten > target ? t("today.over", { n: Math.round(eaten - target) }) : t("today.remaining", { n: Math.round(target - eaten) })}
                  </span>
                </div>
              ) : null}
              {MACROS.map(([code, color]) => (
                <div className="macro" key={code}>
                  <div className="top">
                    <span>{nutrient(code)}</span>
                    <span><strong>{Math.round(data.totals[code]?.value ?? 0)}</strong>{cmp[code] ? ` / ${Math.round(cmp[code].target)}` : ""} g</span>
                  </div>
                  <Bar value={data.totals[code]?.value ?? 0} max={cmp[code]?.target ?? 0} color={color} />
                </div>
              ))}
            </div>
          </div>

          <RecommendCard date={date} refreshKey={refreshKey} />

          <div className="card">
            <div className="page-head" style={{ marginBottom: 8 }}>
              <h3>{t("today.entries")}</h3>
              <div className="row">
                <button className="btn sm" onClick={() => go("assistant")}><Icon name="sparkle" size={16} />{t("today.addAi")}</button>
                <button className="btn sm ghost" onClick={() => go("foods")}><Icon name="search" size={16} />{t("today.addSearch")}</button>
              </div>
            </div>
            {data.entries.length === 0 ? (
              <div className="empty"><strong>{t("today.empty")}</strong>{t("today.emptyHint")}</div>
            ) : MEALS.map((m) => {
              const items = data.entries.filter((e) => e.meal === m);
              if (!items.length) return null;
              const sum = items.reduce((a, e) => a + (e.nutrients?.energy_kcal ?? 0), 0);
              return (
                <div className="meal-block" key={m}>
                  <div className="meal-head"><h3>{t(`meal.${m}`)}</h3><small>{Math.round(sum)} kcal</small></div>
                  {items.map((e) => (
                    <div className="entry" key={e.id}>
                      <span className="name" title={e.name}>{e.name}</span>
                      <small>{e.grams} {t("common.g")}</small>
                      <span className="kcal">{e.nutrients?.energy_kcal == null ? "—" : Math.round(e.nutrients.energy_kcal)} <small>kcal</small></span>
                      <button className="icon-btn" title={t("common.remove")} onClick={() => del(e.id)}><Icon name="x" size={16} /></button>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>

          {data.entries.length > 0 && (
            <div className="card">
              <details open>
                <summary>{t("today.details")}</summary>
                <table style={{ marginTop: 8 }}>
                  <thead><tr><th /><th className="num">{t("today.intake")}</th><th className="num">{t("today.targetCol")}</th><th style={{ width: "26%" }} /><th /></tr></thead>
                  <tbody>
                    {Object.entries(data.totals).map(([code, tot]) => {
                      const c = cmp[code];
                      return (
                        <tr key={code}>
                          <td>{nutrient(code)}{c?.kind === "max" ? <small> ({t("today.max")})</small> : null}</td>
                          <td className="num">{tot.value} {tot.unit}</td>
                          <td className="num">{c ? `${c.target} ${c.unit}` : "—"}</td>
                          <td>{c ? <Bar className="minibar" value={tot.value} max={c.target} color={c.status === "excess" ? "var(--danger)" : "var(--accent)"} /> : null}</td>
                          <td>
                            {c ? <span className={`chip ${c.status}`}>{t(`status.${c.status}`)}</span> : tot.missing_entries.length ? <span className="chip unknown">{t("status.unknown")}</span> : null}
                            {tot.missing_entries.length > 0 && c && c.status !== "unknown" ? <small title={t("today.incomplete")}> ⚠</small> : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <small>{t("today.incomplete")}</small>
              </details>
            </div>
          )}
        </>
      )}
    </div>
  );
}
