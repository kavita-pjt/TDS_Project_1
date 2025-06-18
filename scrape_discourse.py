import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

# === CONFIGURATION ===
BASE_URL = "https://discourse.onlinedegree.iitm.ac.in"
CATEGORY_ID = 34
CATEGORY_SLUG = "tds-kb"
CATEGORY_JSON_URL = f"{BASE_URL}/c/courses/{CATEGORY_SLUG}/{CATEGORY_ID}.json"
AUTH_STATE_FILE = "auth.json"

# Set date range — optional. Comment out to fetch everything.
DATE_FROM = datetime(2025, 1, 1)
DATE_TO = datetime(2025, 4, 14)

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")

def login_and_save_auth(playwright):
    print("🔐 No auth found. Launching browser for manual login...")
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{BASE_URL}/login")
    print("🌐 Log in manually (e.g. with Google), then press ▶️ Resume.")
    page.pause()
    context.storage_state(path=AUTH_STATE_FILE)
    print("✅ Login session saved.")
    browser.close()

def is_authenticated(page):
    try:
        page.goto(CATEGORY_JSON_URL, timeout=10000)
        content = page.content()
        return "topic_list" in content
    except Exception:
        return False

def scrape_posts(playwright):
    print("🔍 Scraping started using saved session...")
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(storage_state=AUTH_STATE_FILE)
    page = context.new_page()

    all_topics = []
    page_num = 0
    while True:
        paginated_url = f"{CATEGORY_JSON_URL}?page={page_num}"
        print(f"📦 Fetching page {page_num}...")
        page.goto(paginated_url)
        
        try:
            text = page.inner_text("pre")
            data = json.loads(text)
        except Exception:
            print("❌ Could not parse JSON — check login or access.")
            break

        topics = data.get("topic_list", {}).get("topics", [])
        if not topics:
            break

        all_topics.extend(topics)
        page_num += 1

    print(f"📄 Found {len(all_topics)} total topics.")

    os.makedirs("downloaded_threads", exist_ok=True)
    saved_count = 0

    for topic in all_topics:
        created_at = parse_date(topic["created_at"])

        # OPTIONAL: Remove this check to fetch all topics
        if not (DATE_FROM <= created_at <= DATE_TO):
            continue

        topic_url = f"{BASE_URL}/t/{topic['slug']}/{topic['id']}.json"
        print(f"🧵 Fetching topic: {topic_url}")
        page.goto(topic_url)

        try:
            text = page.inner_text("pre")
            topic_data = json.loads(text)
        except Exception:
            print(f"⚠️ Failed to fetch topic: {topic_url}")
            continue

        for post in topic_data.get("post_stream", {}).get("posts", []):
            if "cooked" in post:
                post["cooked"] = BeautifulSoup(post["cooked"], "html.parser").get_text()

        filename = f"{topic['slug']}_{topic['id']}.json"
        filepath = os.path.join("downloaded_threads", filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(topic_data, f, indent=2)

        saved_count += 1

    print(f"✅ Finished. Saved {saved_count} threads to 'downloaded_threads/'")
    browser.close()

def main():
    with sync_playwright() as playwright:
        if not os.path.exists(AUTH_STATE_FILE):
            login_and_save_auth(playwright)
        else:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(storage_state=AUTH_STATE_FILE)
            page = context.new_page()

            if not is_authenticated(page):
                print("⚠️ Session expired or invalid. Please log in again.")
                browser.close()
                login_and_save_auth(playwright)
            else:
                print("✅ Using existing authenticated session.")
                browser.close()

        scrape_posts(playwright)

if __name__ == "__main__":
    main()
