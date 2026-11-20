import { useState } from "react";
import { api } from "../api.js";
import { useI18n } from "../i18n.jsx";

// Proposed changes to today's logged intake (from the chat). Nothing is applied until the user confirms.
export default function EditProposals({ message, onSaved }) {
  const { t } = useI18n();
  const changes = message.meta.changes || [];
  const [include, setInclude] = useState(() => changes.map(() => true));
  const [status, setStatus] = useState(message.meta.status || "pending");
  const [results, setResults] = useState(message.meta.results || []);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const describe = (c) => {
    if (c.action === "delete") return t("edit.del", { name: c.name, old: c.old_grams });
    if (c.action === "grams") return t("edit.grams", { name: c.name, old: c.old_grams, new: c.new_grams });
    return t("edit.meal", { name: c.name, meal_old: t(`meal.${c.old_meal}`), meal_new: t(`meal.${c.new_meal}`) });
  };

  const apply = async () => {
    setErr(""); setBusy(true);
    try {
      const chosen = include.map((on, i) => (on ? i : -1)).filter((i) => i >= 0);
      const r = await api.confirmEdits(message.id, chosen);
      setResults(r.results || []); setStatus("saved"); onSaved?.();
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const discard = async () => { await api.setProposalStatus(message.id, "discarded"); setStatus("discarded"); };

  if (status === "saved") {
    const skipped = results.some((x) => x.result === "skipped");
    return <p className="ok-text" style={{ margin: "8px 0 0" }}>✓ {t("edit.applied")}{skipped ? ` · ${t("edit.skipped")}` : ""}</p>;
  }
  if (status === "discarded") return <p className="muted" style={{ margin: "8px 0 0" }}>{t("assistant.discarded")}</p>;

  const count = include.filter(Boolean).length;
  return (
    <div>
      <small style={{ display: "block", marginTop: 8 }}>{t("edit.hint")}</small>
      <div className="proposal">
        <table>
          <tbody>
            {changes.map((c, i) => (
              <tr key={i}>
                <td><input type="checkbox" checked={include[i]} onChange={(e) => setInclude((xs) => xs.map((x, j) => (j === i ? e.target.checked : x)))} /></td>
                <td>{describe(c)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn" onClick={apply} disabled={busy || count === 0}>{t("edit.apply", { n: count })}</button>
        <button className="btn ghost" onClick={discard} disabled={busy}>{t("assistant.discard")}</button>
      </div>
      {err && <p className="err" style={{ margin: "8px 0 0" }}>{err}</p>}
    </div>
  );
}
