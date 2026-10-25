import { useState } from "react";
import { createNarrative } from "../api";

const SOURCE_LABEL = {
  llm: "AI-written. Every number was checked against the findings.",
  mixed: "Partly AI-written. Sentences that failed the number check use rule-based text.",
  rules: "Rule-based summary (the AI explanation was unavailable).",
};

export default function NarrativePanel({ reportId, narrative, onNarrative }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function generate() {
    setBusy(true);
    setError("");
    try {
      const res = await createNarrative(reportId);
      onNarrative(res.narrative);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Plain-English summary</h2>
      {narrative && (
        <>
          <p className="summary">{narrative.summary}</p>
          <p className="muted">{SOURCE_LABEL[narrative.source]}</p>
        </>
      )}
      <button onClick={generate} disabled={busy}>
        {busy ? "Generating (can take up to a minute)..." : narrative ? "Regenerate" : "Generate summary"}
      </button>
      {error && <p className="error">{error}</p>}
    </section>
  );
}