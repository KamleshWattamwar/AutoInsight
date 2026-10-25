import { useEffect, useState } from "react";
import { health } from "./api";
import UploadPanel from "./components/UploadPanel";
import OverviewCards from "./components/OverviewCards";
import NarrativePanel from "./components/NarrativePanel";
import FindingsList from "./components/FindingsList";
import "./index.css";

export default function App() {
  const [api, setApi] = useState("checking...");
  const [dataset, setDataset] = useState(null); // {dataset_id, rows, columns}
  const [report, setReport] = useState(null); // full report with result
  const [narrative, setNarrative] = useState(null);

  useEffect(() => {
    health()
      .then((r) => setApi(r.status))
      .catch(() => setApi("unreachable"));
  }, []);

  function handleDone(newDataset, newReport) {
    setDataset(newDataset);
    setReport(newReport);
    setNarrative(newReport.narrative);
  }

  return (
    <main className="page">
      <h1>AutoInsight</h1>
      <p className="muted">API: {api}</p>

      <UploadPanel onDone={handleDone} />

      {report && (
        <>
          <OverviewCards result={report.result} />
          <NarrativePanel
            key={report.report_id}
            reportId={report.report_id}
            narrative={narrative}
            onNarrative={setNarrative}
          />
          <FindingsList findings={report.result.findings} narrative={narrative} />
        </>
      )}
    </main>
  );
}