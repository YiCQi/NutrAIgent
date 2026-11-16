import { useEffect, useState } from "react";

const today = () => new Date().toISOString().slice(0, 10);

export default function App() {
  const [health, setHealth] = useState("checking...");
  const [intake, setIntake] = useState(null);

  useEffect(() => {
    fetch("/api/health").then((r) => r.json()).then((d) => setHealth(d.status)).catch(() => setHealth("backend offline"));
    fetch(`/api/intake/${today()}`).then((r) => r.json()).then(setIntake).catch(() => {});
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", maxWidth: 720, margin: "2rem auto", padding: "0 1rem" }}>
      <h1>NutrAIgent</h1>
      <p>Backend: {health}</p>
      <h2>Today ({today()})</h2>
      {intake?.comparison ? (
        <table>
          <thead><tr><th>Nutrient</th><th>Intake</th><th>Target</th><th>Status</th></tr></thead>
          <tbody>
            {intake.comparison.map((c) => (
              <tr key={c.nutrient}>
                <td>{c.nutrient}</td><td>{c.intake} {c.unit}</td><td>{c.target} {c.unit}</td>
                <td>{c.status}{c.incomplete_data ? " (incomplete data)" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>Set up a profile to see targets. (Profile form: TODO)</p>
      )}
    </main>
  );
}
