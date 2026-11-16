import { useEffect, useState } from "react";
import ProfileTab from "./ProfileTab.jsx";
import FoodsTab from "./FoodsTab.jsx";
import LogTab from "./LogTab.jsx";
import "./styles.css";

const TABS = ["Log", "Foods", "Profile"];

export default function App() {
  const [tab, setTab] = useState("Log");
  const [health, setHealth] = useState("checking…");
  const [refreshKey, setRefreshKey] = useState(0);
  const bump = () => setRefreshKey((k) => k + 1);

  useEffect(() => {
    fetch("/api/health").then((r) => r.json()).then((d) => setHealth(d.status)).catch(() => setHealth("backend offline"));
  }, []);

  return (
    <main>
      <header>
        <h1>NutrAIgent</h1>
        <span className={health === "ok" ? "ok" : "err"}>backend: {health}</span>
      </header>
      <nav>
        {TABS.map((t) => (
          <button key={t} className={t === tab ? "active" : ""} onClick={() => setTab(t)}>{t}</button>
        ))}
      </nav>
      {tab === "Profile" && <ProfileTab onSaved={bump} />}
      {tab === "Foods" && <FoodsTab onLogged={bump} />}
      {tab === "Log" && <LogTab refreshKey={refreshKey} />}
    </main>
  );
}
