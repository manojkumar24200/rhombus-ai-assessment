# Validation report: baseline-first-run

- Input: `datasets/baseline.csv`
- Output: `gs://manoj-rhombus-dest/RhombusAI_output_1791200320685.csv`
- Rows: input 132, output 132, expected 110
- Output hash: `573c5cc6474f57a6`
- **Verdict: FAIL**

| Check | Status | Detail |
|---|---|---|
| schema.columns | PASS | 9 expected columns, expected order |
| schema.price_numeric | FAIL | 12 non-numeric price values e.g. ['$7.50', '$79.90', '$7.50'] |
| schema.quantity_integer | FAIL | 4 non-integer quantity values e.g. ['', '', ''] |
| schema.order_date_iso | FAIL | 3 dates not YYYY-MM-DD e.g. ['', '', ''] |
| rows.match_reference | FAIL | input=132 output=132 expected_by_rules=110 (diff +22) |
| clean.no_empty_order_id | FAIL | 1 violating rows e.g. [''] |
| clean.no_duplicate_order_id | FAIL | 23 violating rows e.g. ['ORD-1075', 'ORD-1014', 'ORD-1087'] |
| clean.no_exact_duplicate_rows | FAIL | 16 violating rows e.g. ['ORD-1075', 'ORD-1014', 'ORD-1087'] |
| clean.name_title_case | FAIL | 13 violating rows e.g. ['  RAVI MULLER ', '  PRIYA KIM ', '  TARIQ KHAN '] |
| clean.country_canonical | FAIL | 113 violating rows e.g. ['india', ' US ', 'IND'] |
| clean.status_canonical | FAIL | 98 violating rows e.g. ['PENDING', ' shipped', 'Pending'] |
| clean.email_valid_or_empty | FAIL | 2 violating rows e.g. ['not-an-email', 'bob@@example'] |
| clean.price_non_negative | FAIL | 1 violating rows e.g. ['-19.99'] |
| clean.quantity_in_range | FAIL | 2 violating rows e.g. ['1000000.0', '-3.0'] |
| semantic.price_magnitude | PASS | median price 34.95; 1% of prices outside (1.0, 1000.0) |
| semantic.date_window | PASS | 0 dates outside 2024-01-01..2024-09-30 |
| semantic.price_vs_reference | PASS | 0/120 prices differ from baseline; median ratio 1.00 |
| semantic.date_vs_reference | PASS | 0/120 dates differ from baseline; e.g. [] |
| determinism | PASS | hash 573c5cc6474f57a6; 1 repeat run(s); differing: none |
