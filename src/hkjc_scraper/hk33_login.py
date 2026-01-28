"""
HK33 Login and Cookie Management Module
"""

import json
import logging
import time

from hkjc_scraper.config import config

logger = logging.getLogger(__name__)


def perform_hk33_login() -> bool:
    """
    Attempt automatic login to HK33 using Selenium to retrieve fresh cookies.
    Requires Selenium and Chrome driver.

    Returns:
        bool: True if login effective and cookies saved, False otherwise.
    """
    try:
        import pickle

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        logger.error("Selenium not installed. Run: pip install selenium")
        return False

    logger.info("🤖 Attempting automatic login via Selenium...")

    options = Options()
    # Ensure headless mode is off if debugging is needed, but for automation usually it's better to verify visually or use headless
    # The original script kept it visible. We'll keep it visible for now as it helps with debugging/captcha if any.

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)

        logger.info("Navigating to login page...")
        driver.get("https://www.hk33.com/user/login-register")

        # Credentials from config
        email = config.HK33_EMAIL
        pwd = config.HK33_PASSWORD

        # Handle Age Verification
        try:
            time.sleep(2)
            age_btn = driver.find_elements(By.ID, "landing_on_or_over_18_button")
            if age_btn and age_btn[0].is_displayed():
                logger.info("Found age verification popup, clicking...")
                age_btn[0].click()
                time.sleep(1)
            else:
                overlays = driver.find_elements(
                    By.CSS_SELECTOR, "div[class*='overlay'] button, div[class*='modal'] button"
                )
                for btn in overlays:
                    if "18" in btn.text or "年滿" in btn.text:
                        logger.info(f"Clicking potential age verification button: {btn.text}")
                        btn.click()
                        time.sleep(1)
                        break
        except Exception as e:
            logger.warning(f"Error checking age verification: {e}")

        # Login Form
        logger.info("Looking for login form...")
        time.sleep(1)

        try:
            username_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "email_or_username"))
            )
            username_input.clear()
            username_input.send_keys(email)
        except Exception:
            logger.warning("Could not find 'email_or_username', trying fallback selectors...")
            username_input = driver.find_element(By.CSS_SELECTOR, "input[type='text'], input[type='email']")
            username_input.clear()
            username_input.send_keys(email)

        password_input = driver.find_element(By.NAME, "password")
        password_input.clear()
        password_input.send_keys(pwd)

        submit_btn = driver.find_element(By.CLASS_NAME, "submit_button")
        submit_btn.click()

        logger.info("Waiting for login to complete...")
        time.sleep(5)

        # Verify and Save Cookies
        cookies = driver.get_cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}

        if "user_id" in cookie_dict or "PHPSESSID" in cookie_dict:
            logger.info("✅ Login successful!")

            # Save JSON
            with open(".hk33_cookies", "w") as f:
                json.dump(cookie_dict, f, indent=2)

            # Save Pickle
            with open("cookies.pkl", "wb") as f:
                pickle.dump(cookies, f)

            logger.info(f"💾 Saved {len(cookies)} cookies to .hk33_cookies and cookies.pkl")
            return True
        else:
            logger.error("❌ Login might have failed (no user_id cookie found).")
            return False

    except Exception as e:
        logger.error(f"❌ Auto-login failed: {e}")
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
