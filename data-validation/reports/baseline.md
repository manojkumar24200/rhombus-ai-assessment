# Validation report: baseline

- Input: `datasets/baseline.csv`
- Output: `gs://manoj-rhombus-dest/RhombusAI_output_1791200896216.csv`
- Rows: input 132, output 110, expected 110
- Output hash: `fa3b48f6dff6abd9`
- **Verdict: FAIL**

| Check | Status | Detail |
|---|---|---|
| schema.columns | PASS | 9 expected columns, expected order |
| schema.price_numeric | PASS | 0 non-numeric price values |
| schema.quantity_integer | PASS | 0 non-integer quantity values |
| schema.order_date_iso | PASS | 0 dates not YYYY-MM-DD |
| rows.match_reference | PASS | input=132 output=110 expected_by_rules=110 (diff +0) |
| clean.no_empty_order_id | PASS | 0 violating rows |
| clean.no_duplicate_order_id | PASS | 0 violating rows |
| clean.no_exact_duplicate_rows | PASS | 0 violating rows |
| clean.name_title_case | PASS | 0 violating rows |
| clean.country_canonical | PASS | 0 violating rows |
| clean.status_canonical | PASS | 0 violating rows |
| clean.email_valid_or_empty | PASS | 0 violating rows |
| clean.price_non_negative | PASS | 0 violating rows |
| clean.quantity_in_range | PASS | 0 violating rows |
| semantic.price_magnitude | PASS | median price 34.95; 0% of prices outside (1.0, 1000.0) |
| semantic.date_window | PASS | 0 dates outside 2024-01-01..2024-09-30 |
| semantic.price_vs_reference | PASS | 0/110 prices differ from baseline; median ratio 1.00 |
| semantic.date_vs_reference | PASS | 0/110 dates differ from baseline; e.g. [] |
| determinism | FAIL | hash fa3b48f6dff6abd9; 2 repeat run(s); differing: ['gs://manoj-rhombus-dest/RhombusAI_output_1791200882577.csv'] |
