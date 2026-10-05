# Semantic drift: dates switch from MM/DD to DD/MM

| | |
|---|---|
| **Dataset** | [`datasets/semantic_date_ddmm.csv`](../datasets/semantic_date_ddmm.csv) |
| **Pipeline stopped?** | **Carried on**: run green, 110 rows written to GCS |
| **Chatbot fix worked?** | N/A (the run reported success) |
| **Severity** | **High**: 20 dates silently changed meaning |
| **Validation report** | [`data-validation/reports/semantic-date-ddmm.md`](../data-validation/reports/semantic-date-ddmm.md) |

## What I changed
Same columns; every `MM/DD/YYYY` date rewritten as `DD/MM/YYYY` (e.g. `05/29/2024` -> `29/05/2024`; `03/04/2024` now means 3 April, not 4 March). ISO and text dates unchanged.

## What I expected
Unambiguous dates (day > 12) fail month-first parsing -> rows dropped (row count falls). Ambiguous dates (day <= 12) are **silently swapped**. Rhombus is unlikely to notice; validation should catch via `rows.match_reference`, `semantic.date_vs_reference`.

## Steps to reproduce
1. Baseline pipeline `orders-cleaning` is scheduled (S3 `s3://<bucket>/input/baseline.csv` -> GCS `gs://<bucket>/output/`), last scheduled run green.
2. Overwrite the S3 source object with `datasets/semantic_date_ddmm.csv` (same key): `aws s3 cp datasets/semantic_date_ddmm.csv s3://<bucket>/input/baseline.csv`.
3. Trigger the run (▶). Output arrived at 12:13:52 UTC.
4. Inspect run status, logs, GCS output; run `python data-validation/validate.py --case semantic-date-ddmm --input datasets/semantic_date_ddmm.csv --output gs://<bucket>/output/<file> --reference datasets/baseline.csv`.
5. Paste the error/log into the AI chatbot, apply its fix, re-run.
6. Restore `datasets/baseline.csv` to S3 before the next case.

## What actually happened
All nodes green, with no warning. GCS received `RhombusAI_output_1791202431847.csv` with **110 rows**, the same as baseline.

## What the logs said
Evidence: the GCS object and the [validation report](../data-validation/reports/semantic-date-ddmm.md). Rhombus logged only "started" and "completed successfully".
```
Pipeline execution started.
Pipeline execution completed successfully.   (no warnings)
```
There was no message. The format change from MM/DD to DD/MM was never flagged.

## What the chatbot said
> Not asked. The pipeline reported success.

N/A

## Did the fix work?
N/A

## Schedule afterwards
Unchanged: **Active**.

## Validation result
**FAIL, caught by semantic checks** ([report](../data-validation/reports/semantic-date-ddmm.md)):
- `semantic.date_vs_reference`: **20/110 dates differ from baseline**, e.g. `ORD-1073` → `2024-10-08` (truth `2024-08-10`), `ORD-1097` → `2024-10-06` (truth `2024-06-10`), `ORD-1101` → `2024-01-03` (truth `2024-03-01`)
- `semantic.date_window`: 5 dates fall outside the real order window (Jan–Sep 2024)
- `rows.match_reference` also fails (110 vs 87), but **this is my oracle being stricter than Rhombus**: my reference parses month-first and drops impossible dates like `29/05/2024`, while Rhombus inferred those correctly. That part is a validator artefact, not a platform bug.

## Assessment
Rhombus handled the *unambiguous* dates sensibly, which makes this worse: the output looks right, row counts match, yet **every ambiguous date (day ≤ 12) was silently read month-first and is now wrong**, with some even in the future. The source format changed and nothing warned. **High.**
