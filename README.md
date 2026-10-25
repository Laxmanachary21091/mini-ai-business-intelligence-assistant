# Mini AI Business Intelligence Assistant

A small, runnable sales analytics app using Python, Pandas, SQLite, FastAPI,
Streamlit, and the Gemini REST API (optional). No sample sales results are
included: every displayed figure is computed from the CSV you ingest.

## Requirements

- Python 3.10+
- A sales CSV in the schema below
- Optional Gemini API key for LLM-based intent classification

## CSV schema and cleaning

The supplied `ai_bi_assistant_sales_data - GET.csv` uses
`Transaction_Id`, `Order_date`, `Product`, `Region`, `Quantity`, `Unit_price`,
`Discount_amount`, and `Status`. The loader uses
`net sales = Quantity * Unit_price - Discount_amount` for this source format.
It also accepts a direct `sales`/`revenue`/`amount` column instead of the
quantity/price pair. Category and sales-channel columns are not used by these
analytics; they remain in the raw fields of any rejected row.

Date, product, and region are required in either format. Dates are parsed from
`YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`, or `YYYY/MM/DD` and saved as ISO
`YYYY-MM-DD`. Quantity and unit price must be finite, non-negative numbers;
discount must be finite and non-negative and cannot exceed gross sales.
Discount may be blank and then defaults to zero. A zero quantity is valid and
produces zero net sales. Direct sales amounts must be finite and non-negative;
embedded comma separators are removed.

The optional `returned` field accepts true/false, yes/no, y/n, 1/0, or
returned/not returned. If no returned field exists, `Status` values `Returned`
are excluded while recognized non-returned statuses (such as `Completed`) are
included. With neither field, transactions default to not returned. Invalid or
missing dates, amounts, quantities, prices, product/region, or return/status
values are rejected rather than silently imputed. Each rejected record, its
source row, raw fields, and reason are persisted in `rejected_records`.

When an input transaction ID exists, it is the idempotency key (a repeated ID
updates the existing transaction). Without one, a hash of the normalized row
plus its occurrence number within the input file is used, preserving identical
rows while making repeated loads of the same file idempotent. A new changed
file without transaction IDs is treated as a new source unless its normalized
rows and their occurrences match existing keys.

**Revenue policy:** revenue is the sum of non-negative sales for non-returned
transactions. For the supplied quantity-based data, sales means
`quantity * unit_price - discount_amount`; returned transactions are excluded,
not subtracted. Returns remain stored so that this rule is explicit and
auditable. Month-over-month change is end-month revenue minus start-month
revenue; percentage change uses start-month revenue as its base and is
reported as undefined when that base is zero. Missing months in comparisons
count as zero revenue. Top-item ties are resolved alphabetically. Figures use
the input data's currency units; no currency conversion is performed.

## Setup

From the project root, create and activate a virtual environment, then install
the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Ingest the supplied CSV. This creates `data/sales.db` unless `DATABASE_PATH`
is set:

```powershell
python -m app.ingest ".\ai_bi_assistant_sales_data - GET.csv"
```

The ingestion command prints loaded, updated, and rejected counts. The
regenerable database is intentionally excluded from version control.

## Run the API

```powershell
uvicorn app.api:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API docs. Example request:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ask `
  -ContentType 'application/json' `
  -Body '{"question":"What is the total revenue?"}'
```

The endpoint is `POST /ask` and accepts `{"question": "..."}`. Responses
include `answer`, `supporting_figures`, `query_intent`,
`classification_source`, and `fallback_notice`. Unsupported or incomplete
questions return structured error JSON with HTTP 422. Unexpected failures are
logged server-side and return a safe HTTP 500 response.

## Run the Streamlit dashboard

In a second terminal, from the project root:

```powershell
streamlit run streamlit_app.py
```

The UI supports the same question intents, shows supporting figures, and
renders the monthly trend when eligible transactions are present. It displays a
helpful empty-state message before data is ingested.

## Gemini and deterministic fallback

Gemini settings are read from the project-root `.env` file. The repository
includes a local `.env` with a blank key and a `.env.example` template. Open
`.env`, paste your key after `GEMINI_API_KEY=`, and save it. Get a key from
[Google AI Studio](https://aistudio.google.com/apikey). The `.env` file is
ignored by Git; never commit or share it.

```dotenv
GEMINI_API_KEY=your-google-ai-studio-api-key
GEMINI_MODEL=gemini-3.8-flash
GEMINI_TIMEOUT_SECONDS=60
```

Install the newly added environment loader if needed, then stop and restart
both the API and Streamlit processes so they read `.env`:

```powershell
pip install -r requirements.txt
```

Gemini is only asked to return an intent and month parameters. The returned
intent is checked against a fixed allowlist, and only application-owned
parameterized SQL statements are executed. The model cannot issue SQL. With no
key, a network/API failure, or an invalid model response, rule-based routing
is used and the response explicitly says so. Rule routing recognizes comparison
months in `YYYY-MM` form.
The Gemini request timeout defaults to 60 seconds and can be set from 1 to
300 seconds with `GEMINI_TIMEOUT_SECONDS`. A longer timeout can help with a slow
response, but it cannot resolve an unavailable Gemini service or blocked
network connection.

Fallback notices distinguish a missing key, rejected key/permissions (HTTP
401/403), unknown model (HTTP 404), quota/rate limit (HTTP 429), and network or
invalid-response problems. The API key is sent in the request header rather
than included in the URL. If you just edited `.env`, restart the API and
Streamlit processes before trying again.

## Tests

```powershell
pytest -q
```

The test suite creates isolated temporary databases and CSVs; no sales figures
are asserted for a real dataset.

## Architecture

- `app/ingestion.py`: Pandas CSV validation, normalization, rejection audit,
  and repeatable SQLite writes.
- `app/db.py`: SQLite schema, path configuration, and connection management.
- `app/analytics.py`: fixed SQL aggregations. Model output is never passed as
  SQL, and analytics connections are opened read-only.
- `app/nlq.py`: optional Gemini classification, strict intent/month validation,
  and visible rule-based fallback.
- `app/service.py`: intent-to-analytics orchestration and user-facing errors,
  shared by both interfaces.
- `app/api.py`: FastAPI request/response validation and HTTP error mapping.
- `streamlit_app.py`: interactive dashboard and monthly trend chart.

Configure a different database with `DATABASE_PATH`, or pass `--database` to
the ingestion command. Ensure the API and UI use the same path.
