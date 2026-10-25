const BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, options);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return body;
}

export const health = () => request("/health");

export const uploadDataset = (file) => {
  const form = new FormData();
  form.append("file", file);
  return request("/datasets/upload", { method: "POST", body: form });
};

export const analyze = (id) => request(`/datasets/${id}/analyze`, { method: "POST" });
export const getStatus = (id) => request(`/datasets/${id}/status`);
export const getResult = (id) => request(`/datasets/${id}/result`);

export const createNarrative = (reportId) =>
  request(`/reports/${reportId}/narrative`, { method: "POST" });
export const getReport = (reportId) => request(`/reports/${reportId}`);
export const listReports = (datasetId) =>
  request(`/reports${datasetId ? `?dataset_id=${datasetId}` : ""}`);
export const listDatasets = () => request("/datasets");

export const chartOptions = (id) => request(`/datasets/${id}/charts/options`);

export const getChart = (id, { type, columns = [], bins, top }) => {
  const params = new URLSearchParams({ type });
  columns.forEach((c) => params.append("columns", c)); // repeated param: columns=a&columns=b
  if (bins) params.set("bins", bins);
  if (top) params.set("top", top);
  return request(`/datasets/${id}/charts?${params}`);
};