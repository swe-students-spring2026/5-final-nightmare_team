"""Headless browser smoke tests for the composed webapp + ML recommender."""

# pylint: disable=missing-function-docstring,too-many-statements

from playwright.sync_api import expect, sync_playwright

BASE = "http://localhost:5050"


def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("\n[1] Home page loads recommender UI...")
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        assert "Recommendations" in page.title()
        expect(page.locator("h1")).to_contain_text("Music Recommendations")
        print("    OK - recommender shell loaded")

        print("\n[2] Last.fm seed songs render...")
        page.wait_for_selector("#seedSongList .song-row", timeout=30000)
        seed_rows = page.locator("#seedSongList .song-row")
        assert seed_rows.count() > 0
        print(f"    OK - {seed_rows.count()} seed rows")

        print("\n[3] Catalog paging and filtering work...")
        first_page_title = page.locator("#seedSongList .song-row h3").first.inner_text()
        page.click("#nextCatalogBtn")
        expect(page.locator("#pageLabel")).to_contain_text("Page 2", timeout=10000)
        second_page_title = page.locator(
            "#seedSongList .song-row h3"
        ).first.inner_text()
        assert first_page_title != second_page_title
        page.fill("#catalogSearch", "Radiohead")
        page.click("#filterBtn")
        expect(page.locator("#pageLabel")).to_contain_text("Page 1", timeout=10000)
        expect(page.locator("#seedSongList .song-row").first).to_contain_text(
            "Radiohead", timeout=10000
        )
        print("    OK - next page and search filter")

        print("\n[4] Like and dislike actions post feedback; dislike hides row...")
        response_events = []
        page.on(
            "response",
            lambda res: (
                response_events.append((res.url, res.status))
                if "/api/events" in res.url
                else None
            ),
        )
        before_dislike_count = page.locator("#seedSongList .song-row").count()
        page.locator("#seedSongList button[data-action='like']").first.click()
        page.locator("#seedSongList button[data-action='dislike']").nth(1).click()
        page.wait_for_function(
            "count => document.querySelectorAll('#seedSongList .song-row').length === count - 1",
            arg=before_dislike_count,
            timeout=10000,
        )
        after_dislike_count = page.locator("#seedSongList .song-row").count()
        assert any(status == 201 for _, status in response_events), response_events
        assert after_dislike_count == before_dislike_count - 1
        expect(page.locator("#hiddenLabel")).to_contain_text("hidden", timeout=10000)
        print(f"    OK - feedback responses: {response_events}")

        print("\n[5] Train recommendations switches to model source...")
        page.click("#trainBtn")
        expect(page.locator("#modelBadge")).to_contain_text(
            "Model Source", timeout=30000
        )
        expect(page.locator("#recommendationStatus")).to_contain_text(
            "Model trained", timeout=30000
        )
        print("    OK - model trained")

        print("\n[6] Recommendations render from backend...")
        page.click("#recommendationBtn")
        page.wait_for_selector("#recommendationList .song-row", timeout=30000)
        rec_rows = page.locator("#recommendationList .song-row")
        assert rec_rows.count() > 0
        print(f"    OK - {rec_rows.count()} recommendation rows")

        print("\n[7] Similar songs affordance renders related tracks...")
        page.locator("#recommendationList button[data-action='similar']").first.click()
        page.wait_for_selector(
            "#similarSection:not(.hidden) #similarList .song-row", timeout=30000
        )
        similar_rows = page.locator("#similarList .song-row")
        assert similar_rows.count() > 0
        print(f"    OK - {similar_rows.count()} similar rows")

        print("\n[8] Save recommendations uses session-owned user...")
        save_responses = []
        page.on(
            "response",
            lambda res: (
                save_responses.append((res.url, res.status))
                if "/api/playlists" in res.url
                else None
            ),
        )
        page.click("#saveBtn")
        expect(page.locator("#saveToast")).to_contain_text("saved", timeout=10000)
        assert any(status == 201 for _, status in save_responses), save_responses
        print(f"    OK - save responses: {save_responses}")

        print("\n[9] Health check reports composed Mongo connection...")
        page.click("#healthBtn")
        expect(page.locator("#healthLabel")).to_contain_text(
            "DB Connected", timeout=10000
        )
        print("    OK - health connected")

        browser.close()
        print("\nAll browser smoke tests passed.")


if __name__ == "__main__":
    run_tests()
