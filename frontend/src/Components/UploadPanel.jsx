import { useEffect, useRef, useState } from "react";
import { analyze, getReport, uploadDataset } from "../api";

const POLL_MS = 1000;
const MAX_POLLS = 120; // 2 minutes, then give up (a stuck report must not spin forever)

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export default function UploadPanel({ onDone }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false; // stops the polling loop after unmount
    };
  }, []);

  async function handleFile(e) {
    const input = e.target;
    const file = input.files[0];
    if (!file) return;

    setBusy(true);
    setError("");
    try {
      setMessage("Uploading...");
      const dataset = await uploadDataset(file);

      setMessage("Analyzing...");
      const { report_id } = await analyze(dataset.dataset_id);

      for (let i = 0; i < MAX_POLLS; i++) {
        await sleep(POLL_MS);
        if (!alive.current) return;
        const report = await getReport(report_id);
        if (report.status === "done") {
          setMessage("Done");
          onDone(dataset, report);
          return;
        }
        if (report.status === "failed") {
          throw new Error(report.error ?? "Analysis failed");
        }
      }
      throw new Error("Analysis is taking too long. Please try again later.");
    } catch (err) {
      if (alive.current) {
        setMessage("");
        setError(err.message);
      }
    } finally {
      if (alive.current) setBusy(false);
      input.value = ""; // allows choosing the same file again
    }
  }

  return (
    <section className="card">
      <h2>Upload a CSV</h2>
      <input type="file" accept=".csv" onChange={handleFile} disabled={busy} />
      {busy && <p className="muted">{message}</p>}
      {error && <p className="error">{error}</p>}
    </section>
  );
}