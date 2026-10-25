import { useEffect, useState } from "react";
import { health } from "./api";
import "./index.css";

export default function App() {
  const [api, setApi] = useState("checking...");

  useEffect(() => {
    health()
      .then((r) => setApi(r.status))
      .catch(() => setApi("unreachable"));
  }, []);

  return (
    <main className="page">
      <h1>AutoInsight</h1>
      <p>API: {api}</p>
    </main>
  );
}