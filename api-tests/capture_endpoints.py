"""Record the backend API calls the Rhombus web app makes (the 'network tab', automated).

    python api-tests/capture_endpoints.py

A browser opens; log in and click through your pipeline (runs, schedule, connections).
Close the browser window when done. Output:
  - api-tests/captured_endpoints.json   method, URL, status, response-body preview
                                        (Authorization headers redacted; safe to commit)
  - .auth/token.txt                     the bearer token seen (git-ignored); copy to .env
Use the URLs found here to fill RHOMBUS_API_BASE / *_PATH values in .env.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
OUT = Path(__file__).resolve().parent / "captured_endpoints.json"
TOKEN = ROOT / ".auth" / "token.txt"


def main():
    calls, token = {}, None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        def on_response(resp):
            nonlocal token
            req = resp.request
            if req.resource_type not in ("xhr", "fetch"):
                return
            auth = req.headers.get("authorization")
            if auth and auth.lower().startswith("bearer "):
                token = auth.split(" ", 1)[1]
            key = f"{req.method} {req.url.split('?')[0]}"
            try:
                preview = resp.text()[:300]
            except Exception:
                preview = "<unavailable>"
            calls[key] = {"method": req.method, "url": req.url, "status": resp.status,
                          "auth": "bearer" if auth else ("cookie" if "cookie" in req.headers else "none"),
                          "response_preview": preview}

        page.on("response", on_response)
        page.goto(os.getenv("RHOMBUS_APP_URL", "https://rhombusai.com"))
        page.wait_for_event("close", timeout=0)  # until you close the window
        browser.close()

    OUT.write_text(json.dumps(sorted(calls.values(), key=lambda c: c["url"]), indent=2), encoding="utf-8")
    print(f"{len(calls)} distinct API calls -> {OUT}")
    if token:
        TOKEN.parent.mkdir(exist_ok=True)
        TOKEN.write_text(token, encoding="utf-8")
        print(f"bearer token saved to {TOKEN} (copy into .env as RHOMBUS_API_TOKEN)")


if __name__ == "__main__":
    main()
