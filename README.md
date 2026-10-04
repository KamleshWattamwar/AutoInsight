# AutoInsight 📊
**Automated EDA-to-Insight Report Generator**

Transform raw CSV data into analyst-style reports. AutoInsight automatically profiles datasets, detects statistical patterns via a deterministic rule engine, and generates plain-English insights—powered by an LLM but grounded in verified numbers.

## Why This Matters
Most data analysis tools either:
- Generate arbitrary charts without insight (dashboards)
- Let LLMs hallucinate statistics from raw data (unreliable)

AutoInsight does this:
```
CSV → Pandas Stats → Rule-Based Finder → LLM Translation → Analyst Report
```
The LLM only narrates; the math is bulletproof.

---

## ✨ Core Features

| Feature | What It Does |
|---------|-------------|
| **Data Profiling** | Detects types, nulls, duplicates, descriptive stats automatically |
| **Outlier Detection** | IQR-based anomaly flagging with severity scoring |
| **Correlation Analysis** | Pearson/Spearman correlations without false causation claims |
| **Rule-Based Insights** | High missingness, skewed distributions, strong relationships → deterministic flags |
| **LLM Narratives** | Structured findings → clear executive summaries + recommendations |
| **Visual Exploration** | User-selectable charts (histogram, scatter, bar, box plot) |
| **Report History** | Save & retrieve past analyses from PostgreSQL |

---

## 🛠 Tech Stack

**Frontend:** React, Vite, Tailwind CSS, Recharts  
**Backend:** FastAPI, Pydantic, Python  
**Data:** Pandas, NumPy, SciPy  
**Database:** PostgreSQL, SQLAlchemy  
**AI:** OpenAI API  
**Deployment:** Docker, Docker Compose

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 16+
- PostgreSQL (or run via Docker)

### Run Locally

1. **Clone & setup:**
   ```bash
   git clone https://github.com/KamleshWattamwar/AutoInsight.git
   cd AutoInsight
   ```

2. **Create `.env`:**
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/autoinsight
   OPENAI_API_KEY=your_key_here
   ```

3. **Start with Docker:**
   ```bash
   docker-compose up --build
   ```

4. **Access:**
   - Frontend: http://localhost:3000
   - API Docs: http://localhost:8000/docs

---

## 📁 Project Structure

```
AutoInsight/
├── backend/
│   ├── app/
│   │   ├── api/              # Endpoints: upload, analyze, reports
│   │   ├── services/         # Profiler, statistics, LLM logic
│   │   ├── models/           # SQLAlchemy DB models
│   │   └── core/             # Config, database
│   ├── requirements.txt
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/       # UI components
│   │   ├── pages/            # Upload, Dashboard, History
│   │   └── services/         # API calls
│   └── package.json
├── docker-compose.yml
└── .env.example
```

---

## 💡 How It Works (Example)

**Input:** `sales_2026.csv` (10K rows, 15 columns)

**Backend Output (JSON):**
```json
{
  "dataset": { "rows": 10000, "columns": 15 },
  "missing_values": { "commission": 2.3, "region": 0.1 },
  "outliers": { "revenue": { "count": 47, "method": "IQR" } },
  "correlations": [
    { "columns": ["sales", "experience"], "pearson": 0.82 }
  ],
  "insights": [
    {
      "type": "high_missingness",
      "column": "commission",
      "percentage": 2.3,
      "severity": "medium"
    }
  ]
}
```

**LLM Receives (Structured):**  
→ Generates: *"Commission data is incomplete (2.3%). Consider whether this correlates with contract type or region."*

**React Dashboard Displays:**
- Overview cards (10K rows, 15 cols, 2.3% nulls)
- Insight cards with severity badges
- Charts: correlation heatmap, commission distribution, scatter (sales vs. experience)
- "Why this matters" explanations

---


## 📝 API Endpoints (Key Routes)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/datasets/upload` | Upload CSV file |
| `POST` | `/api/datasets/{id}/analyze` | Run full analysis |
| `GET` | `/api/reports/{id}` | Fetch report JSON |
| `GET` | `/api/reports` | List past reports |
| `POST` | `/api/explore/chart` | Generate chart config |



## 🧪 Testing

```bash
# Backend
cd backend
pytest tests/

# Frontend
cd ../frontend
npm test
```

---

