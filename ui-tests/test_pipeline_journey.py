"""End-to-end customer journey: S3 source -> AI-built cleaning pipeline -> GCS destination -> schedule.

Run:  python -m pytest ui-tests --headed          (watch it)
      python -m pytest ui-tests --tracing retain-on-failure

No fixed sleeps: every wait is an expect() on a real UI condition.
"""
import os
import re
from pathlib import Path

from playwright.sync_api import Page, expect

from conftest import env
from pages import AI_TIMEOUT, RUN_TIMEOUT, ConnectionsPage, Dashboard, PipelineBuilder, RunHistory, SchedulePanel

PROMPT = (Path(__file__).resolve().parent.parent / "datasets" / "ai_builder_prompt.txt").read_text(encoding="utf-8")


def test_login_lands_on_dashboard(page: Page, base_url):
    page.goto(base_url)
    Dashboard(page).expect_loaded()


def test_s3_source_connection_exists(page: Page, base_url):
    page.goto(base_url)
    conns = ConnectionsPage(page)
    conns.open()
    name = os.getenv("S3_CONNECTION_NAME", "orders-s3")
    if not conns.connection(name).is_visible():
        conns.add_s3(name, env("AWS_ACCESS_KEY_ID"), env("AWS_SECRET_ACCESS_KEY"),
                     env("S3_BUCKET"), os.getenv("AWS_REGION", "us-east-1"))
    expect(conns.connection(name)).to_be_visible(timeout=30000)
    # A saved connection must not be in an error state
    expect(page.get_by_text(re.compile(r"connection failed|invalid credentials", re.I))).to_have_count(0)


def test_ai_builder_creates_cleaning_steps(page: Page, base_url):
    page.goto(base_url)
    builder = PipelineBuilder(page)
    builder.open(env("RHOMBUS_PIPELINE_NAME"))
    expect(builder.source()).to_be_visible(timeout=30000)
    builder.ask_ai(PROMPT)
    # The AI must turn the prompt into real transformation steps, not just reply in chat.
    builder.expect_ai_built_steps(minimum=2)
    expect(page.get_by_text(re.compile(r"something went wrong|error generating", re.I))).to_have_count(0)


def test_gcs_destination_configured(page: Page, base_url):
    page.goto(base_url)
    builder = PipelineBuilder(page)
    builder.open(env("RHOMBUS_PIPELINE_NAME"))
    expect(builder.destination()).to_be_visible(timeout=30000)
    expect(page.get_by_text(os.getenv("GCS_BUCKET", "")).first).to_be_visible()


def test_schedule_active_and_last_scheduled_run_succeeded(page: Page, base_url):
    page.goto(base_url)
    PipelineBuilder(page).open(env("RHOMBUS_PIPELINE_NAME"))
    schedule = SchedulePanel(page)
    schedule.open()
    expect(schedule.status()).to_be_visible(timeout=30000)

    history = RunHistory(page)
    history.open()
    # Real outcome: the latest run finished successfully (polls the UI, no sleep).
    expect(history.latest_status()).to_contain_text(re.compile(r"success|succeeded|completed", re.I),
                                                    timeout=RUN_TIMEOUT)
