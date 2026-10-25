
# Mini AI Business Intelligence Assistant

**AI-Assisted Development Challenge — Graduate Engineer Trainee | RSG**

A lightweight Business Intelligence (BI) application that enables users to ask natural-language questions about sales transactions and receive data-backed answers. It combines Python, Pandas, SQLite, FastAPI, Streamlit, and optional Google Gemini integration to translate questions into validated analytics operations and execute deterministic SQL queries.

The system is designed to prioritize **accuracy, explainability, data quality, and safe query execution** over unnecessary complexity.

## Key Features

- **Natural-language analytics:** Ask questions about revenue, product performance, regional sales, monthly trends, and month-over-month changes.
- **Database-backed calculations:** Calculate all reported sales figures from ingested transaction data using predefined SQL queries.
- **Optional Generative AI:** Use Gemini to classify questions into supported analytics intents and extract month parameters.
- **Deterministic fallback:** Continue supporting recognized questions through rule-based routing when Gemini is unavailable or its response cannot be validated.
- **Data validation and cleaning:** Validate dates, numeric values, required fields, discounts, and transaction statuses during CSV ingestion.
- **Rejected-record auditing:** Store invalid records with their source row, original fields, and rejection reasons.
- **REST API:** Expose analytics through a FastAPI endpoint with structured responses and error handling.
- **Interactive dashboard:** Use Streamlit to ask questions, inspect supporting figures, and visualize monthly revenue trends.
- **Automated tests:** Test analytics behavior using isolated test databases and CSV files.

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Language | Python 3.10+ | Application logic and analytics |
| Data processing | Pandas | CSV ingestion and validation |
| Database | SQLite | Persistent transaction storage |
| Backend | FastAPI | REST API and request validation |
| Frontend | Streamlit | Interactive analytics dashboard |
| AI integration | Google Gemini REST API | Natural-language intent classification |
| Testing | pytest | Automated testing |
| Version control | Git and GitHub | Source control and submission |

## Architecture

```text
                  Business User
                       |
             Natural-Language Question
                       |
             +---------+---------+
             |                   |
        Streamlit UI         REST API
             |               FastAPI
             |                   |
             +---------+---------+
                       |
                 Shared Service
                       |
                Question Router
                       |
              +--------+--------+
              |                 |
         Gemini REST API    Rule-Based
         (-----------)       Fallback
              |                 |
              +--------+--------+
                       |
             Intent and Parameter
                   Validation
                       |
             Predefined Analytics
                  Functions
                       |
              Read-Only SQL
                       |
                 SQLite DB
                       |
             Structured Results
                       |
            Answer + Supporting Data
```

### Data ingestion flow

```text
Sales CSV
    |
    v
Pandas Validation and Normalization
    |
    +---- Invalid records ----> Rejection Audit
    |
    v
Validated Transactions
    |
    v
SQLite Database
    |
    v
SQL-Based Analytics
```

The Streamlit dashboard and FastAPI backend share the same service and analytics logic, helping keep calculations consistent across both interfaces.

## Supported Business Questions

The application is designed to support the following questions:

1. **Total revenue:** What is the total revenue?
2. **Top-performing product:** Which product generated the highest revenue?
3. **Monthly revenue trend:** What is the monthly revenue trend?
4. **Regional performance:** Which region generated the highest sales?
5. **Month-over-month comparison:** How did revenue change between January and February?

For month comparisons, provide months in `YYYY-MM` format when needed, for example:

- `Compare revenue between 2026-01 and 2026-02`
- `How did revenue change from 2026-03 to 2026-04?`

Actual results depend on the transactions successfully ingested into the database.

## Data Model and Cleaning Rules

The supplied sales CSV contains the following core fields:

| Column | Purpose |
|---|---|
| `Transaction_Id` | Transaction identifier |
| `Order_date` | Transaction date |
| `Product` | Product name |
| `Region` | Sales region |
| `Quantity` | Number of units sold |
| `Unit_price` | Price per unit |
| `Discount_amount` | Discount applied |
| `Status` | Transaction status |

The ingestion logic also supports a direct sales, revenue, or amount column where applicable.

### Revenue calculation

For quantity-based records, net sales are calculated as:

```text
Net Sales = (Quantity × Unit Price) − Discount Amount
```

Revenue is the sum of valid, non-negative sales amounts from transactions that are not marked as returned.

### Data-quality policies

- Required dates, product names, regions, and monetary inputs are validated.
- Supported date formats are normalized to ISO `YYYY-MM-DD`.
- Quantity and unit price must be finite and non-negative.
- Discounts must be finite, non-negative, and no greater than gross sales.
- Blank discounts default to zero.
- A zero quantity is valid and produces zero net sales.
- Missing or invalid required values cause the affected record to be rejected and audited.
- Returned transactions remain stored but are excluded from revenue calculations.
- Recognized completed or other supported non-returned statuses are handled according to the ingestion rules.
- Repeated transaction IDs update existing records rather than creating duplicate transactions.
- Transactions without IDs use normalized-row hashes and occurrence numbers for repeatable ingestion.

Rejected records are preserved in the `rejected_records` table for auditing and troubleshooting.

### Reporting conventions

- Month-over-month change = ending-month revenue − starting-month revenue.
- Percentage change uses starting-month revenue as the baseline.
- Percentage change is undefined when starting-month revenue is zero.
- Missing months in comparisons are treated as having zero revenue.
- Product ties are resolved alphabetically.
- Monetary figures use the source data's currency units; no currency conversion is performed.

## Project Structure

```text
mini-bi-assistant/
├── app/
│   ├── api.py              # FastAPI endpoints
│   ├── analytics.py        # SQL analytics
│   ├── db.py               # Database configuration
│   ├── ingestion.py        # CSV validation and ingestion
│   ├── nlq.py              # AI and rule-based question routing
│   └── service.py          # Shared application logic
├── data/
│   └── sales.db            # Generated local database
├── tests/                  # Automated tests
├── streamlit_app.py        # Streamlit dashboard
├── requirements.txt        # Python dependencies
├── .env.example            # Environment-variable template
├── .gitignore
└── README.md
```

The exact repository may contain additional files. The SQLite database is generated from the supplied CSV and is intentionally excluded from version control.

## Getting Started

### Prerequisites

- Python 3.10 or later
- Git
- The supplied sales CSV file
- Optional Gemini API key for AI-based question classification

### 1. Clone the repository

```bash
git clone YOUR_PUBLIC_GITHUB_REPOSITORY_URL
cd YOUR_PROJECT_FOLDER
```

Replace the placeholders with your actual repository URL and folder name.

### 2. Create and activate a virtual environment

On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Ingest the sales data

Place the supplied CSV in the project root or update the path to match its actual location.

```powershell
python -m app.ingest ".\ai_bi_assistant_sales_data - GET.csv"
```

The ingestion process creates `data/sales.db` by default and reports the numbers of loaded, updated, and rejected records.

If `DATABASE_PATH` is configured, the application uses that database location instead.

### 5. Configure optional Gemini integration

Create a local `.env` file in the project root, using `.env.example` as a reference:

```dotenv
GEMINI_API_KEY=your-google-ai-studio-api-key
GEMINI_MODEL=your-supported-gemini-model
GEMINI_TIMEOUT_SECONDS=60
```

Replace the model placeholder with a model currently available to your API key and integration.

Obtain an API key through [Google AI Studio](https://aistudio.google.com/apikey).

Never commit `.env` or expose API keys in source code, logs, screenshots, or public repositories.

If no API key is configured, the application can use its supported rule-based question routing.

### 6. Start the FastAPI backend

Open a terminal in the project root and run:

```powershell
python -m uvicorn app.api:app --reload
```

The API runs locally at:

`http://127.0.0.1:8000`

Interactive API documentation is available at:

`http://127.0.0.1:8000/docs`

### 7. Start the Streamlit dashboard

Open a second terminal, activate the same virtual environment, and run:

```powershell
python -m streamlit run streamlit_app.py
```

Open the local URL printed in the terminal, usually:

`http://localhost:8501`

Ensure the API and dashboard use the same database configuration.

## API Usage

### Endpoint

`POST /ask`

### Request

```json
{
  "question": "What is the total revenue?"
}
```

### Response format

A successful response contains fields such as:

```json
{
  "answer": "Calculated result based on the ingested data",
  "supporting_figures": {},
  "query_intent": "total_revenue",
  "classification_source": "rule_based",
  "fallback_notice": "Optional explanation"
}
```

This is an illustrative response structure, not a claim about the actual revenue or exact runtime output. The `supporting_figures` content depends on the analytics operation.

### Test the API using PowerShell

With the backend running, execute:

```powershell
$body = @{
    question = "What is the total revenue?"
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/ask" `
    -ContentType "application/json" `
    -Body $body
```

Unsupported or incomplete questions are handled with structured errors. Unexpected server-side errors are logged and returned as safe error responses.

## AI Integration and Reliability

Gemini is used for question interpretation, not for calculating or inventing business metrics.

The AI-assisted flow is:

1. Receive the user's natural-language question.
2. Ask Gemini to classify the question into a supported analytics intent and extract required parameters.
3. Validate the returned intent and parameters against application-defined rules.
4. Execute the corresponding predefined, parameterized SQL query.
5. Return the calculated result with supporting figures.

### Safety and fallback behavior

- Model output is never executed as SQL.
- Only supported analytics intents are accepted.
- Database analytics use read-only connections.
- Query parameters are validated before execution.
- Missing keys, network failures, API errors, and invalid model responses can trigger rule-based fallback.
- Fallback behavior is disclosed instead of being presented as successful AI interpretation.

Rule-based routing provides a limited alternative when Gemini is unavailable. It does not replace the need to test natural-language coverage or verify AI-based classification.

## Testing

Run the automated test suite from the project root:

```powershell
python -m pytest -q
```

The tests use temporary databases and CSV files to avoid depending on hard-coded results from the supplied dataset.

Recommended test coverage includes:

- Total revenue calculation.
- Highest-revenue product selection.
- Monthly revenue aggregation.
- Highest-performing region.
- Month-over-month revenue and percentage changes.
- Invalid and unsupported questions.
- Missing or invalid source values.
- Returned transactions and zero-quantity records.
- Idempotent data ingestion.
- Zero starting-month revenue.

Run the tests before submitting changes and resolve any failures.

## Development Process and AI Assistance

AI coding tools were used to support implementation and debugging:

- **OpenAI Codex:** Assisted with code generation, implementation, and development tasks.
- **VS Code Agent:** Assisted with project editing, integration, and troubleshooting.
- **GPT-6 luna**

The implementation was organized around separate modules for ingestion, analytics, question interpretation, API handling, and presentation.

The development approach emphasizes inspecting generated code, validating data transformations, testing SQL calculations, and keeping AI output separate from executable database operations.

Development issues, debugging steps, and potential improvements should be documented in `AI_DEVELOPMENT_NOTES.md` based on the actual work performed.

## Known Limitations

- Question interpretation is limited to the supported analytics intents and implemented parameter patterns.
- Rule-based fallback may not recognize every natural-language variation.
- Gemini availability depends on valid credentials, model access, network connectivity, and applicable API quotas.
- The application analyzes the supplied transaction data and does not independently verify its accuracy.
- Currency conversion and advanced financial accounting rules are outside the current scope.
- The application is a selection-challenge prototype, not a production-hardened BI platform.

## Future Improvements

With additional development time, the application could be extended with:

- Broader natural-language question coverage and clarification prompts.
- More advanced filters for date ranges, products, regions, and categories.
- Richer dashboard visualizations and exportable reports.
- Additional data-quality and integration tests.
- Structured observability for model latency and fallback frequency.
- Deployment to a cloud platform with managed secrets and monitoring.
- Authentication, authorization, and production deployment hardening.

## Challenge Deliverables

This repository is intended to contain:

- Application source code.
- CSV ingestion and database-backed analytics.
- FastAPI backend and Streamlit interface.
- Optional Gemini integration with deterministic fallback.
- Automated tests.
- Setup and execution instructions.
- Architecture and AI development documentation.

---


