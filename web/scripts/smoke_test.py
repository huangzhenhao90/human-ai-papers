"""Production browser smoke test for the unified AI Papers frontend."""

import re
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:3300"


def main() -> None:
    console_errors: list[str] = []
    failed_responses: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("response", lambda response: failed_responses.append(f"{response.status} {response.url}") if response.status >= 400 else None)

        page.goto(BASE_URL, wait_until="networkidle")
        page.get_by_role("heading", name=re.compile("追踪 AI 如何改变")).wait_for()
        assert page.locator(".paper-card").count() > 0, "Home paper stream is empty"
        assert page.get_by_role("group", name="研究频道").get_by_role("button", name=re.compile("心理健康")).count() == 1
        page.screenshot(path="/tmp/human-ai-papers-home.png", full_page=False)

        first_title = page.locator(".paper-card h2").first.inner_text()
        page.get_by_role("searchbox").fill(first_title[:8])
        page.wait_for_url(re.compile(r"[?&]q="))
        page.locator(".paper-card").first.wait_for()
        page.get_by_role("button", name="清空搜索").click()
        page.locator("#desktop-year").select_option("2026")
        page.wait_for_url(re.compile(r"year=2026"))
        page.locator(".filters-desktop .filter-group").nth(2).locator("button").first.click()
        page.wait_for_url(re.compile(r"topic="))
        page.locator(".filters-desktop .filter-group").nth(3).locator("button").first.click()
        page.wait_for_url(re.compile(r"aitype="))
        page.get_by_role("button", name="≥ 4").first.click()
        page.wait_for_url(re.compile(r"minscore=4"))
        page.locator(".sort-field select").select_option("score")
        page.wait_for_url(re.compile(r"sort=score"))
        page.locator(".filters-desktop .clear-filters").click()
        page.wait_for_url(BASE_URL + "/")

        page.get_by_role("group", name="研究频道").get_by_role("button", name=re.compile("心理健康")).click()
        page.get_by_role("heading", name="心理健康", exact=True).wait_for()
        assert page.locator(".paper-card").count() > 0, "Mental-health channel is empty"
        page.get_by_role("button", name=re.compile("全部领域")).click()
        page.get_by_role("button", name=re.compile("组织与商业")).click()
        page.wait_for_url(re.compile(r"domain=ob"))
        assert page.locator(".paper-card").count() > 0, "OB channel is empty"

        first_card = page.locator(".paper-card").first
        first_card.locator(".bookmark-button").click()
        page.get_by_role("link", name=re.compile("我的收藏")).first.click()
        page.wait_for_load_state("networkidle")
        page.locator(".paper-card").first.wait_for()
        assert page.locator(".paper-card").count() == 1, "Favorite did not persist"

        page.locator(".paper-card__title-link").first.click()
        page.wait_for_url(re.compile(r"/papers/"))
        page.wait_for_load_state("networkidle")
        assert re.search(r"/papers/", page.url), "Detail route did not open"
        assert page.locator(".paper-detail h1").count() == 1, "Detail heading is missing"
        assert page.locator(".channel-profile").count() >= 1, "Channel profile is missing"

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(BASE_URL, wait_until="networkidle")
        page.get_by_role("button", name=re.compile("筛选")).click()
        assert page.get_by_role("dialog").is_visible(), "Mobile filter drawer did not open"
        page.keyboard.press("Escape")
        assert not page.get_by_role("dialog").is_visible(), "Mobile filter drawer did not close"
        page.screenshot(path="/tmp/human-ai-papers-mobile.png", full_page=False)

        page.goto(f"{BASE_URL}/recent", wait_until="networkidle")
        page.get_by_role("heading", level=1, name=re.compile("过去 7 天")).wait_for()
        page.goto(f"{BASE_URL}/about", wait_until="networkidle")
        page.get_by_role("heading", name=re.compile("不是三个论文站")).wait_for()

        browser.close()

    if console_errors:
        raise AssertionError(f"Browser console errors: {console_errors}")
    if failed_responses:
        raise AssertionError(f"Failed HTTP responses: {failed_responses}")

    for screenshot in [Path("/tmp/human-ai-papers-home.png"), Path("/tmp/human-ai-papers-mobile.png")]:
        assert screenshot.exists() and screenshot.stat().st_size > 0
    print("Smoke test passed: home, domain, favorite, detail, mobile drawer, recent, about")


if __name__ == "__main__":
    main()
