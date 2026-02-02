"""
HK33 Login and Cookie Management Module
"""

import json
import logging
import os
from pathlib import Path

import requests

from hkjc_scraper.config import config

logger = logging.getLogger(__name__)


def login_hk33_requests() -> dict[str, str]:
    """
    Login to HK33 using requests (no browser needed).

    Steps:
    1. GET login page to establish PHPSESSID cookie
    2. POST login credentials via AJAX endpoint
    3. Save cookies to .hk33_cookies on success

    Returns:
        Dict of cookie name -> value on success, empty dict on failure.
    """
    email = config.HK33_EMAIL
    password = config.HK33_PASSWORD

    if not email or not password:
        logger.error("HK33_EMAIL and HK33_PASSWORD must be set in .env for auto-login")
        return {}

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    })

    try:
        # Step 1: GET login page to establish session cookie
        logger.info("Establishing HK33 session...")
        login_page_url = "https://www.hk33.com/user/login-register"
        resp = session.get(login_page_url, timeout=15)
        resp.raise_for_status()

        # Step 2: POST login via AJAX endpoint
        logger.info("Submitting login credentials...")
        payload = {
            "action": "login",
            "fp[email_or_username]": email,
            "fp[password]": password,
            "fp[is_remember_me]": "1",
        }
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": login_page_url,
            "Origin": "https://www.hk33.com",
        }

        resp = session.post(config.HK33_LOGIN_URL, data=payload, headers=headers, timeout=15)
        resp.raise_for_status()

        # Check response for success
        try:
            result = resp.json()
            if result.get("status") == "error" or result.get("error"):
                logger.error(
                    f"HK33 login returned error: status={result.get('status')}, "
                    f"message={result.get('message', 'unknown')}"
                )
                return {}
        except (ValueError, KeyError):
            # Response might not be JSON; check cookies instead
            pass

        # Step 3: Verify cookies
        cookie_dict = dict(session.cookies)

        if "user_id" in cookie_dict or "PHPSESSID" in cookie_dict:
            logger.info(f"HK33 requests-based login successful ({len(cookie_dict)} cookies)")

            # Step 4: Pass age verification gate
            try:
                session.post(
                    "https://horse.hk33.com/ajaj/landing.ajaj",
                    data={"action": "set_18"},
                    headers={
                        "X-Requested-With": "XMLHttpRequest",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": "https://horse.hk33.com/",
                    },
                    timeout=10,
                )
                cookie_dict = dict(session.cookies)
                if "i_am_18_or_over" in cookie_dict:
                    logger.info("Passed age verification gate")
                else:
                    cookie_dict["i_am_18_or_over"] = "1"
                    logger.info("Set age gate cookie manually")
            except Exception as e:
                logger.warning(f"Age gate POST failed: {e}, setting cookie manually")
                cookie_dict["i_am_18_or_over"] = "1"

            # Step 5: Save cookies with restrictive permissions
            cookie_file = Path(".hk33_cookies")
            with open(cookie_file, "w") as f:
                json.dump(cookie_dict, f, indent=2)
            os.chmod(cookie_file, 0o600)
            logger.info(f"Saved {len(cookie_dict)} cookies to {cookie_file}")

            return cookie_dict
        else:
            logger.warning("HK33 login response received but no session cookies found.")
            logger.debug(f"Cookie keys: {list(cookie_dict.keys())}")
            return {}

    except requests.RequestException as e:
        logger.error(f"HK33 requests-based login failed: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error during HK33 login: {e}")
        return {}


