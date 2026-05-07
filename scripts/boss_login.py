"""
BOSS直聘 login helper.
Opens a Chrome window for you to log in manually, then saves the session.
After this, the crawler can reuse your login automatically.

Run: python scripts/boss_login.py
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chrome_dev_profile", "boss")
os.makedirs(PROFILE_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        PROFILE_DIR,
        headless=False,
        viewport={"width": 1400, "height": 900},
        locale="zh-CN",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = browser.pages[0] if browser.pages else browser.new_page()

    page.goto("https://www.zhipin.com/web/user/?ka=header-login")
    print("\n" + "=" * 50)
    print("Please log in to BOSS (scan QR code with app)")
    print("The browser will stay open. Close it when done.")
    print("Session will be saved automatically.")
    print("=" * 50 + "\n")

    # Wait for user to login (check for redirect away from login page)
    try:
        page.wait_for_url("**/web/geek/**", timeout=300000)
        print("Login detected! Saving profile...")
        time.sleep(2)
    except:
        print("Waiting for manual close...")

    browser.close()
    print(f"Profile saved to {PROFILE_DIR}")
    print("You can now run the boss crawler.")
