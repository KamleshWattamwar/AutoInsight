export default function OverviewCards({ result }) {
  const ov = result.overview;
  const cards = [
    ["Rows", ov.rows.toLocaleString()],
    ["Columns", ov.columns],
    ["Duplicate rows", ov.duplicate_rows],
    ["Missing values", `${ov.total_missing_pct}%`],
    ["Quality score", `${result.quality_score}/100`],
  ];

  return (
    <section className="card">
      <h2>Overview</h2>
      <div className="stats">
        {cards.map(([label, value]) => (
          <div className="stat" key={label}>
            <div className="stat-value">{value}</div>
            <div className="muted">{label}</div>
          </div>
        ))}
      </div>
      {result.warnings.map((w) => (
        <p className="warning" key={w}>{w}</p>
      ))}
    </section>
  );
}