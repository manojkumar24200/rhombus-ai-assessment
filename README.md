# Rhombus AI: Scheduled ETL Pipeline & Drift Testing

Testing Rhombus AI as a customer would: a **scheduled S3 → AI-built cleaning pipeline → GCS** job, then deliberately breaking the input (schema drift and semantic drift) to see how the platform responds.

```
datasets/          baseline.csv + 7 drifted variants (+ generator, + AI builder prompt)
ui-tests/          Playwright (Python): login, S3 source, AI-built pipeline, GCS destination, schedule
api-tests/         Backend API tests (positive + negative) + endpoint capture tool
data-validation/   validate.py: compares GCS output vs S3 input (+ self-tests)
observations/      one report per drift case; screenshots/logs in observations/evidence/
```

---

## 1. Setup and how to run

**Prerequisites:** Python 3.11+, an AWS S3 bucket, a GCS bucket with a service-account key, and a Rhombus AI account.

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env        # then fill in credentials (never committed, see .gitignore)
```

### Datasets
```bash
python datasets/generate_datasets.py      # deterministic (seed 42); regenerates every CSV
```
| File | What it is |
|---|---|
| `baseline.csv` | 132 rows: 8 exact + 4 near duplicates, blanks, mixed date/country/status formats, `$` prices, invalid emails/prices/quantities/dates |
| `schema_drop_column.csv` | `email` removed |
| `schema_rename_column.csv` | `price` → `unit_price` |
| `schema_type_change.csv` | `quantity` as words (`three`) |
| `schema_add_column.csv` | new `discount_code` column |
| `schema_combined.csv` | all four at once |
| `semantic_price_cents.csv` | prices ×100 (dollars → cents) |
| `semantic_date_ddmm.csv` | MM/DD/YYYY → DD/MM/YYYY |

The pipeline was built **only with the AI builder**, using the prompt in [`datasets/ai_builder_prompt.txt`](datasets/ai_builder_prompt.txt). The validator's reference cleaner implements exactly the same rules.

### Data validation
```bash
python -m pytest data-validation -q                          # self-tests: prove each check catches its fault
cp data-validation/runs.example.json data-validation/runs.json   # set your bucket names
python data-validation/validate.py --manifest data-validation/runs.json
```
It reads `s3://`, `gs://` or local paths, and writes `data-validation/reports/<case>.md|json` plus `summary.json`. The exit code is 1 if any check fails.

| Check group | What it verifies |
|---|---|
| `schema.*` | 9 expected columns/order; `price` numeric, `quantity` integer, `order_date` ISO |
| `rows.*` | output non-empty, not larger than input, equals the row count the cleaning rules predict |
| `clean.*` | no duplicate/empty `order_id`, no duplicate rows, trimmed text, Title-Case names, canonical country/status, valid emails, no negative prices, quantity 1–1000 |
| `determinism` | order-independent SHA-256 of the output equals that of repeat runs |
| `semantic.*` | price magnitude band, date window, and per-`order_id` comparison of price/date against the baseline oracle (catches cents and DD/MM) |

### UI tests (Playwright)
```bash
python -m pytest ui-tests --headed              # watch it
python -m pytest ui-tests --tracing retain-on-failure
```
- Logs in once per session and reuses the storage state.
- Uses no fixed sleeps: every wait is an `expect()` on a UI condition. AI generation and pipeline runs have long, configurable *condition* timeouts (`AI_TIMEOUT_MS`, `RUN_TIMEOUT_MS`).
- Asserts real outcomes: the S3 connection is saved with no error, the AI produced ≥2 transformation steps, the GCS destination shows the bucket, the schedule is active and the latest run status is *success*.
- All selectors are in [`ui-tests/pages.py`](ui-tests/pages.py) (page objects, role/text based). If the UI changes, re-record with `python -m playwright codegen https://rhombusai.com` and update only that file.

### API tests
```bash
python api-tests/capture_endpoints.py    # opens a browser, records the app's XHR/fetch calls -> captured_endpoints.json
python -m pytest api-tests -v
```
| Test | Type | Asserts |
|---|---|---|
| `test_list_pipelines_returns_my_pipeline` | positive | 200, JSON, my pipeline is in the list |
| `test_latest_run_has_a_status` | positive | 200, runs present, run has a status |
| `test_unauthenticated_request_is_rejected` | **negative** | 401/403, no pipeline data leaked |
| `test_invalid_token_is_rejected` | **negative** | 401/403, no data leaked |
| `test_login_with_wrong_password_is_rejected` | **negative** | 4xx, no token issued |
| `test_unknown_pipeline_returns_404` | **negative** | 400/403/404 |

A test whose endpoint isn't configured in `.env` is **skipped** with a reason rather than passing silently.

---

## 2. Observations summary

| Drift case | Change | Pipeline stopped? | Chatbot fix worked? | Severity |
|---|---|---|---|---|
| [schema-drop-column](observations/schema-drop-column.md) | drop `email` | _FILL_ | _FILL_ | _FILL_ |
| [schema-rename-column](observations/schema-rename-column.md) | `price` → `unit_price` | _FILL_ | _FILL_ | _FILL_ |
| [schema-type-change](observations/schema-type-change.md) | `quantity` int → words | _FILL_ | _FILL_ | _FILL_ |
| [schema-add-column](observations/schema-add-column.md) | add `discount_code` | _FILL_ | _FILL_ | _FILL_ |
| [schema-combined](observations/schema-combined.md) | all four | _FILL_ | _FILL_ | _FILL_ |
| [semantic-price-cents](observations/semantic-price-cents.md) | dollars → cents | _FILL_ | N/A | _FILL_ |
| [semantic-date-ddmm](observations/semantic-date-ddmm.md) | MM/DD → DD/MM | _FILL_ | N/A | _FILL_ |

Severity scale: **High** means wrong data reaches GCS silently. **Medium** means the run fails but the cause is unclear or the fix doesn't work. **Low** means it is handled, with a cosmetic or UX issue at most.

### Top three findings
1. _FILL_
2. _FILL_
3. _FILL_

---

## 3. Usability feedback

_FILL: what was most helpful or enjoyable, what was frustrating or difficult, and concrete suggestions._

---

## 4. Demo video

_FILL: link_

---

### Trade-offs and limitations
- **Python Playwright** instead of Node, so all three suites share one toolchain and one `requirements.txt`.
- **The UI tests depend on Rhombus's DOM.** Selectors are role/text based and isolated in one file, but they were written against the live app at a single point in time.
- **API tests use endpoints observed in the browser.** They aren't a documented public API, so their paths are configurable rather than hard-coded.
- **The validator's oracle is my own implementation of the cleaning rules.** If the AI interprets a rule differently (for example, keeping rows with an invalid date), it shows up as a `rows.match_reference` warning or failure with the exact difference. That is a finding worth reporting, not necessarily a platform bug.
