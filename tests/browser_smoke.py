"""Production-browser smoke test for the unified AI Papers frontend."""

from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import ConsoleMessage, Response, sync_playwright


BASE_URL = "http://localhost:3300"
ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "artifacts" / "screenshots"
META = json.loads((ROOT / "web/public/data/meta.json").read_text(encoding="utf-8"))
TOTAL_PAPERS = int(META["totals"]["papers"])
MH_PAPERS = int(META["channels"]["mh"]["papers"])


def main() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    browser_errors: list[str] = []
    http_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        context.add_init_script("localStorage.removeItem('human-ai-papers-read-v1'); localStorage.removeItem('human-ai-papers-favorites-v1');")
        page = context.new_page()
        paper_index_requests: list[str] = []
        explorer_route_requests: list[str] = []

        def on_console(message: ConsoleMessage) -> None:
            if message.type == "error":
                browser_errors.append(message.text)

        def on_response(response: Response) -> None:
            if response.status >= 400:
                http_errors.append(f"{response.status} {response.url}")

        page.on("console", on_console)
        page.on("response", on_response)
        page.on(
            "request",
            lambda request: paper_index_requests.append(request.url)
            if request.url.endswith("/data/papers.json") else None,
        )
        page.on(
            "request",
            lambda request: explorer_route_requests.append(request.url)
            if "_rsc=" in request.url and (
                "/recent?" in request.url or request.url.startswith(f"{BASE_URL}/?")
            ) else None,
        )

        page.goto(BASE_URL, wait_until="networkidle")
        page.get_by_role("heading", name="追踪 AI 如何改变人、组织与心理健康").wait_for()
        page.get_by_role("group", name="研究频道").get_by_text("全部领域").wait_for()
        assert page.locator(".paper-card").count() == 24
        assert f"{TOTAL_PAPERS:,}" in page.locator(".filters-desktop .filter-summary").inner_text()
        assert "篇论文" not in page.locator(".result-heading").inner_text()
        assert page.locator(".result-heading .sort-field").is_visible()
        assert page.locator(".filters-desktop .search-field").is_visible()
        assert not page.locator(".search-field--results").is_visible()
        first_home_card = page.locator(".paper-card").first
        assert first_home_card.locator(".domain-track").count() == 0
        assert first_home_card.locator(".favorite-button").is_visible()
        assert first_home_card.locator(".paper-card__metrics").count() == 0
        assert first_home_card.locator(".paper-card__chinese").count() <= 1
        assert first_home_card.get_by_role("link", name="原文 ↗").get_attribute("href")
        assert page.get_by_role("link", name="PDF ↗").count() > 0
        first_home_card.locator(".paper-card__meta").click()
        assert "paper-card--read" in (first_home_card.get_attribute("class") or "")
        assert len(paper_index_requests) == 1
        explorer_route_requests.clear()

        page.locator(".main-nav").get_by_role("link", name="最近发表").click()
        page.wait_for_url("**/recent")
        page.get_by_role("heading", name="过去 7 天，哪些研究刚刚出现？").wait_for()
        page.get_by_role("group", name="研究频道").get_by_role("button", name=re.compile(r"用户与交互")).click()
        page.wait_for_url("**/recent?domain=ur")
        page.get_by_role("heading", name="用户与交互", exact=True).wait_for()
        explorer_route_requests.clear()
        page.locator(".main-nav").get_by_role("link", name="全部论文").click()
        page.wait_for_url(BASE_URL + "/")
        page.get_by_role("heading", name="追踪 AI 如何改变人、组织与心理健康").wait_for()
        page.get_by_role("heading", name="统一论文流", exact=True).wait_for()
        assert page.get_by_role("group", name="研究频道").get_by_role("button", name=re.compile(r"用户与交互")).get_attribute("aria-pressed") == "false"
        assert len(paper_index_requests) == 1, "route switching downloaded papers.json again"
        assert not explorer_route_requests, "route switching fetched a Next.js page payload"
        page.screenshot(path=str(SCREENSHOT_DIR / "home-desktop.png"), full_page=True)

        page.get_by_role("group", name="研究频道").get_by_role(
            "button", name=re.compile(rf"心理健康\s*{MH_PAPERS} 篇")
        ).click()
        page.wait_for_function(
            "() => new URLSearchParams(window.location.search).get('domain') === 'mh'"
        )
        page.get_by_text("AI和大语言模型时代数字心理健康研究优先事项再审视").wait_for()
        assert str(MH_PAPERS) in page.locator(".filters-desktop .filter-summary").inner_text()
        page.screenshot(path=str(SCREENSHOT_DIR / "mental-health-desktop.png"), full_page=True)

        first_card = page.locator(".paper-card").first
        first_title = first_card.locator(".paper-card__chinese").inner_text()
        first_card.locator(".favorite-button").click()
        first_card.locator(".paper-card__title-link").click()
        page.wait_for_url("**/papers/p_*")
        page.get_by_role("heading", name=first_title).wait_for()
        assert page.locator(".channel-profile").count() >= 1

        page.locator(".main-nav").get_by_role("link", name=re.compile(r"我的收藏")).click()
        page.wait_for_url("**/favorites")
        page.get_by_text(first_title).wait_for()

        page.locator(".main-nav").get_by_role("link", name="最近发表").click()
        page.wait_for_url("**/recent")
        page.get_by_role("heading", name="过去 7 天，哪些研究刚刚出现？").wait_for()

        mobile = context.new_page()
        mobile.set_viewport_size({"width": 390, "height": 844})
        mobile.on("console", on_console)
        mobile.on("response", on_response)
        mobile.goto(BASE_URL, wait_until="networkidle")
        assert mobile.locator(".search-field--results").is_visible()
        mobile.get_by_role("button", name="筛选").click()
        mobile.get_by_role("dialog", name="筛选论文").wait_for()
        mobile.wait_for_timeout(350)
        mobile.screenshot(path=str(SCREENSHOT_DIR / "home-mobile-filters.png"))
        mobile.locator(".filter-drawer__header button").click()
        assert not mobile.get_by_role("dialog", name="筛选论文").is_visible()

        browser.close()

    result = {
        "status": "passed" if not browser_errors and not http_errors else "failed",
        "assertions": [
            f"home shows {TOTAL_PAPERS} unified papers",
            "desktop search stays in the filter rail",
            "sort control replaces the duplicated result count",
            "main navigation clears an active channel when returning to all papers",
            "paper cards use the compact UR-style citation hierarchy",
            "paper cards expose direct source and PDF links when available",
            "clicking a paper card marks it as read",
            f"mental-health channel shows {MH_PAPERS} real scored papers",
            "paper detail opens",
            "favorite persists across routes",
            "recent page uses publication-date copy",
            "mobile search remains visible",
            "mobile filter dialog opens and closes",
        ],
        "browser_errors": browser_errors,
        "http_errors": http_errors,
        "screenshots": [
            str(SCREENSHOT_DIR / "home-desktop.png"),
            str(SCREENSHOT_DIR / "mental-health-desktop.png"),
            str(SCREENSHOT_DIR / "home-mobile-filters.png"),
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
