# AutoInsight

**Automated EDA-to-insight report generator.** Upload a CSV and get an analyst-style report: data profile, detected problems and patterns, and a data quality score.

**Design rule:** the engine computes every number. A planned LLM layer will only narrate verified findings, so the report cannot invent statistics.

```
CSV -> Pandas/SciPy profile -> rule-based findings -> quality score -> (planned) LLM narrative
```

## Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Deterministic EDA engine (profiling, outliers, correlations, findings, score) | Done |
| 2 | FastAPI layer: safe upload, background analysis, status polling | Done |
| 3 | PostgreSQL persistence: datasets and report history | Done |
| 4 | LLM narrative layer (validated against the findings) | Planned |
| 5 | Chart endpoints (aggregated data only) | Planned |
| 6 | React dashboard | Planned |
| 7 | Deployment | Planned |

## Features (built)

- **Type detection:** numeric, categorical, boolean, datetime, text, identifier, empty.
- **Profiling:** missing values, duplicates, constant columns, descriptive stats.
- **Outliers:** IQR method with bounds and counts.
- **Correlations:** Pearson and Spearman with p-values. Findings use the stronger of the two and never claim causation.
- **Rule-based findings:** missing data, skew, outliers, dominant category, high cardinality, correlation. Sorted by severity.
- **Quality score:** 0 to 100, from a documented capped-penalty formula.
- **API:** CSV upload with a 50 MB cap and UUID file names, analysis as a background job, status polling.
- **Persistence:** datasets and reports stored in PostgreSQL. Re-analysis keeps the report history.

## Tech stack

| Layer | Choice |
|-------|--------|
| Engine | Python, Pandas, NumPy, SciPy |
| API | FastAPI, uvicorn |
| Database | PostgreSQL, SQLAlchemy 2.0, psycopg |
| Tests | pytest, FastAPI TestClient |
| Planned | LLM API (provider undecided), React, Recharts |

## Running (PostgreSQL)

Requirements: Python 3.10+ and PostgreSQL.

1. Create the database user and databases:

```sql
create user autoinsight with password 'autoinsight';
create database autoinsight owner autoinsight;
create database autoinsight_test owner autoinsight;
```

2. Install and run the API:

```powershell
git clone https://github.com/KamleshWattamwar/AutoInsight.git
cd AutoInsight/backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

3. Run the tests (PostgreSQL must be running):

```powershell
python -m pytest
```

Configuration (see `.env.example`):

| Variable | Used by | Default |
|----------|---------|---------|
| `DATABASE_URL` | the app | local `autoinsight` database |
| `TEST_DATABASE_URL` | the tests | local `autoinsight_test` database |

The URL format is `postgresql+psycopg://user:password@host:5432/dbname`. The test fixture refuses to run unless the database name ends with `_test`, because it drops all tables.

CLI without a server: `python analyze.py file.csv --json out.json`

## API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/datasets/upload` | Upload a CSV (400 bad file, 413 too large) |
| `GET` | `/datasets` | List datasets, newest first |
| `POST` | `/datasets/{id}/analyze` | Start analysis, returns 202 and a `report_id` |
| `GET` | `/datasets/{id}/status` | Status of the latest report |
| `GET` | `/datasets/{id}/result` | Latest result (409 until it is done) |
| `GET` | `/reports` | Report history, optional `?dataset_id=` |
| `GET` | `/reports/{id}` | One report with its result |

Typical flow: upload, analyze, poll `status` until `done`, then fetch `result`.

## Result shape

```
{
  "overview":     { rows, columns, duplicate_rows, total_missing_pct, missing, constant_columns, column_types },
  "columns":      { <column>: { type, stats?, outliers?, unique? } },
  "correlations": { pairs, matrix, skipped_columns },
  "findings":     [ { type, severity, columns, message, evidence } ],
  "quality_score": 0-100,
  "warnings":     [ ... ]
}
```

## Project structure

```
AutoInsight/
├── backend/
│   ├── app/
│   │   ├── main.py          # routes, background job
│   │   ├── db.py            # engine, session, get_db
│   │   ├── models.py        # Dataset, Report
│   │   └── services/        # loader, profiler, findings, analyzer
│   ├── tests/
│   ├── analyze.py           # CLI
│   └── requirements.txt
├── frontend/                # not built yet
├── data/                    # sample CSVs
├── docs/
└── .env.example
```

## Known limitations

- Analysis runs as a background task inside the server process. Use a single worker.
- A report left `pending` or `running` by a server crash is not recovered automatically, and it blocks re-analysis of that dataset.
- Uploaded CSVs are stored on local disk. A deployment needs a persistent disk or object storage.
- No authentication or rate limiting.
- Detection thresholds are validated on only a few datasets.