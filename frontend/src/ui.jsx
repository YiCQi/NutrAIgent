const PATHS = {
  today: "M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
  search: "M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-4.3-4.3",
  book: "M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2zM4 19a2 2 0 012-2h13",
  user: "M20 21a8 8 0 10-16 0M12 13a4 4 0 100-8 4 4 0 000 8z",
  plus: "M12 5v14M5 12h14",
  x: "M6 6l12 12M18 6L6 18",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  left: "M15 6l-6 6 6 6",
  right: "M9 6l6 6-6 6",
  calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  leaf: "M5 19c0-9 5-14 15-14 0 10-5 15-14 15M5 19l7-7",
};

export function Icon({ name, size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={PATHS[name]} /></svg>
  );
}

export function Ring({ value, max, size = 168, stroke = 14, children }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = max > 0 ? Math.min(value / max, 1) : 0;
  const over = max > 0 && value > max;
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={over ? "var(--danger)" : "var(--accent)"} strokeWidth={stroke}
                strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct)} style={{ transition: "stroke-dashoffset .5s" }} />
      </svg>
      <div className="center">{children}</div>
    </div>
  );
}

export function Bar({ value, max, color = "var(--accent)", className = "" }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return <div className={`bar ${className}`}><span style={{ width: `${pct}%`, background: color }} /></div>;
}
