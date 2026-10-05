"""Page objects for the Rhombus AI web app.

ALL selectors live here. They use accessible roles/visible text (resilient to CSS changes).
If the UI wording differs, record the real flow once with
    python -m playwright codegen https://rhombusai.com
and update only this file.
"""
import os
import re

from playwright.sync_api import Page, expect

# Long operations (AI generation, pipeline runs) get generous *condition-based* waits.
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT_MS", "180000"))
RUN_TIMEOUT = int(os.getenv("RUN_TIMEOUT_MS", "900000"))


class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def login(self, base_url: str, email: str, password: str):
        self.page.goto(base_url)
        # Landing page -> app sign-in
        sign_in = self.page.get_by_role("link", name=re.compile(r"log ?in|sign ?in", re.I)).first
        if sign_in.is_visible():
            sign_in.click()
        self.page.get_by_label(re.compile("email", re.I)).fill(email)
        self.page.get_by_label(re.compile("password", re.I)).fill(password)
        self.page.get_by_role("button", name=re.compile(r"log ?in|sign ?in|continue", re.I)).click()


class Dashboard:
    def __init__(self, page: Page):
        self.page = page
        self.user_menu = page.get_by_role("button", name=re.compile(r"account|profile|user", re.I))
        self.new_project = page.get_by_role("button", name=re.compile(r"new (project|pipeline|workflow)", re.I))

    def expect_loaded(self):
        expect(self.page).not_to_have_url(re.compile(r"login|sign-?in", re.I), timeout=30000)
        expect(self.new_project.or_(self.user_menu).first).to_be_visible(timeout=30000)


class ConnectionsPage:
    """Data connectors (S3 source / GCS destination)."""

    def __init__(self, page: Page):
        self.page = page

    def open(self):
        self.page.get_by_role("link", name=re.compile(r"connect|integration|data source", re.I)).first.click()

    def connection(self, name: str):
        return self.page.get_by_text(name, exact=False).first

    def add_s3(self, name: str, access_key: str, secret_key: str, bucket: str, region: str):
        self.page.get_by_role("button", name=re.compile(r"add|new connection", re.I)).first.click()
        self.page.get_by_text(re.compile(r"amazon s3|\bs3\b", re.I)).first.click()
        self.page.get_by_label(re.compile("name", re.I)).first.fill(name)
        self.page.get_by_label(re.compile("access key", re.I)).first.fill(access_key)
        self.page.get_by_label(re.compile("secret", re.I)).first.fill(secret_key)
        self.page.get_by_label(re.compile("bucket", re.I)).first.fill(bucket)
        region_field = self.page.get_by_label(re.compile("region", re.I)).first
        if region_field.is_visible():
            region_field.fill(region)
        self.page.get_by_role("button", name=re.compile(r"save|connect|test", re.I)).last.click()


class PipelineBuilder:
    def __init__(self, page: Page):
        self.page = page
        self.chat_input = page.get_by_role("textbox", name=re.compile(r"ask|message|prompt|describe", re.I)).last
        self.send = page.get_by_role("button", name=re.compile(r"send|submit|generate", re.I)).last
        # Transformation steps/nodes rendered by the AI builder
        self.steps = page.locator("[data-testid*='node'], .react-flow__node")

    def open(self, pipeline_name: str):
        self.page.get_by_text(pipeline_name, exact=False).first.click()

    def ask_ai(self, prompt: str):
        self.chat_input.fill(prompt)
        self.send.click()

    def expect_ai_built_steps(self, minimum: int = 2):
        expect(self.steps.nth(minimum - 1)).to_be_visible(timeout=AI_TIMEOUT)

    def destination(self):
        return self.page.get_by_text(re.compile(r"google cloud storage|\bgcs\b", re.I)).first

    def source(self):
        return self.page.get_by_text(re.compile(r"amazon s3|\bs3\b", re.I)).first


class SchedulePanel:
    def __init__(self, page: Page):
        self.page = page

    def open(self):
        self.page.get_by_role("button", name=re.compile(r"schedul", re.I)).first.click()

    def status(self):
        return self.page.get_by_text(re.compile(r"(every|hourly|daily|cron|next run)", re.I)).first


class RunHistory:
    def __init__(self, page: Page):
        self.page = page
        self.rows = page.get_by_role("row")

    def open(self):
        self.page.get_by_role("tab", name=re.compile(r"run|history|log", re.I)).or_(
            self.page.get_by_role("link", name=re.compile(r"run|history|log", re.I))).first.click()

    def latest_status(self):
        return self.rows.nth(1)
