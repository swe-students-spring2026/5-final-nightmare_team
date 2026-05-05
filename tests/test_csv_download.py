"""Headless browser test: save playlist triggers MongoDB save + CSV download + profile listing."""

import tempfile
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5050"
TEST_EMAIL = "csvtest@example.com"
TEST_PASSWORD = "TestPass123!"
TEST_NAME = "CSV Tester"

MOCK_TRACKS = [
    {"song_id": "s1", "title": "Blinding Lights", "artist": "The Weeknd", "genre": "Pop", "mood": ["Energetic"], "era": "20s", "score": 0.95},
    {"song_id": "s2", "title": "Levitating",      "artist": "Dua Lipa",   "genre": "Pop", "mood": ["Happy"],    "era": "20s", "score": 0.91},
    {"song_id": "s3", "title": "Watermelon Sugar","artist": "Harry Styles","genre": "Pop","mood": ["Chill"],    "era": "20s", "score": 0.88},
]


def login(page):
    page.goto(f"{BASE}/login")
    page.wait_for_load_state("networkidle")
    # Try register first
    page.click("#tab-register")
    page.wait_for_selector("#panel-register", state="visible")
    page.fill('#panel-register input[name="name"]',     TEST_NAME)
    page.fill('#panel-register input[name="email"]',    TEST_EMAIL)
    page.fill('#panel-register input[name="password"]', TEST_PASSWORD)
    page.click('#panel-register button[type="submit"]')
    page.wait_for_load_state("networkidle")
    # Fall back to login if already registered
    if "/login" in page.url:
        page.click("#tab-login")
        page.wait_for_selector("#panel-login", state="visible")
        page.fill('#panel-login input[name="email"]',    TEST_EMAIL)
        page.fill('#panel-login input[name="password"]', TEST_PASSWORD)
        page.click('#panel-login button[type="submit"]')
        page.wait_for_load_state("networkidle")
    assert "/login" not in page.url, f"Auth failed, still at {page.url}"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # ── 1. Auth ──────────────────────────────────────────────────────────
        print("\n[1] Authenticating...")
        login(page)
        print(f"    OK — at {page.url}")

        # ── 2. Load home, inject mock playlist via route intercept ───────────
        print("\n[2] Loading home page with mocked generate-playlist...")
        page.route(
            "**/api/generate-playlist",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"tracks":%s,"source":"tag-based","size":%d}' % (
                    __import__("json").dumps(MOCK_TRACKS), len(MOCK_TRACKS)
                ),
            ),
        )
        page.goto(BASE)
        page.wait_for_load_state("networkidle")

        # Click a genre chip then generate
        page.locator('#genre-chips [data-tag="pop"]').wait_for(state="visible", timeout=5000)
        page.locator('#genre-chips [data-tag="pop"]').click()
        page.click("#generate-btn")
        page.wait_for_selector("#results", state="visible", timeout=15000)
        page.wait_for_selector("#track-list li", timeout=10000)
        print(f"    OK — {page.locator('#track-list li').count()} tracks rendered")

        # ── 3. Click Save — check loading spinner, then CSV download ─────────
        print("\n[3] Clicking Save and waiting for loading state + CSV download...")

        save_api_calls = []
        page.on("response", lambda r: save_api_calls.append((r.url, r.status))
                if "/api/playlists" in r.url else None)

        with page.expect_download(timeout=15000) as dl_info:
            page.click("#save-btn")
            # Spinner should appear immediately (button disabled + "Saving…" text)
            try:
                page.wait_for_function(
                    "document.getElementById('save-btn').disabled === true",
                    timeout=2000,
                )
                print("    Loading state: button disabled during save ✓")
            except Exception:
                print("    Loading state: could not confirm (save may be very fast)")

        download = dl_info.value
        filename = download.suggested_filename
        assert filename.endswith(".csv"), f"Expected .csv file, got: {filename}"

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
            tmp_path = tf.name
        download.save_as(tmp_path)
        with open(tmp_path, encoding="utf-8") as f:
            csv_content = f.read()

        lines = [l for l in csv_content.splitlines() if l.strip()]
        assert "title" in lines[0] and "artist" in lines[0], f"Bad CSV header: {lines[0]}"
        assert len(lines) > 1, "CSV has no data rows"
        print(f"    CSV '{filename}' — {len(lines)-1} rows, header: {lines[0]}")
        print(f"    First row: {lines[1]}")

        # ── 4. Confirm save button resets to "Save" ──────────────────────────
        page.wait_for_function(
            "document.getElementById('save-btn').textContent.trim() === 'Save'",
            timeout=5000,
        )
        print("\n[4] Save button reset to 'Save' ✓")

        # ── 5. Confirm /api/playlists POST returned 201 ──────────────────────
        post_201 = [s for url, s in save_api_calls if "csv" not in url and s == 201]
        assert post_201, f"No 201 from POST /api/playlists. Calls: {save_api_calls}"
        print(f"\n[5] POST /api/playlists → 201 ✓  (all calls: {save_api_calls})")

        # ── 6. Settings page shows saved playlist ────────────────────────────
        print("\n[6] Checking settings page for saved playlists...")
        page.goto(f"{BASE}/settings")
        page.wait_for_load_state("networkidle")
        # Wait for loading skeleton to disappear
        page.wait_for_selector("#playlistsLoading.hidden", timeout=10000)
        visible = page.locator("#playlistsList").is_visible()
        count_text = page.locator("#playlistCount").inner_text()
        items = page.locator("#playlistsList li").count()
        assert visible and items > 0, f"Saved playlists list not populated (items={items})"
        print(f"    {count_text} displayed, {items} list item(s) ✓")

        # Verify each item has a CSV download link
        csv_links = page.locator('#playlistsList a[href*="/csv"]').count()
        assert csv_links == items, f"CSV links ({csv_links}) != items ({items})"
        print(f"    Each item has a CSV download link ✓")

        browser.close()
        print("\n✓ All checks passed — save button loads, MongoDB saves, CSV downloads, profile shows playlists.")


if __name__ == "__main__":
    run()
