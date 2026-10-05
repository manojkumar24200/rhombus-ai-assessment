# Semantic drift: price in cents instead of dollars

| | |
|---|---|
| **Dataset** | [`datasets/semantic_price_cents.csv`](../datasets/semantic_price_cents.csv) |
| **Pipeline stopped?** | **Carried on**: run green, 110 rows written to GCS |
| **Chatbot fix worked?** | N/A (nothing failed, so there was nothing to ask about) |
| **Severity** | **High**: wrong financial values published silently |
| **Validation report** | [`data-validation/reports/semantic-price-cents.md`](../data-validation/reports/semantic-price-cents.md) |

## What I changed
Same columns and types; `price` values multiplied by 100 (`49.99` -> `4999`), as if the upstream system switched to cents.

## What I expected
Rhombus will most likely **not notice** (structure valid, numbers non-negative). Our validation should catch it via `semantic.price_magnitude` and `semantic.price_vs_reference` (ratio 100).

## Steps to reproduce
1. Baseline pipeline `orders-cleaning` is scheduled (S3 `s3://<bucket>/input/baseline.csv` -> GCS `gs://<bucket>/output/`), last scheduled run green.
2. Overwrite the S3 source object with `datasets/semantic_price_cents.csv` (same key): `aws s3 cp datasets/semantic_price_cents.csv s3://<bucket>/input/baseline.csv`.
3. Trigger the run (▶). Output arrived at 12:12:41 UTC, ~95 s after upload.
4. Inspect run status, logs, GCS output; run `python data-validation/validate.py --case semantic-price-cents --input datasets/semantic_price_cents.csv --output gs://<bucket>/output/<file> --reference datasets/baseline.csv`.
5. Paste the error/log into the AI chatbot, apply its fix, re-run.
6. Restore `datasets/baseline.csv` to S3 before the next case.

## What actually happened
All nodes green, with no warning. GCS received `RhombusAI_output_1791202361058.csv`: **110 rows, the same count as baseline**, with every price 100× too large (Monitor `18900.0` instead of `189.0`).

## What the logs said
Evidence: the GCS object and the [validation report](../data-validation/reports/semantic-price-cents.md). Rhombus logged only "started" and "completed successfully".
```
Pipeline execution started.
Pipeline execution completed successfully.   (no warnings)
```
There is nothing to explain: Rhombus saw a valid numeric column and raised **no warning**, even though the median price jumped from 34.95 to 3,495.

## What the chatbot said
> Not asked. The pipeline reported success, so a user would have no reason to ask.

N/A

## Did the fix work?
N/A. Detection relies entirely on external validation.

## Schedule afterwards
Unchanged: **Active**. A scheduled job would keep publishing inflated prices on every run.

## Validation result
**FAIL, caught by both semantic checks** ([report](../data-validation/reports/semantic-price-cents.md)):
- `semantic.price_magnitude`: median price **3495.00**; 88% of prices outside the plausible band (1–1000)
- `semantic.price_vs_reference`: **110/110** prices differ from baseline, **median ratio 100.00**
All 14 schema, row-count and cleaning checks **pass**, so structural validation alone would not catch this.

## Assessment
This is the most dangerous class of failure: the pipeline is green, the schema is valid, the row count is right, and every price is wrong by 100×. Rhombus has no distribution or range monitoring between runs. A simple "median shifted >10× vs last run" warning would have caught it. **High.**
