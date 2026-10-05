# Semantic drift: price in cents instead of dollars

| | |
|---|---|
| **Dataset** | [`datasets/semantic_price_cents.csv`](../datasets/semantic_price_cents.csv) |
| **Pipeline stopped?** | _FILL: Failed / Warned / Carried on_ |
| **Chatbot fix worked?** | _FILL: Yes / Partly / No / N/A_ |
| **Severity** | _FILL: High / Medium / Low_ |
| **Validation report** | [`data-validation/reports/semantic-price-cents.md`](../data-validation/reports/semantic-price-cents.md) |

## What I changed
Same columns and types; `price` values multiplied by 100 (`49.99` -> `4999`), as if the upstream system switched to cents.

## What I expected
Rhombus will most likely **not notice** (structure valid, numbers non-negative). Our validation should catch it via `semantic.price_magnitude` and `semantic.price_vs_reference` (ratio 100).

## Steps to reproduce
1. Baseline pipeline `orders-cleaning` is scheduled (S3 `s3://<bucket>/input/orders.csv` -> GCS `gs://<bucket>/output/`), last scheduled run green.
2. Overwrite the S3 source object with `datasets/semantic_price_cents.csv` (same key): `aws s3 cp datasets/semantic_price_cents.csv s3://<bucket>/input/orders.csv`.
3. Wait for the next scheduled run (do not trigger manually) - _FILL: time of run_.
4. Inspect run status, logs, GCS output; run `python data-validation/validate.py --case semantic-price-cents --input datasets/semantic_price_cents.csv --output gs://<bucket>/output/<file> --reference datasets/baseline.csv`.
5. Paste the error/log into the AI chatbot, apply its fix, re-run.
6. Restore `datasets/baseline.csv` to S3 before the next case.

## What actually happened
_FILL: run status, duration, what (if anything) landed in GCS. Screenshot:_
![run status](evidence/semantic-price-cents-run.png)

## What the logs said
```
FILL: paste log excerpt
```
_FILL: Is the message clear? Does it name the column/file/row?_ ![logs](evidence/semantic-price-cents-logs.png)

## What the chatbot said
> FILL: prompt you gave it, and its answer (quote)

_FILL: Was the diagnosis correct?_ ![chatbot](evidence/semantic-price-cents-chatbot.png)

## Did the fix work?
_FILL: what the fix changed, re-run result, validation verdict after the fix._

## Schedule afterwards
_FILL: still active / paused / disabled? Did the next scheduled run fire?_

## Validation result
_FILL: verdict + failing checks from the report._

## Assessment
_FILL: one or two sentences - impact for a real customer, severity rationale._
