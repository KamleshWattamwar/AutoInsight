import { useEffect, useState } from "react";
import { health } from "./api";
import UploadPanel from "./components/UploadPanel";
import "./index.css";

export default function App() {
  const [api, setApi] = useState("checking...");
  const [dataset, setDataset] = useState(null); // {dataset_id, rows, columns}
  const [report, setReport] = useState(null); // full report with result

  useEffect(() => {
    health()
      .then((r) => setApi(r.status))
      .catch(() => setApi("unreachable"));
  }, []);

  function handleDone(newDataset, newReport) {
    setDataset(newDataset);
    setReport(newReport);
  }

  return (
    <main className="page">
      <h1>AutoInsight</h1>
      <p className="muted">API: {api}</p>

      <UploadPanel onDone={handleDone} />

      {report && (
        <section className="card">
          <h2>Analysis finished</h2>
          <p>
            {dataset.rows} rows, {dataset.columns} columns. Quality score:{" "}
            {report.result.quality_score}/100. Findings: {report.result.findings.length}.
          </p>
        </section>
      )}
    </main>
  );
}
