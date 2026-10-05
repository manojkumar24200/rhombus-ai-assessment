"""Run one drift case end-to-end against the live scheduled pipeline.

    python data-validation/run_drift.py schema-rename-column
    python data-validation/run_drift.py restore          # put baseline back

1. Uploads datasets/<case>.csv over the pipeline's S3 source object.
2. Waits (polling GCS, no fixed sleep) for the next scheduled run's output.
3. Validates it against the drifted input and the baseline oracle.
4. Leaves the drifted file in S3 (to test the chatbot's fix); run `restore` afterwards.
Appends timings to data-validation/reports/runs_log.json.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from dotenv import load_dotenv
from google.cloud import storage

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(ROOT / "gcp-key.json"))
sys.path.insert(0, str(Path(__file__).parent))
import validate  # noqa: E402

S3_KEY = os.getenv("S3_SOURCE_KEY", "input/baseline.csv")
WAIT_S = int(os.getenv("DRIFT_WAIT_S", "600"))
LOG = Path(__file__).parent / "reports" / "runs_log.json"


def upload(local: str):
    boto3.client("s3", region_name=os.getenv("AWS_REGION")).upload_file(
        str(ROOT / local), os.getenv("S3_BUCKET"), S3_KEY)
    print(f"S3 <- {local}")


def wait_for_new_output(bucket, seen, since):
    deadline = time.time() + WAIT_S
    while time.time() < deadline:
        new = [b for b in bucket.list_blobs() if b.name not in seen]
        if new:
            return max(new, key=lambda b: b.time_created)
        time.sleep(10)  # polling interval, not a fixed wait for the result
    return None


def main(case: str):
    if case == "restore":
        upload("datasets/baseline.csv")
        return 0
    dataset = f"datasets/{case.replace('-', '_')}.csv"
    bucket = storage.Client().bucket(os.getenv("GCS_BUCKET"))
    seen = {b.name for b in bucket.list_blobs()}
    started = datetime.now(timezone.utc)
    upload(dataset)
    blob = wait_for_new_output(bucket, seen, started)
    if blob is None:
        print(f"NO OUTPUT in {WAIT_S}s -> pipeline likely stopped/failed. Check Rhombus Logs + schedule.")
        entry = {"case": case, "output": None, "verdict": "NO_OUTPUT"}
    else:
        print(f"GCS -> {blob.name} ({blob.size} B) at {blob.time_created}")
        rep = validate.validate(case, dataset, f"gs://{bucket.name}/{blob.name}",
                                reference_uri="datasets/baseline.csv")
        validate.print_report(rep)
        validate.write_report(rep)
        entry = {"case": case, "output": blob.name, "verdict": rep.verdict,
                 "rows": rep.output_rows, "seconds_after_upload":
                     round((blob.time_created - started).total_seconds())}
    # Drifted file stays in S3 so the chatbot fix can be tested; run `restore` afterwards.
    LOG.parent.mkdir(exist_ok=True)
    log = json.loads(LOG.read_text()) if LOG.exists() else []
    log.append({**entry, "uploaded_at": started.isoformat()})
    LOG.write_text(json.dumps(log, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
