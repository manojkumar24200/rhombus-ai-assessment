"""Self-tests for validate.py: prove each check catches what it claims to catch.

Uses simulated pipeline outputs (our reference cleaner + deliberate corruption),
so it runs offline:  python -m pytest data-validation -q
"""
import pandas as pd
import pytest

import validate as v

BASELINE = "datasets/baseline.csv"


@pytest.fixture
def write_csv(tmp_path):
    def _write(df, name="out.csv"):
        path = tmp_path / name
        df.to_csv(path, index=False)
        return str(path)
    return _write


def statuses(rep):
    return {c.name: c.status for c in rep.checks}


def test_correct_output_passes_every_check(write_csv):
    good = v.reference_clean(v.read_table(BASELINE))
    rep = v.validate("good", BASELINE, write_csv(good), reference_uri=BASELINE,
                     compare=[write_csv(good.sample(frac=1, random_state=1), "repeat.csv")])
    assert rep.verdict == "PASS", [c for c in rep.checks if c.status != "PASS"]
    assert rep.expected_rows == rep.output_rows == len(good)
    assert rep.input_rows == 132


def test_reference_cleaner_removes_duplicates_and_invalid_rows():
    good = v.reference_clean(v.read_table(BASELINE))
    assert good["order_id"].is_unique
    assert len(good) < 120  # 120 unique orders minus invalid ones
    assert set(good["country"]) <= v.COUNTRIES


def test_uncleaned_output_fails_cleaning_rules(write_csv):
    rep = v.validate("raw", BASELINE, BASELINE)
    s = statuses(rep)
    for check in ["clean.no_duplicate_order_id", "clean.country_canonical",
                  "clean.status_canonical", "schema.order_date_iso", "schema.price_numeric"]:
        assert s[check] == "FAIL", check


def test_dropped_column_fails_schema(write_csv):
    good = v.reference_clean(v.read_table(BASELINE)).drop(columns=["email"])
    rep = v.validate("drop", BASELINE, write_csv(good))
    assert statuses(rep)["schema.columns"] == "FAIL"


def test_price_in_cents_is_caught(write_csv):
    cents = v.reference_clean(v.read_table("datasets/semantic_price_cents.csv"))
    rep = v.validate("cents", "datasets/semantic_price_cents.csv", write_csv(cents), reference_uri=BASELINE)
    s = statuses(rep)
    assert s["semantic.price_magnitude"] == "FAIL"
    assert s["semantic.price_vs_reference"] == "FAIL"


def test_day_month_swap_is_caught(write_csv):
    # A pipeline that keeps parsing month-first silently swaps ambiguous dates.
    swapped = v.reference_clean(v.read_table("datasets/semantic_date_ddmm.csv"))
    rep = v.validate("ddmm", "datasets/semantic_date_ddmm.csv", write_csv(swapped), reference_uri=BASELINE)
    assert statuses(rep)["semantic.date_vs_reference"] == "FAIL"


def test_non_deterministic_output_is_caught(write_csv):
    good = v.reference_clean(v.read_table(BASELINE))
    other = good.copy()
    other.loc[0, "country"] = "Unknown" if other.loc[0, "country"] != "Unknown" else "India"
    rep = v.validate("det", BASELINE, write_csv(good), compare=[write_csv(other, "run2.csv")])
    assert statuses(rep)["determinism"] == "FAIL"


def test_canonical_hash_ignores_row_and_column_order():
    df = pd.DataFrame({"a": ["1", "2"], "b": ["x", "y"]})
    assert v.canonical_hash(df) == v.canonical_hash(df.iloc[::-1][["b", "a"]])
