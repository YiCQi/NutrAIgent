import { useEffect, useState } from "react";
import { I18nProvider, useI18n } from "./i18n.jsx";
import { Icon } from "./ui.jsx";
import TodayPage from "./pages/TodayPage.jsx";
import AssistantPage from "./pages/AssistantPage.jsx";
import FoodsPage from "./pages/FoodsPage.jsx";
import RecipesPage from "./pages/RecipesPage.jsx";
import PlanPage from "./pages/PlanPage.jsx";
import ProfilePage from "./pages/ProfilePage.jsx";
import "./app.css";

const NAV = [
  ["today", "today", "nav.today"],
  ["assistant", "sparkle", "nav.assistant"],
  ["plan", "calendar", "nav.plan"],
  ["foods", "search", "nav.foods"],
  ["recipes", "book", "nav.recipes"],
  ["profile", "user", "nav.profile"],
];

function LangSwitch() {
  const { lang, setLang } = useI18n();
  return (
    <div className="seg" role="group" aria-label="language">
      <button className={lang === "zh" ? "on" : ""} onClick={() => setLang("zh")}>中文</button>
      <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button>
    </div>
  );
}

function Shell() {
  const { t } = useI18n();
  const [page, setPage] = useState(() => { try { return localStorage.getItem("page") || "today"; } catch { return "today"; } });
  const [online, setOnline] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const bump = () => setRefreshKey((k) => k + 1);
  const go = (p) => { setPage(p); try { localStorage.setItem("page", p); } catch {} };

  useEffect(() => {
    const ping = () => fetch("/api/health").then((r) => setOnline(r.ok)).catch(() => setOnline(false));
    ping();
    const id = setInterval(ping, 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="app">
      <nav className="sidebar">
        <div className="brand"><span className="logo"><Icon name="leaf" size={20} /></span>NutrAIgent</div>
        {NAV.map(([id, icon, label]) => (
          <button key={id} className={`nav-item ${page === id ? "active" : ""}`} onClick={() => go(id)}>
            <Icon name={icon} /> <span>{t(label)}</span>
          </button>
        ))}
        <div className="spacer" />
        <div className="side-foot">
          <LangSwitch />
          <span><span className={`dot ${online ? "" : "off"}`} />{online ? t("app.online") : t("app.offline")}</span>
        </div>
      </nav>
      <main>
        <div className="topbar-mobile"><strong>NutrAIgent</strong><LangSwitch /></div>
        {!online && <div className="content" style={{ paddingBottom: 0 }}><div className="banner" style={{ background: "var(--danger-soft)", color: "var(--danger)" }}>{t("app.offline")}</div></div>}
        <div className="content">
          {page === "today" && <TodayPage refreshKey={refreshKey} go={go} />}
          {/* Assistant and Plan stay mounted (hidden) so a running request keeps its progress UI */}
          <div hidden={page !== "assistant"}><AssistantPage onLogged={bump} /></div>
          <div hidden={page !== "plan"}><PlanPage onLogged={bump} go={go} /></div>
          {page === "foods" && <FoodsPage onLogged={bump} />}
          {page === "recipes" && <RecipesPage />}
          {page === "profile" && <ProfilePage onSaved={bump} />}
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return <I18nProvider><Shell /></I18nProvider>;
}
