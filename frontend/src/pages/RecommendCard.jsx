import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { Icon } from "../ui.jsx";

// Diet suggestions for one day: what is still short (with yesterday carry-over), and stored AI options whose
// numbers were computed from the food database by the backend.
export default function RecommendCard({ date, refreshKey }) {
  const { t, lang, nutrient } = useI18n();
  const [data, setData] = useState(null);
  const [hidden, setHidden] = useState(false);
  const [folded, setFolded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    api.getRecommendation(date)
      .then((d) => { setData(d); setHidden(false); })
      .catch((e) => { if (e.status === 409) setHidden(true); else setErr(e.message); });
  }, [date]);
  useEffect(load, [load, refreshKey]);

  // a generation started earlier (page switch, reload) is still running on the server: poll until it ends
  useEffect(() => {
    if (!data?.pending || busy) return undefined;
    const id = setTimeout(load, 3000);
    return () => clearTimeout(id);
  }, [data, busy, load]);

  const generate = async () => {
    setBusy(true); setErr("");
    try {
      await api.generateRecommendation(date, lang, () => {});
    } catch (e) {
      setErr(e.message);
    }
    setBusy(false);
    load();
  };

  if (hidden || !data) return null;
  const { live, stored, stale } = data;
  const pending = busy || data.pending;

  return (
    <div className="card">
      <div className="page-head" style={{ marginBottom: 8 }}>
        <div className="row">
          <button className="icon-btn" onClick={() => setFolded((f) => !f)} aria-expanded={!folded}
                  title={t(folded ? "common.expand" : "common.collapse")}><Icon name={folded ? "down" : "up"} size={18} /></button>
          <h3>{t("rec.title")}</h3>
        </div>
        <button className="btn sm" onClick={generate} disabled={pending}>
          <Icon name="sparkle" size={16} />{pending ? t("rec.busy") : stored ? t("rec.regenerate") : t("rec.generate")}
        </button>
      </div>
      <div hidden={folded}>
      <small>{t("rec.hint")}</small>

      {live.short.length === 0 ? (
        <p className="ok-text" style={{ margin: "8px 0" }}>{t("rec.noShort")}</p>
      ) : (
        <div className="row" style={{ flexWrap: "wrap", gap: 6, margin: "10px 0" }}>
          {live.short.map((s) => (
            <span key={s.nutrient} className={`chip ${s.repeated ? "deficient" : "low"}`}>
              {nutrient(s.nutrient)} · {t("rec.lacks", { n: s.gap, unit: s.unit })}{s.repeated ? ` · ${t("rec.repeat")}` : ""}
            </span>
          ))}
        </div>
      )}
      {live.excess.length > 0 && (
        <p className="warn" style={{ margin: "4px 0" }}>{t("rec.excess")}: {live.excess.map((x) => nutrient(x.nutrient)).join(", ")}</p>
      )}
      {live.unknown.length > 0 && (
        <small className="muted" style={{ display: "block" }}>{t("rec.unknown")}: {live.unknown.map((c) => nutrient(c)).join(", ")}</small>
      )}
      {live.yesterday.logged && live.yesterday.short.length > 0 && (
        <small className="muted" style={{ display: "block" }}>
          {t("rec.yesterday")}: {live.yesterday.short.map((c) => nutrient(c)).join(", ")}
        </small>
      )}

      {stale && <p className="warn" style={{ margin: "8px 0 0" }}>{t("rec.stale")}</p>}
      {stored && (
        <div style={{ marginTop: 10 }}>
          <small className="muted">{t("rec.generatedAt", { when: data.created_at })}</small>
          {stored.options.length === 0 ? (
            <p className="muted">{t("rec.none")}</p>
          ) : stored.options.map((o, i) => (
            <div className="proposal" key={i} style={{ marginTop: 8 }}>
              <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
                <strong>{o.title || t("rec.option")}</strong>
                <small className="muted">{t(`meal.${o.meal}`)}{o.kcal != null ? ` · ${o.kcal} kcal` : ""}</small>
              </div>
              <table style={{ marginTop: 6 }}>
                <tbody>
                  {o.items.map((it, k) => (
                    <tr key={k}>
                      <td>{it.label} <small className="muted">{it.food_name}</small></td>
                      <td className="num">{it.grams} {t("common.g")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="row" style={{ flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                {Object.entries(o.covers_short_percent).filter(([, p]) => p != null).map(([c, p]) => (
                  <span key={c} className="chip ok">{nutrient(c)} {Math.round(p)}%</span>
                ))}
              </div>
              {o.exceeds_energy_left && <small className="err" style={{ display: "block", marginTop: 4 }}>{t("rec.overBudget")}</small>}
              {o.over_limit.length > 0 && (
                <small className="err" style={{ display: "block", marginTop: 4 }}>
                  {t("rec.limitWarn", { x: o.over_limit.map((c) => nutrient(c)).join(", ") })}
                </small>
              )}
            </div>
          ))}
        </div>
      )}
      {err && <p className="err" style={{ margin: "8px 0 0" }}>{err}</p>}
      </div>
    </div>
  );
}
