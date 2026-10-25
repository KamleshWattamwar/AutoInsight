export default function FindingsList({ findings, narrative }) {
  // index in narrative.findings = position in the findings list (first 15 only)
  const explain = {};
  narrative?.findings.forEach((f) => {
    if (f.source === "llm") explain[f.index] = f.text;
  });

  return (
    <section className="card">
      <h2>Findings ({findings.length})</h2>
      {findings.length === 0 && <p className="muted">No issues found.</p>}
      {findings.map((f, i) => (
        <div className="finding" key={i}>
          <span className={`badge ${f.severity}`}>{f.severity}</span>
          <div>
            <div>{f.message}</div>
            {f.columns.length > 0 && <div className="muted">Columns: {f.columns.join(", ")}</div>}
            {explain[i] && <div className="explain">{explain[i]}</div>}
          </div>
        </div>
      ))}
    </section>
  );
}