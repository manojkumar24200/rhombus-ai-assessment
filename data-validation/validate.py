"""Compare a Rhombus AI pipeline output (GCS) with its input (S3).

Checks: schema, row counts, cleaning rules, determinism, semantic drift.

Single run:
    python data-validation/validate.py --case baseline \
        --input datasets/baseline.csv --output gs://my-bucket/out/baseline.csv

Every run listed in a manifest (baseline + all drift cases):
    python data-validation/validate.py --manifest data-validation/runs.json

Paths may be local files, s3://bucket/key or gs://bucket/key.
Exit code is 1 if any check FAILs, so the script can gate CI.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPORTS = Path(__file__).resolve().parent / "reports"

EXPECTED_COLUMNS = ["order_id", "customer_name", "email", "country", "order_date",
                    "product", "quantity", "price", "status"]
COUNTRIES = {"United States", "India", "United Kingdom", "Germany", "Unknown"}
STATUSES = {"shipped", "pending", "cancelled", "unknown"}
COUNTRY_MAP = {"united states": "United States", "usa": "United States", "u.s.": "United States",
               "us": "United States", "india": "India", "in": "India", "ind": "India",
               "united kingdom": "United Kingdom", "uk": "United Kingdom", "u.k.": "United Kingdom",
               "england": "United Kingdom", "germany": "Germany", "de": "Germany"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Plausible unit-price band for this catalogue (USD). Prices in cents land far outside it.
PRICE_BAND = (1.0, 1000.0)


# --------------------------------------------------------------------------- I/O
def read_table(uri: str) -> pd.DataFrame:
    """Read CSV/Parquet from a local path, s3:// or gs:// URI. All columns as strings."""
    if uri.startswith("s3://"):
        import boto3
        bucket, key = uri[5:].split("/", 1)
        body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    elif uri.startswith("gs://"):
        from google.cloud import storage
        bucket, key = uri[5:].split("/", 1)
        body = storage.Client().bucket(bucket).blob(key).download_as_bytes()
    else:
        path = Path(uri)
        if not path.is_absolute():
            path = ROOT / path
        body = path.read_bytes()
    if uri.endswith(".parquet"):
        return pd.read_parquet(io.BytesIO(body)).astype("string")
    return pd.read_csv(io.BytesIO(body), dtype=str, keep_default_na=False)


# ------------------------------------------------------------ reference cleaner
def parse_month_first(value: str):
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_price(value: str):
    try:
        num = float(str(value).strip().replace("$", ""))
    except ValueError:
        return None
    return num if num >= 0 else None


def parse_quantity(value: str):
    try:
        num = float(str(value).strip())
    except ValueError:
        return None
    return int(num) if num.is_integer() and 1 <= num <= 1000 else None


def reference_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Our own implementation of the cleaning rules given to the AI builder.

    Used as the oracle for expected row counts and expected values.
    """
    out = []
    seen = set()
    for _, r in df.iterrows():
        oid = str(r.get("order_id", "")).strip()
        if not oid or oid in seen:
            continue
        d = parse_month_first(r.get("order_date", ""))
        p = parse_price(r.get("price", ""))
        q = parse_quantity(r.get("quantity", ""))
        if d is None or p is None or q is None:
            continue
        seen.add(oid)
        email = str(r.get("email", "")).strip().lower()
        status = str(r.get("status", "")).strip().lower().replace("canceled", "cancelled")
        out.append({
            "order_id": oid,
            "customer_name": str(r.get("customer_name", "")).strip().title(),
            "email": email if EMAIL_RE.match(email) else "",
            "country": COUNTRY_MAP.get(str(r.get("country", "")).strip().lower(), "Unknown"),
            "order_date": d.isoformat(),
            "product": str(r.get("product", "")).strip(),
            "quantity": q,
            "price": round(p, 2),
            "status": status if status in STATUSES else "unknown",
        })
    return pd.DataFrame(out, columns=EXPECTED_COLUMNS)


# ------------------------------------------------------------------- checks
@dataclass
class Check:
    name: str
    status: str  # PASS / WARN / FAIL / SKIP
    detail: str


@dataclass
class Report:
    case: str
    input: str
    output: str
    input_rows: int = 0
    output_rows: int = 0
    expected_rows: int = 0
    output_hash: str = ""
    checks: list[Check] = field(default_factory=list)

    def add(self, name, status, detail):
        self.checks.append(Check(name, status, detail))

    @property
    def verdict(self):
        statuses = {c.status for c in self.checks}
        return "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"


def canonical_hash(df: pd.DataFrame) -> str:
    """Order-independent content hash: sort columns and rows, then sha256."""
    norm = df.reindex(sorted(df.columns), axis=1).astype(str)
    norm = norm.sort_values(list(norm.columns)).reset_index(drop=True)
    return hashlib.sha256(norm.to_csv(index=False).encode()).hexdigest()[:16]


def check_schema(rep: Report, out: pd.DataFrame):
    missing = [c for c in EXPECTED_COLUMNS if c not in out.columns]
    extra = [c for c in out.columns if c not in EXPECTED_COLUMNS]
    if missing:
        rep.add("schema.columns", "FAIL", f"missing columns: {missing}; extra: {extra}")
    elif extra:
        rep.add("schema.columns", "WARN", f"unexpected extra columns: {extra}")
    elif list(out.columns) != EXPECTED_COLUMNS:
        rep.add("schema.columns", "WARN", f"column order changed: {list(out.columns)}")
    else:
        rep.add("schema.columns", "PASS", "9 expected columns, expected order")

    if "price" in out.columns:
        bad = pd.to_numeric(out["price"], errors="coerce").isna() & (out["price"] != "")
        rep.add("schema.price_numeric", "FAIL" if bad.any() else "PASS",
                f"{int(bad.sum())} non-numeric price values" + _sample(out.loc[bad, "price"]))
    if "quantity" in out.columns:
        q = pd.to_numeric(out["quantity"], errors="coerce")
        bad = q.isna() | (q % 1 != 0)
        rep.add("schema.quantity_integer", "FAIL" if bad.any() else "PASS",
                f"{int(bad.sum())} non-integer quantity values" + _sample(out.loc[bad, "quantity"]))
    if "order_date" in out.columns:
        bad = ~out["order_date"].str.match(ISO_DATE_RE)
        rep.add("schema.order_date_iso", "FAIL" if bad.any() else "PASS",
                f"{int(bad.sum())} dates not YYYY-MM-DD" + _sample(out.loc[bad, "order_date"]))


def check_row_counts(rep: Report, inp: pd.DataFrame, out: pd.DataFrame, expected: pd.DataFrame):
    rep.input_rows, rep.output_rows, rep.expected_rows = len(inp), len(out), len(expected)
    if len(out) == 0:
        rep.add("rows.non_empty", "FAIL", "output is empty")
        return
    if len(out) > len(inp):
        rep.add("rows.not_inflated", "FAIL", f"output {len(out)} > input {len(inp)} rows")
    diff = len(out) - len(expected)
    status = "PASS" if diff == 0 else ("WARN" if abs(diff) <= 3 else "FAIL")
    rep.add("rows.match_reference", status,
            f"input={len(inp)} output={len(out)} expected_by_rules={len(expected)} (diff {diff:+d})")


def check_cleaning_rules(rep: Report, out: pd.DataFrame):
    def rule(name, mask, col):
        rep.add(f"clean.{name}", "FAIL" if mask.any() else "PASS",
                f"{int(mask.sum())} violating rows" + _sample(out.loc[mask, col]))

    if "order_id" in out.columns:
        rule("no_empty_order_id", out["order_id"].str.strip() == "", "order_id")
        rule("no_duplicate_order_id", out["order_id"].duplicated(keep=False), "order_id")
    rule("no_exact_duplicate_rows", out.duplicated(keep=False), out.columns[0])
    for col in out.columns:
        if out[col].dtype == object or str(out[col].dtype) == "string":
            ws = out[col] != out[col].str.strip()
            if ws.any():
                rule(f"trimmed.{col}", ws, col)
    if "customer_name" in out.columns:
        rule("name_title_case", out["customer_name"] != out["customer_name"].str.title(), "customer_name")
    if "country" in out.columns:
        rule("country_canonical", ~out["country"].isin(COUNTRIES), "country")
    if "status" in out.columns:
        rule("status_canonical", ~out["status"].isin(STATUSES), "status")
    if "email" in out.columns:
        rule("email_valid_or_empty", (out["email"] != "") & ~out["email"].str.match(EMAIL_RE), "email")
    if "price" in out.columns:
        rule("price_non_negative", pd.to_numeric(out["price"], errors="coerce") < 0, "price")
    if "quantity" in out.columns:
        q = pd.to_numeric(out["quantity"], errors="coerce")
        rule("quantity_in_range", (q < 1) | (q > 1000), "quantity")


def check_semantics(rep: Report, out: pd.DataFrame, reference: pd.DataFrame | None):
    """Catch meaning changes that keep the same structure."""
    # 1. Stand-alone heuristic: price magnitude (dollars -> cents).
    if "price" in out.columns:
        prices = pd.to_numeric(out["price"], errors="coerce").dropna()
        if len(prices):
            med = prices.median()
            lo, hi = PRICE_BAND
            outside = ((prices < lo) | (prices > hi)).mean()
            status = "FAIL" if (med > hi or outside > 0.2) else "PASS"
            rep.add("semantic.price_magnitude", status,
                    f"median price {med:.2f}; {outside:.0%} of prices outside {PRICE_BAND}")

    # 2. Stand-alone heuristic: dates must fall inside the known order window.
    if "order_date" in out.columns:
        dates = pd.to_datetime(out["order_date"], format="%Y-%m-%d", errors="coerce").dropna()
        if len(dates):
            out_of_window = ((dates < "2024-01-01") | (dates > "2024-09-30")).sum()
            rep.add("semantic.date_window", "FAIL" if out_of_window else "PASS",
                    f"{out_of_window} dates outside 2024-01-01..2024-09-30")

    # 3. Against the baseline oracle: same order_id must keep the same meaning.
    if reference is None or "order_id" not in out.columns:
        rep.add("semantic.vs_reference", "SKIP", "no reference supplied")
        return
    joined = out.merge(reference, on="order_id", suffixes=("", "_ref"))
    if joined.empty:
        rep.add("semantic.vs_reference", "WARN", "no order_ids in common with reference")
        return
    if "price" in joined.columns:
        ratio = pd.to_numeric(joined["price"], errors="coerce") / joined["price_ref"].astype(float)
        changed = (ratio.round(4) != 1.0) & ratio.notna()
        rep.add("semantic.price_vs_reference", "FAIL" if changed.any() else "PASS",
                f"{int(changed.sum())}/{len(joined)} prices differ from baseline; "
                f"median ratio {ratio.median():.2f}")
    if "order_date" in joined.columns:
        changed = joined["order_date"] != joined["order_date_ref"]
        sample = joined.loc[changed, ["order_id", "order_date", "order_date_ref"]].head(3).to_dict("records")
        rep.add("semantic.date_vs_reference", "FAIL" if changed.any() else "PASS",
                f"{int(changed.sum())}/{len(joined)} dates differ from baseline; e.g. {sample}")
    missing = set(reference["order_id"]) - set(out["order_id"])
    if missing:
        rep.add("semantic.rows_lost_vs_reference", "WARN",
                f"{len(missing)} valid baseline orders missing from output, e.g. {sorted(missing)[:5]}")


def check_determinism(rep: Report, out: pd.DataFrame, compare_uris: list[str]):
    rep.output_hash = canonical_hash(out)
    if not compare_uris:
        rep.add("determinism", "SKIP", f"hash {rep.output_hash}; no repeat runs supplied")
        return
    hashes = {u: canonical_hash(read_table(u)) for u in compare_uris}
    differing = [u for u, h in hashes.items() if h != rep.output_hash]
    rep.add("determinism", "FAIL" if differing else "PASS",
            f"hash {rep.output_hash}; {len(compare_uris)} repeat run(s); differing: {differing or 'none'}")


def _sample(series: pd.Series, n: int = 3) -> str:
    vals = series.head(n).tolist()
    return f" e.g. {vals}" if vals else ""


# ------------------------------------------------------------------- driver
def validate(case: str, input_uri: str, output_uri: str,
             reference_uri: str | None = None, compare: list[str] | None = None) -> Report:
    rep = Report(case=case, input=input_uri, output=output_uri)
    inp = read_table(input_uri)
    out = read_table(output_uri)
    # The rules' expected result for *this* input (drifted inputs may legitimately differ).
    expected = reference_clean(inp) if set(EXPECTED_COLUMNS) <= set(inp.columns) else \
        reference_clean(inp.rename(columns={"unit_price": "price"}))
    reference = reference_clean(read_table(reference_uri)) if reference_uri else None
    if reference is not None:
        reference = reference.astype({"price": float})

    check_schema(rep, out)
    check_row_counts(rep, inp, out, expected)
    check_cleaning_rules(rep, out)
    check_semantics(rep, out, reference)
    check_determinism(rep, out, compare or [])
    return rep


def write_report(rep: Report):
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"{rep.case}.json").write_text(
        json.dumps({**asdict(rep), "verdict": rep.verdict}, indent=2), encoding="utf-8")
    lines = [f"# Validation report: {rep.case}", "",
             f"- Input: `{rep.input}`", f"- Output: `{rep.output}`",
             f"- Rows: input {rep.input_rows}, output {rep.output_rows}, expected {rep.expected_rows}",
             f"- Output hash: `{rep.output_hash}`", f"- **Verdict: {rep.verdict}**", "",
             "| Check | Status | Detail |", "|---|---|---|"]
    lines += [f"| {c.name} | {c.status} | {c.detail.replace('|', '/')} |" for c in rep.checks]
    (REPORTS / f"{rep.case}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_report(rep: Report):
    print(f"\n=== {rep.case}: {rep.verdict} ===")
    for c in rep.checks:
        print(f"  [{c.status:4}] {c.name}: {c.detail}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", help="JSON list of runs (see runs.example.json)")
    ap.add_argument("--case", default="adhoc")
    ap.add_argument("--input")
    ap.add_argument("--output")
    ap.add_argument("--reference", help="baseline input, used as the semantic oracle")
    ap.add_argument("--compare", nargs="*", default=[], help="outputs of repeat runs (determinism)")
    args = ap.parse_args(argv)

    if args.manifest:
        manifest_path = Path(args.manifest)
        runs = json.loads(manifest_path.read_text(encoding="utf-8"))
    elif args.input and args.output:
        runs = [{"case": args.case, "input": args.input, "output": args.output,
                 "reference": args.reference, "compare": args.compare}]
    else:
        ap.error("give --manifest, or --input and --output")

    summary, failed = [], False
    for run in runs:
        try:
            rep = validate(run["case"], run["input"], run["output"],
                           run.get("reference"), run.get("compare"))
        except Exception as exc:  # unreadable output is itself a finding
            rep = Report(case=run["case"], input=run["input"], output=run["output"])
            rep.add("io.read", "FAIL", f"{type(exc).__name__}: {exc}")
        print_report(rep)
        write_report(rep)
        failed |= rep.verdict == "FAIL"
        summary.append({"case": rep.case, "verdict": rep.verdict, "input_rows": rep.input_rows,
                        "output_rows": rep.output_rows, "expected_rows": rep.expected_rows,
                        "hash": rep.output_hash,
                        "failed_checks": [c.name for c in rep.checks if c.status == "FAIL"]})
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
