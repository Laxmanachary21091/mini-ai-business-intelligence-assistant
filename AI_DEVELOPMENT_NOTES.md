# AI Development Notes

## AI tools and development assistance

The implementation was prepared with AI coding assistance in the VS Code
Copilot environment. Code generation was reviewed against the stated behavior,
then validated with automated tests. Gemini integration is an optional runtime
feature for mapping a user's question to one of five supported analytics
intents; it is not used to calculate or fabricate sales metrics.

## Development decisions and challenges

- The supplied CSV uses `Quantity`, `Unit_price`, `Discount_amount`, and
  `Status`, rather than a ready-made sales amount and returned flag. Ingestion
  therefore derives net sales as quantity * unit price - discount and maps a
  `Returned` status to the return flag. No sample sales figures were added.
- Analytics use SQL aggregates to keep the calculation source auditable.
  Returned transactions are stored but excluded from revenue; rejected rows
  are recorded with their source row, raw values, and reason.
- Re-ingestion is keyed by transaction ID when available. Otherwise normalized
  row fingerprints and occurrence counts avoid duplicate rows across repeated
  loads without collapsing identical line items in a single file.
- The model response is untrusted input. A strict allowlist and month format
  validation block unsupported intents, and all SQL is predefined and
  parameterized in the analytics module.
- Gemini access is optional; deterministic rule routing covers common
  phrasings and the response states when that fallback was used.

## Debugging and verification

The tests use temporary CSVs and SQLite databases, not real-dataset results.
They cover returned-transaction exclusion, total revenue, top product, monthly
aggregation, top region, month comparison, empty/zero revenue, unsupported or
incomplete questions, rejected rows, and repeatable ingestion. Run them with
`pytest -q`.

## Future improvements

- Add domain-specific treatment if the challenge defines cancellation,
  partial-return, or tax rules beyond the current `Status == Returned` policy.
- Add an ingestion preview and rejected-row report to the dashboard.
- Add timezone/date-format constraints if the source data contract requires
  them, and consider storing currency explicitly if data can contain multiple
  currencies.
- Add structured request tracing and operational metrics around the optional
  Gemini call, plus integration tests against a mocked Gemini HTTP response.
