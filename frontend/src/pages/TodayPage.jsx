import { useCallback, useEffect, useState } from "react";
import { api, todayISO } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { Bar, Icon, Ring } from "../ui.jsx";
import RecommendCard from "./RecommendCard.jsx";

const MEALS = ["breakfast", "lunch", "dinner", "snack", "other"];
const MACROS = [["protein_g", "var(--protein)"], ["carbohydrate_g", "var(--carbs)"], ["fat_g", "var(--fat)"]];
// Must match backend app/estimate.py ESTIMATE_CODES.
const ESTIMATE_CODES = ["calcium_mg", "iron_mg", "vitamin_c_mg", "vitamin_b12_ug",
  "ala_g", "epa_g", "dha_g", "linoleic_g", "cholesterol_mg", "potassium_mg", "magnesium_mg",
  "phosphorus_mg", "zinc_mg", "selenium_ug", "iodine_ug", "vitamin_a_ug", "vitamin_d_ug",
  "vitamin_e_mg", "vitamin_k_ug", "folate_ug"];

// Main nutrients shown by default; everything else appears under "show all".
const CORE_CODES = ["energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fibre_g", "sugars_g", "sat_fat_g",
  "sodium_mg", "calcium_mg", "iron_mg", "vitamin_c_mg", "vitamin_b12_ug"];

const unitLabel = (u) => (u === "ug" ? "µg" : u);
const fmtAmt = (v) => (v >= 10 ? Math.round(v) : Number(v.toFixed(2)));

// Hover/focus popover listing which logged foods contribute to one nutrient.
function SourceTip({ entries, code, unit, children }) {
  const { t, nutrient } = useI18n();
  const rows = entries.filter((e) => e.nutrients?.[code] != null)
    .sort((a, b) => b.nutrients[code] - a.nutrients[code]);
  const missing = entries.length - rows.length;
  return (
    <span className="src" tabIndex={0}>
      {children}
      <span className="src-pop" role="tooltip">
        <strong>{t("today.sourcesOf", { n: nutrient(code) })}</strong>
        {rows.length === 0 ? <small>{t("today.noSources")}</small> : (
          <ul>
            {rows.map((e) => (
              <li key={e.id}>
                <span className="name">{e.name}</span>
                <small>{e.grams} {t("common.g")}</small>
                <span className="amt">{fmtAmt(e.nutrients[code])} {unit}</span>
              </li>
            ))}
          </ul>
        )}
        {missing > 0 && <small className="warn">{t("today.sourcesMissing", { n: missing })}</small>}
      </span>
    </span>
  );
}

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
  const [editing, setEditing] = useState(null);
  const [editVal, setEditVal] = useState("");
  const [editErr, setEditErr] = useState("");
  const startEdit = (e) => { setEditing(e.id); setEditVal(String(e.grams)); setEditErr(""); };
  const cancelEdit = () => { setEditing(null); setEditErr(""); };
  const [logFolded, setLogFolded] = useState(false);
  const saveGrams = async (id) => {
    const g = Number(editVal);
    if (!(g > 0)) { setEditErr(t("today.gramsInvalid")); return; }
    try { await api.editIntake(id, g); cancelEdit(); load(); }
    catch (e) { setEditErr(e.message); }
  };
  const [estBusy, setEstBusy] = useState(false);
  const [showAllNut, setShowAllNut] = useState(false);
  const [estMsg, setEstMsg] = useState("");
  const estimate = async () => {
    setEstBusy(true); setEstMsg("");
    try {
      const r = await api.estimateIntake(date);
      setEstMsg(r.foods === 0 ? t("today.estimateNone") : t("today.estimated", { n: r.stored }));
      load();
    } catch (e) { setEstMsg(e.message); }
    setEstBusy(false);
  };
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
                  <SourceTip entries={data.entries} code={code} unit={data.totals[code]?.unit ?? "g"}>
                    <div className="top">
                      <span>{nutrient(code)}</span>
                      <span><strong>{Math.round(data.totals[code]?.value ?? 0)}</strong>{cmp[code] ? ` / ${Math.round(cmp[code].target)}` : ""} g</span>
                    </div>
                    <Bar value={data.totals[code]?.value ?? 0} max={cmp[code]?.target ?? 0} color={color} />
                  </SourceTip>
                </div>
              ))}
            </div>
          </div>

          <RecommendCard date={date} refreshKey={refreshKey} />

          {data.entries.length > 0 && (
            <div className="card">
              <details open>
                <summary>{t("today.details")}</summary>
                {Object.values(data.totals).some((tot) => tot.estimated) && (
                  <div className="ai-notice">{t("today.aiNotice")}</div>
                )}
                {ESTIMATE_CODES.some((c) => data.totals[c]?.missing_entries.length > 0) && (
                  <div className="row" style={{ flexWrap: "wrap", gap: 8, marginTop: 8 }}>
                    <button className="btn sm ghost" onClick={estimate} disabled={estBusy}>
                      <Icon name="sparkle" size={16} />{estBusy ? t("today.estimating") : t("today.estimate")}
                    </button>
                    <small>{estMsg || t("today.estimateHint")}</small>
                  </div>
                )}
                <table style={{ marginTop: 8 }}>
                  <thead><tr><th /><th className="num">{t("today.intake")}</th><th className="num">{t("today.targetCol")}</th><th style={{ width: "26%" }} /><th /></tr></thead>
                  <tbody>
                    {Object.entries(data.totals).filter(([code]) => showAllNut || CORE_CODES.includes(code)).map(([code, tot]) => {
                      const c = cmp[code];
                      return (
                        <tr key={code}>
                          <td><SourceTip entries={data.entries} code={code} unit={tot.unit}>{nutrient(code)}</SourceTip>{c?.kind === "max" ? <small> ({t("today.max")})</small> : null}{tot.estimated ? <span className="chip predicted" style={{ marginLeft: 6 }}>{t("today.aiPredicted")}</span> : null}</td>
                          <td className="num">{tot.value} {unitLabel(tot.unit)}</td>
                          <td className="num">{c ? `${c.target} ${unitLabel(c.unit)}` : "—"}</td>
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
                <button className="btn sm ghost" style={{ marginTop: 8 }} onClick={() => setShowAllNut((v) => !v)}>
                  {showAllNut ? t("today.showCore") : t("today.showAll")}
                </button>
                <small>{t("today.incomplete")}</small>
              </details>
            </div>
          )}

          <div className="card">
            <div className="page-head" style={{ marginBottom: 8 }}>
              <div className="row">
                <button className="icon-btn" onClick={() => setLogFolded((f) => !f)} aria-expanded={!logFolded}
                        title={t(logFolded ? "common.expand" : "common.collapse")}><Icon name={logFolded ? "down" : "up"} size={18} /></button>
                <h3>{t("today.entries")}</h3>
              </div>
              <div className="row">
                <button className="btn sm" onClick={() => go("assistant")}><Icon name="sparkle" size={16} />{t("today.addAi")}</button>
                <button className="btn sm ghost" onClick={() => go("foods")}><Icon name="search" size={16} />{t("today.addSearch")}</button>
              </div>
            </div>
            <div hidden={logFolded}>
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
                      {editing === e.id ? (
                        <span className="grams-edit">
                          <input type="number" min="0" step="any" autoFocus value={editVal}
                                 onChange={(ev) => setEditVal(ev.target.value)}
                                 onKeyDown={(ev) => { if (ev.key === "Enter") saveGrams(e.id); if (ev.key === "Escape") cancelEdit(); }} />
                          <span>{t("common.g")}</span>
                          <button className="btn sm" onClick={() => saveGrams(e.id)}>{t("common.save")}</button>
                          <button className="btn sm ghost" onClick={cancelEdit}>{t("common.cancel")}</button>
                          {editErr && <small className="err">{editErr}</small>}
                        </span>
                      ) : (
                        <button className="grams-btn" title={t("common.edit")} onClick={() => startEdit(e)}>{e.grams} {t("common.g")}</button>
                      )}
                      <span className="kcal">{e.nutrients?.energy_kcal == null ? "—" : Math.round(e.nutrients.energy_kcal)} <small>kcal</small></span>
                      <button className="icon-btn" title={t("common.remove")} onClick={() => del(e.id)}><Icon name="x" size={16} /></button>
                    </div>
                  ))}
                </div>
              );
            })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
