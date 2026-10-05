"""Backend API tests for Rhombus AI (endpoints discovered via capture_endpoints.py / DevTools).

Configure in .env:
    RHOMBUS_API_BASE=https://<api host>           e.g. from captured_endpoints.json
    RHOMBUS_API_TOKEN=<bearer token>              from .auth/token.txt
    RHOMBUS_PIPELINES_PATH=/<path listing pipelines/projects>
    RHOMBUS_PIPELINE_NAME=<name of your pipeline>
    RHOMBUS_RUNS_PATH=/<path listing runs of the pipeline>   (optional)
    RHOMBUS_LOGIN_PATH=/<login endpoint>                      (optional)

Run:  python -m pytest api-tests -v
"""
import json
import os
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
TIMEOUT = 30


def env(name):
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} not set in .env")
    return value


@pytest.fixture(scope="module")
def api():
    return env("RHOMBUS_API_BASE").rstrip("/")


@pytest.fixture(scope="module")
def auth_headers():
    return {"Authorization": f"Bearer {env('RHOMBUS_API_TOKEN')}", "Accept": "application/json"}


def items(body):
    """Pipelines may come back as a bare list or wrapped ({data|results|items: [...]})."""
    if isinstance(body, list):
        return body
    for key in ("data", "results", "items", "projects", "pipelines", "workflows"):
        if isinstance(body.get(key), list):
            return body[key]
    return []


# ----------------------------------------------------------------- positive
def test_list_pipelines_returns_my_pipeline(api, auth_headers):
    resp = requests.get(api + env("RHOMBUS_PIPELINES_PATH"), headers=auth_headers, timeout=TIMEOUT)
    assert resp.status_code == 200, resp.text[:300]
    assert "application/json" in resp.headers.get("Content-Type", "")
    pipelines = items(resp.json())
    assert pipelines, f"no pipelines in response: {resp.text[:300]}"
    names = json.dumps(pipelines)
    assert env("RHOMBUS_PIPELINE_NAME") in names, "created pipeline not returned by the API"


def test_latest_run_has_a_status(api, auth_headers):
    resp = requests.get(api + env("RHOMBUS_RUNS_PATH"), headers=auth_headers, timeout=TIMEOUT)
    assert resp.status_code == 200, resp.text[:300]
    runs = items(resp.json())
    assert runs, "pipeline has no runs"
    assert any(k in runs[0] for k in ("status", "state")), f"run without status: {runs[0]}"


# ----------------------------------------------------------------- negative
def test_unauthenticated_request_is_rejected(api):
    resp = requests.get(api + env("RHOMBUS_PIPELINES_PATH"), headers={"Accept": "application/json"},
                        timeout=TIMEOUT)
    assert resp.status_code in (401, 403), f"expected 401/403, got {resp.status_code}: {resp.text[:300]}"
    # No pipeline data may leak in the error body
    assert env("RHOMBUS_PIPELINE_NAME") not in resp.text


def test_invalid_token_is_rejected(api):
    resp = requests.get(api + env("RHOMBUS_PIPELINES_PATH"),
                        headers={"Authorization": "Bearer invalid.token.value", "Accept": "application/json"},
                        timeout=TIMEOUT)
    assert resp.status_code in (401, 403), f"expected 401/403, got {resp.status_code}: {resp.text[:300]}"
    assert env("RHOMBUS_PIPELINE_NAME") not in resp.text


def test_login_with_wrong_password_is_rejected(api):
    resp = requests.post(api + env("RHOMBUS_LOGIN_PATH"),
                         json={"email": env("RHOMBUS_EMAIL"), "password": "definitely-wrong-password-123"},
                         timeout=TIMEOUT)
    assert 400 <= resp.status_code < 500, f"got {resp.status_code}: {resp.text[:300]}"
    assert "token" not in resp.text.lower() or "invalid" in resp.text.lower()


def test_unknown_pipeline_returns_404(api, auth_headers):
    resp = requests.get(api + env("RHOMBUS_PIPELINES_PATH").rstrip("/") + "/00000000-0000-0000-0000-000000000000",
                        headers=auth_headers, timeout=TIMEOUT)
    assert resp.status_code in (400, 403, 404), f"got {resp.status_code}: {resp.text[:300]}"
