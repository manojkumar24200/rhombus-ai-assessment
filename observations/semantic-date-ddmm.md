# Semantic drift: dates switch from MM/DD to DD/MM

| | |
|---|---|
| **Dataset** | [`datasets/semantic_date_ddmm.csv`](../datasets/semantic_date_ddmm.csv) |
| **Pipeline stopped?** | _FILL: Failed / Warned / Carried on_ |
| **Chatbot fix worked?** | _FILL: Yes / Partly / No / N/A_ |
| **Severity** | _FILL: High / Medium / Low_ |
| **Validation report** | [`data-validation/reports/semantic-date-ddmm.md`](../data-validation/reports/semantic-date-ddmm.md) |

## What I changed
Same columns; every `MM/DD/YYYY` date rewritten as `DD/MM/YYYY` (e.g. `05/29/2024` -> `29/05/2024`; `03/04/2024` now means 3 April, not 4 March). ISO and text dates unchanged.

## What I expected
Unambiguous dates (day > 12) fail month-first parsing -> rows dropped (row count falls). Ambiguous dates (day <= 12) are **silently swapped**. Rhombus is unlikely to notice; validation should catch via `rows.match_reference`, `semantic.date_vs_reference`.

## Steps to reproduce
1. Baseline pipeline `orders-cleaning` is scheduled (S3 `s3://<bucket>/input/orders.csv` -> GCS `gs://<bucket>/output/`), last scheduled run green.
2. Overwrite the S3 source object with `datasets/semantic_date_ddmm.csv` (same key): `aws s3 cp datasets/semantic_date_ddmm.csv s3://<bucket>/input/orders.csv`.
3. Wait for the next scheduled run (do not trigger manually) - _FILL: time of run_.
4. Inspect run status, logs, GCS output; run `python data-validation/validate.py --case semantic-date-ddmm --input datasets/semantic_date_ddmm.csv --output gs://<bucket>/output/<file> --reference datasets/baseline.csv`.
5. Paste the error/log into the AI chatbot, apply its fix, re-run.
6. Restore `datasets/baseline.csv` to S3 before the next case.

## What actually happened
_FILL: run status, duration, what (if anything) landed in GCS. Screenshot:_
![run status](evidence/semantic-date-ddmm-run.png)

## What the logs said
```
FILL: paste log excerpt
```
_FILL: Is the message clear? Does it name the column/file/row?_ ![logs](evidence/semantic-date-ddmm-logs.png)

## What the chatbot said
> FILL: prompt you gave it, and its answer (quote)

_FILL: Was the diagnosis correct?_ ![chatbot](evidence/semantic-date-ddmm-chatbot.png)

## Did the fix work?
_FILL: what the fix changed, re-run result, validation verdict after the fix._

## Schedule afterwards
_FILL: still active / paused / disabled? Did the next scheduled run fire?_

## Validation result
_FILL: verdict + failing checks from the report._

## Assessment
_FILL: one or two sentences - impact for a real customer, severity rationale._
