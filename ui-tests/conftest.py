import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from pages import Dashboard, LoginPage

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
AUTH_STATE = ROOT / ".auth" / "state.json"


def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} not set in .env")
    return value


@pytest.fixture(scope="session")
def base_url():
    return os.getenv("RHOMBUS_APP_URL", "https://rhombusai.com")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, browser, base_url):
    """Log in once per session and reuse the saved storage state for every test."""
    AUTH_STATE.parent.mkdir(exist_ok=True)
    if not AUTH_STATE.exists() or os.getenv("FRESH_LOGIN") == "1":
        ctx = browser.new_context()
        page = ctx.new_page()
        LoginPage(page).login(base_url, env("RHOMBUS_EMAIL"), env("RHOMBUS_PASSWORD"))
        Dashboard(page).expect_loaded()
        ctx.storage_state(path=str(AUTH_STATE))
        ctx.close()
    return {**browser_context_args, "storage_state": str(AUTH_STATE),
            "viewport": {"width": 1440, "height": 900}}
