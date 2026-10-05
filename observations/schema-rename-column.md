# Schema drift: rename a column

| | |
|---|---|
| **Dataset** | [`datasets/schema_rename_column.csv`](../datasets/schema_rename_column.csv) |
| **Pipeline stopped?** | **Failed** (stopped at node `orders_fields_cleaned`; nothing written to GCS) |
| **Chatbot fix worked?** | **No** (2 attempts) |
| **Severity** | **Medium**: safe failure, but the error is unclear and the chatbot could not repair it |
| **Validation report** | [`data-validation/reports/schema-rename-column.md`](../data-validation/reports/schema-rename-column.md) |

## What I changed
Renamed `price` -> `unit_price`. Values unchanged.

## What I expected
Pipeline should **fail or warn** that `price` is missing. Risk: price-cleaning steps are skipped and uncleaned `unit_price` (with `$`, negatives, `abc`) reaches GCS.

## Steps to reproduce
1. Baseline pipeline `orders-cleaning` is scheduled (S3 `s3://<bucket>/input/baseline.csv` -> GCS `gs://<bucket>/output/`), last scheduled run green.
2. Overwrite the S3 source object with `datasets/schema_rename_column.csv` (same key): `aws s3 cp datasets/schema_rename_column.csv s3://<bucket>/input/baseline.csv`.
3. Trigger the run (▶) at 11:06 PM local. The scheduled run was not used because the schedule was not firing; see [baseline-ai-build.md](baseline-ai-build.md) Finding 5.
4. Inspect run status, logs, GCS output; run `python data-validation/validate.py --case schema-rename-column --input datasets/schema_rename_column.csv --output gs://<bucket>/output/<file> --reference datasets/baseline.csv`.
5. Paste the error/log into the AI chatbot, apply its fix, re-run.
6. Restore `datasets/baseline.csv` to S3 before the next case.

## What actually happened
The run failed after ~4 s at the first Custom (LLM) node. **No object was written to GCS** (latest object is still the baseline run `RhombusAI_output_1791200896216.csv`), so no bad data was published.

## What the logs said
```
11:06:15 PM  Pipeline failed at orders_fields_cleaned: LLM execution failed (code_sha=1fecff7b9a1a): 'price'
             --- Generated code --- import pandas as...
11:06:15 PM  Pipeline execution completed successfully.      <-- same second, contradicts the failure
11:06:11 PM  Pipeline execution started.

Expanded failure (later attempt):
"reason": "LLM execution failed (code_sha=5e06f8bf1c19): 'price'
--- Generated code ---
import pandas as pd ..."
"nodeId": "llm_node_1", "nodeLabel": "orders_fields_cleaned"
```
**Partly clear.** The only clue is `'price'`, a bare Python `KeyError` followed by truncated generated code. It never says *"column `price` not found in input; found `unit_price`"*. Two further problems:
- **Contradictory logs:** "Pipeline failed" and "Pipeline execution completed successfully" are logged at the same second, so an alert keyed on "completed successfully" would report this run as green.
- **The code is regenerated on each run:** the `code_sha` changed between attempts (`1fecff7b9a1a` → `5e06f8bf1c19`). The Custom node asks the LLM to write new pandas code on every execution, which also explains the non-deterministic baseline output (`None` vs `Unknown`). ![logs](evidence/schema-rename-column-logs.png) · [full error JSON](evidence/schema-rename-column-error.json)

## What the chatbot said
> Used the **Ask Chatbot** button on the failed log entry (twice).

The chatbot was reached in one click from the error, which is good UX, but it **did not produce a working fix on either attempt**.

## Did the fix work?
**No.** Two chatbot attempts; the pipeline still failed on re-run. The obvious fix (map `unit_price` → `price`, or make the step tolerant of either name) was not achieved.

## Schedule afterwards
Schedule stayed **Active** (`*/15 * * * *`); it was not paused or disabled after the failure. No alert or notification was observed.

## Validation result
No output was produced, so there was nothing to validate. The validator would have caught it anyway: `schema.columns` FAIL (missing `price`).

## Assessment
Failing closed is the right behaviour: no corrupted file reached GCS. But the error is a raw `KeyError`, the logs contradict themselves, and the built-in chatbot could not repair a one-column rename, so a customer would need to edit the pipeline by hand. **Medium.**
