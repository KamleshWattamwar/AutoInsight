# AutoInsight

**Automated EDA-to-insight report generator.** Upload a CSV and get an analyst-style report: data profile, detected problems and patterns, a data quality score, and a plain-English narrative.

**Design rule:** the engine computes every number. The LLM only narrates verified findings, and every number in its output is checked against those findings in code. Anything that fails is replaced by a rule-based message, so the report cannot invent statistics and still works if the LLM is down.

```
CSV -> Pandas/SciPy profile -> rule-based findings -> quality score -> LLM narrative (validated)
```

## Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Deterministic EDA engine (profiling, outliers, correlations, findings, score) | Done |
| 2 | FastAPI layer: safe upload, background analysis, status polling | Done |
| 3 | PostgreSQL persistence: datasets and report history | Done |
| 4 | LLM narrative layer (Gemini, validated against the findings) | Done |
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
- **LLM narrative:** Gemini explains the findings in plain English and suggests a next step for each. It sees only verified findings, never raw rows. Every number in its text must match a number in the findings (after rounding). A sentence that fails the check, or any LLM failure, falls back to the rule-based message. Each piece is marked `llm` or `rules`.
- **API:** CSV upload with a 50 MB cap and UUID file names, analysis as a background job, status polling.
- **Persistence:** datasets, reports and narratives stored in PostgreSQL. Re-analysis keeps the report history.

## Tech stack

| Layer | Choice |
|-------|--------|
| Engine | Python, Pandas, NumPy, SciPy |
| API | FastAPI, uvicorn |
| Database | PostgreSQL, SQLAlchemy 2.0, psycopg |
| LLM | Gemini through the official `google-genai` SDK |
| Tests | pytest, FastAPI TestClient (the LLM is faked in tests) |
| Planned | React, Recharts |

## Running (PostgreSQL)

Requirements: Python 3.10+, PostgreSQL, and a Gemini API key for the narrative feature.

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
```

3. Create `backend/.env` from `.env.example` and set your Gemini values (see Configuration). Then start the server:

```powershell
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

4. Run the tests (PostgreSQL must be running):

```powershell
python -m pytest
```

### Configuration

Copy `.env.example` to `backend/.env`. The `.env` file is gitignored and must never be committed. Restart the server after editing it.

| Variable | Used by | Default |
|----------|---------|---------|
| `DATABASE_URL` | the app | local `autoinsight` database |
| `TEST_DATABASE_URL` | the tests | local `autoinsight_test` database |
| `GEMINI_API_KEY` | the narrative feature | none (narrative falls back to rule-based text) |
| `GEMINI_MODEL` | the narrative feature | none. Use the model id, lowercase with hyphens, not the display name |

The database URL format is `postgresql+psycopg://user:password@host:5432/dbname`. The test fixture refuses to run unless the database name ends with `_test`, because it drops all tables.

If you upgrade an existing database from Phase 3, add the new column once:

```sql
alter table reports add column narrative json;
```

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
| `GET` | `/reports/{id}` | One report with its result and narrative |
| `POST` | `/reports/{id}/narrative` | Generate (or regenerate) the narrative for a finished report (409 until it is done) |

Typical flow: upload, analyze, poll `status` until `done`, fetch `result`, then `POST /reports/{id}/narrative` for the plain-English version.

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

## Narrative shape

Stored on the report and returned by `GET /reports/{id}` and `POST /reports/{id}/narrative`:

```
{
  "source":   "llm" | "mixed" | "rules",
  "summary":  "...",
  "findings": [ { index, text, source: "llm" | "rules" } ]
}
```

`source` is `llm` when every sentence passed the number check, `rules` when everything fell back, and `mixed` otherwise. `index` is the position in the result's `findings` list (the first 15 are narrated).

## Project structure

```
AutoInsight/
├── backend/
│   ├── app/
│   │   ├── __init__.py      # loads backend/.env
│   │   ├── main.py          # routes, background job
│   │   ├── db.py            # engine, session, get_db
│   │   ├── models.py        # Dataset, Report
│   │   └── services/        # loader, profiler, findings, analyzer, narrative, llm
│   ├── tests/
│   ├── analyze.py           # CLI
│   └── requirements.txt
├── frontend/                # not built yet
├── data/                    # sample CSVs
├── docs/                    # handoff files
└── .env.example
```

## Known limitations

- Analysis runs as a background task inside the server process. Use a single worker.
- A report left `pending` or `running` by a server crash is not recovered automatically, and it blocks re-analysis of that dataset.
- Uploaded CSVs are stored on local disk. A deployment needs a persistent disk or object storage.
- No authentication or rate limiting. The narrative endpoint calls Gemini on every request.
- The narrative check validates numbers only, not meaning. The advice in the narrative is the model's judgment and is not verified.
- The narrative endpoint is synchronous, so a slow Gemini call holds a request (30 second timeout, up to two attempts).
- Detection thresholds are validated on only a few datasets.