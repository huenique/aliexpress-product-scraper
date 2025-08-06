import argparse
import csv
import datetime
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from typing import Any, Callable, Dict, Generator, List
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv
from playwright.sync_api import Route, sync_playwright

# Load environment variables from .env file
load_dotenv()

API_URL = "https://www.aliexpress.com/fn/search-pc/index"
RESULTS_DIR = "results"
SESSION_CACHE_FILE = "session_cache.json"
CACHE_EXPIRATION_SECONDS = 30 * 60

# --- Oxylabs U.S. Residential Proxy Configuration from Environment ---
OXYLABS_USERNAME = os.getenv("OXYLABS_USERNAME")
OXYLABS_PASSWORD = os.getenv("OXYLABS_PASSWORD")
OXYLABS_ENDPOINT = os.getenv("OXYLABS_ENDPOINT", "pr.oxylabs.io:7777")

# Proxy validation will be done conditionally when proxy is requested

# --- Base Headers (User-Agent will be updated from browser or cache) ---
BASE_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "bx-v": "2.5.28",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://www.aliexpress.com",
    "priority": "u=1, i",
    "sec-ch-ua": "",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 ...",
}


def default_logger(message: str) -> None:
    print(message)


def validate_proxy_credentials(proxy_provider: str) -> None:
    """Validate proxy credentials based on the provider."""
    if proxy_provider == "oxylabs":
        if not OXYLABS_USERNAME or not OXYLABS_PASSWORD:
            raise ValueError(
                "Missing Oxylabs credentials! Please ensure OXYLABS_USERNAME and OXYLABS_PASSWORD "
                "are set in your .env file or environment variables."
            )
    elif proxy_provider == "massive":
        # Add validation for massive proxy credentials when implemented
        raise NotImplementedError("Massive proxy provider is not yet implemented")
    # No validation needed if no proxy provider is specified


def initialize_session_data(
    keyword: str,
    proxy_provider: str = "",
    log_callback: Callable[[str], None] = default_logger,
) -> tuple[dict[str, Any], str]:
    """
    Checks for cached session data first. If valid cache exists, uses it.
    Otherwise, launches a browser to extract session data. If a proxy provider
    is specified, configures proxy accordingly.
    """
    log_callback(f"Initializing session for product: '{keyword}'")

    # Validate proxy credentials if proxy provider is specified
    if proxy_provider:
        validate_proxy_credentials(proxy_provider)

    cached_data = None

    if os.path.exists(SESSION_CACHE_FILE):
        try:
            with open(SESSION_CACHE_FILE, "r") as f:
                cached_data = json.load(f)
            saved_timestamp = cached_data.get("timestamp", 0)
            current_timestamp = time.time()
            cache_age = current_timestamp - saved_timestamp

            if cache_age < CACHE_EXPIRATION_SECONDS:
                log_callback(
                    f"Using cached session data (Age: {datetime.timedelta(seconds=int(cache_age))})."
                )
                return cached_data["cookies"], cached_data["user_agent"]
            else:
                log_callback(
                    f"Cached session data expired (Age: {datetime.timedelta(seconds=int(cache_age))})."
                )

        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            log_callback(
                f"Error reading cache file or cache invalid ({e}). Will fetch fresh session."
            )
            cached_data = None
    else:
        pass

    # --- Cache Miss or Expired: Launch Browser ---
    if proxy_provider:
        log_callback(
            f"Fetching fresh session data using headless browser with {proxy_provider} proxy..."
        )
    else:
        log_callback("Fetching fresh session data using headless browser (no proxy)...")

    playwright = None
    browser = None
    context = None
    page = None

    try:
        playwright = sync_playwright().start()

        # Launch browser with optimization settings
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-images",
                "--disable-css",
                "--disable-plugins",
                "--disable-extensions",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-blink-features=AutomationControlled",
                "--excludeSwitches=enable-automation",
            ],
        )

        user_agent_string = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

        # Configure context with or without proxy
        context_options: dict[str, Any] = {
            "user_agent": user_agent_string,
            "java_script_enabled": False,  # Disable JS for faster loading
            "ignore_https_errors": True,
        }

        # Configure proxy based on provider
        if proxy_provider == "oxylabs":
            context_options["proxy"] = {
                "server": f"http://{OXYLABS_ENDPOINT}",
                "username": OXYLABS_USERNAME,
                "password": OXYLABS_PASSWORD,
            }
            log_callback(f"Configured Oxylabs proxy: {OXYLABS_ENDPOINT}")
        elif proxy_provider == "massive":
            # Add massive proxy configuration when implemented
            raise NotImplementedError("Massive proxy provider is not yet implemented")
        else:
            log_callback("No proxy configured - using direct connection")

        context = browser.new_context(**context_options)

        # Block CSS and images for faster loading
        def handle_route(route: Route) -> None:
            if route.request.resource_type in ["stylesheet", "image", "font", "media"]:
                route.abort()
            else:
                route.continue_()

        context.route("**/*", handle_route)

        page = context.new_page()

        search_url = (
            f"https://www.aliexpress.com/w/wholesale-{quote_plus(keyword)}.html"
        )
        log_callback(
            f"Visiting initial search page (optimized load, images and CSS blocked): {search_url}"
        )

        # Navigate to page with timeout
        page.goto(search_url, timeout=30000, wait_until="domcontentloaded")

        log_callback("Extracting fresh cookies and user agent...")

        # Get cookies from browser context
        fresh_cookies_list = context.cookies()
        fresh_cookies = {
            cookie["name"]: cookie["value"]
            for cookie in fresh_cookies_list
            if "name" in cookie and "value" in cookie
        }

        fresh_user_agent = user_agent_string

        log_callback(f"Using User-Agent: {fresh_user_agent}")
        log_callback(f"Extracted {len(fresh_cookies)} cookies.")

        cache_content: dict[str, Any] = {
            "timestamp": time.time(),
            "cookies": fresh_cookies,
            "user_agent": fresh_user_agent,
        }
        try:
            with open(SESSION_CACHE_FILE, "w") as f:
                json.dump(cache_content, f, indent=4)
            log_callback("Session data cached successfully.")
        except IOError as e:
            log_callback(f"Error saving session cache: {e}")

        return fresh_cookies, fresh_user_agent

    except Exception as e:
        log_callback(f"An error occurred during browser initialization: {e}")
        raise
    finally:
        # --- Ensure browser is closed ---
        if page:
            page.close()
        if context:
            context.close()
        if browser:
            browser.close()
        if playwright:
            playwright.stop()


def scrape_aliexpress_data(
    keyword: str,
    max_pages: int,
    cookies: dict[str, Any],
    user_agent: str,
    proxy_provider: str = "",
    apply_discount_filter: bool = False,
    apply_free_shipping_filter: bool = False,
    min_price: float | None = None,
    max_price: float | None = None,
    delay: float = 1.0,
    log_callback: Callable[[str], None] = default_logger,
) -> tuple[list[dict[str, Any]], Any]:
    """
    Uses requests with extracted session data to scrape product results
    for the given keyword via direct API calls, optionally applying filters.
    Proxy usage is conditional based on proxy_provider parameter.
    Returns (raw_products, session) tuple.
    """
    if proxy_provider:
        log_callback(
            f"\nCreating requests session with {proxy_provider} proxy for API calls for product: '{keyword}'"
        )
    else:
        log_callback(
            f"\nCreating requests session (no proxy) for API calls for product: '{keyword}'"
        )

    # Create requests session
    session = requests.Session()

    # Configure proxy for requests session based on provider
    if proxy_provider == "oxylabs":
        proxy_auth = f"{OXYLABS_USERNAME}:{OXYLABS_PASSWORD}"
        proxy_url = f"http://{proxy_auth}@{OXYLABS_ENDPOINT}"
        session.proxies = {"http": proxy_url, "https": proxy_url}
    elif proxy_provider == "massive":
        # Add massive proxy configuration when implemented
        raise NotImplementedError("Massive proxy provider is not yet implemented")
    # No proxy configuration if no provider specified

    # Set cookies and headers
    session.cookies.update(cookies)  # type: ignore

    current_base_headers = BASE_HEADERS.copy()
    current_base_headers["user-agent"] = user_agent

    all_products_raw: list[dict[str, Any]] = []

    active_switches: list[str] = []
    if apply_discount_filter:
        log_callback("Applying 'Big Sale' discount filter...")
        active_switches.append("filterCode:bigsale")
    if apply_free_shipping_filter:
        log_callback("Applying 'Free Shipping' filter...")
        active_switches.append("filterCode:freeshipping")

    price_range_str = None
    min_price_int = int(min_price) if min_price is not None and min_price >= 0 else None
    max_price_int = int(max_price) if max_price is not None and max_price >= 0 else None

    if min_price_int is not None and max_price_int is not None:
        if min_price_int <= max_price_int:
            price_range_str = f"{min_price_int}-{max_price_int}"
            log_callback(f"Applying Price Filter: {price_range_str}")
        else:
            log_callback(
                "Warning: Min price is greater than max price. Ignoring price filter."
            )
    elif min_price_int is not None:
        price_range_str = f"{min_price_int}-"
        log_callback(f"Applying Price Filter: Min {min_price_int}")
    elif max_price_int is not None:
        price_range_str = f"-{max_price_int}"
        log_callback(f"Applying Price Filter: Max {max_price_int}")

    for current_page_num in range(1, max_pages + 1):
        log_callback(
            f"Attempting to fetch page {current_page_num} for product: '{keyword}' via API..."
        )

        request_headers = current_base_headers.copy()
        referer_keyword_part = quote_plus(keyword)
        referer_url = f"https://www.aliexpress.com/w/wholesale-{referer_keyword_part}.html?page={current_page_num}&g=y&SearchText={referer_keyword_part}"
        if active_switches:
            switches_value = ",".join(active_switches)
            referer_url += f"&selectedSwitches={quote_plus(switches_value)}"
        if price_range_str:
            referer_url += f"&pr={price_range_str}"
        request_headers["Referer"] = referer_url

        payload: dict[str, Any] = {
            "pageVersion": "7ece9c0cc9cf2052db74f0d1b26b7033",
            "target": "root",
            "data": {
                "page": current_page_num,
                "g": "y",
                "SearchText": keyword,
                "origin": "y",
            },
            "eventName": "onChange",
            "dependency": [],
        }

        if active_switches:
            payload["data"]["selectedSwitches"] = ",".join(active_switches)
        if price_range_str:
            payload["data"]["pr"] = price_range_str

        response: requests.Response | None = None

        # Make the POST request
        try:
            response = session.post(
                API_URL, json=payload, headers=request_headers, timeout=30
            )

            if response.status_code != 200:
                log_callback(
                    f"Failed to fetch page {current_page_num}. Status code: {response.status_code}"
                )
                log_callback(f"Response text sample: {response.text[:200]}")
                break

            json_data: dict[str, Any] | None = response.json()

            # save the json response to debug/ dir (for debugging only)
            # with open(f"debug/api_response_page_{current_page_num}.json", "w") as f:
            #     json.dump(json_data, f, indent=4)

            if not isinstance(json_data, dict):
                log_callback(
                    f"Unexpected response format for page {current_page_num}. Expected JSON dict."
                )
                log_callback(f"Response text sample: {response.text[:200]}")
                break

            # Check for validation/captcha errors
            if json_data.get("ret") and "FAIL_SYS_USER_VALIDATE" in json_data.get(
                "ret", []
            ):
                log_callback(
                    "🚫 AliExpress validation error detected - API access blocked"
                )
                log_callback(
                    "💡 Recommendation: Use 'enhanced_scraper.py' which includes captcha solving capabilities"
                )
                log_callback(
                    "   Example: uv run python enhanced_scraper.py 'mechanical keyboard' --max-pages 1"
                )
                break

            items_list = (
                json_data.get("data", {})
                .get("result", {})
                .get("mods", {})
                .get("itemList", {})
                .get("content", [])
            )

            if not items_list:
                log_callback(
                    f"No items found using path 'data.result.mods.itemList.content' on page {current_page_num}."
                )
                if current_page_num == max_pages:
                    log_callback(
                        f"Reached requested page limit ({max_pages}) with no items found on this last page."
                    )
                    break
                elif current_page_num > 1:
                    log_callback(
                        f"Stopping search: No items found on page {current_page_num} (before requested limit of {max_pages} pages)."
                    )
                    break
                else:
                    log_callback(
                        "Continuing to next page (in case only page 1 structure differs)."
                    )
            else:
                log_callback(
                    f"Found {len(items_list)} items on page {current_page_num}."
                )
                all_products_raw.extend(items_list)

        except requests.exceptions.RequestException as e:
            log_callback(f"Request failed for page {current_page_num}: {e}")
            break
        except json.JSONDecodeError:
            log_callback(f"Failed to decode JSON response for page {current_page_num}.")
            if response:
                log_callback(f"Response text sample: {response.text[:200]}")
            else:
                log_callback(
                    "No response object available. This may indicate a connection error."
                )
            break
        except Exception as e:
            log_callback(f"An error occurred processing page {current_page_num}: {e}")
            break

        # Delay between requests
        time.sleep(delay)

    log_callback(
        f"\nAPI Scraping finished for product: '{keyword}'. Total raw products collected: {len(all_products_raw)}"
    )
    return all_products_raw, session


def fetch_store_info_batch(
    product_ids: list[str],
    session: Any,
    proxy_provider: str = "",
    log_callback: Callable[[str], None] = default_logger,
    max_workers: int = 3,
) -> dict[str, dict[str, str | None]]:
    """
    Fetches store information for multiple products.
    Now attempts to use captcha solver for the first few products when available.
    """
    if not product_ids:
        return {}

    log_callback(
        f"Fetching store info for {len(product_ids)} products with enhanced captcha handling..."
    )

    # Try captcha solver for first few products, then fall back to basic method
    store_results: dict[str, dict[str, str | None]] = {}

    try:
        # Try captcha solver for first 3 products
        captcha_products = product_ids[:3]
        log_callback(
            f"🛡️ Attempting captcha-enhanced extraction for {len(captcha_products)} products..."
        )

        for product_id in captcha_products:
            try:
                # Use the basic approach but with enhanced error handling
                store_info = fetch_single_store_with_captcha_fallback(
                    product_id, proxy_provider, log_callback
                )
                store_results[product_id] = store_info

                if store_info.get("store_name"):
                    log_callback(
                        f"✅ Store found for {product_id}: {store_info['store_name']}"
                    )
                else:
                    log_callback(f"⚠️ No store info for {product_id}")

            except Exception as e:
                log_callback(f"❌ Error processing {product_id}: {str(e)}")
                store_results[product_id] = {
                    "store_name": None,
                    "store_id": None,
                    "store_url": None,
                }

        log_callback(
            f"Captcha-enhanced processing complete. Using basic method for remaining products..."
        )

    except ImportError:
        log_callback(
            "⚠️ Captcha solver module not available, using basic method for all products"
        )
        captcha_products = []
    except Exception as e:
        log_callback(f"❌ Captcha solver error: {str(e)}, falling back to basic method")
        captcha_products = []

    # Process remaining products with basic method
    remaining_products = [pid for pid in product_ids if pid not in store_results]
    if remaining_products:
        basic_results = fetch_store_info_batch_basic(
            remaining_products, session, proxy_provider, log_callback, max_workers
        )
        store_results.update(basic_results)

    successful_count = sum(
        1 for result in store_results.values() if result.get("store_name")
    )
    log_callback(
        f"Store info batch fetch complete: {successful_count}/{len(product_ids)} successful"
    )

    return store_results


def fetch_single_store_with_captcha_fallback(
    product_id: str, proxy_provider: str, log_callback: Callable[[str], None]
) -> dict[str, str | None]:
    """
    Attempt to fetch store info for a single product using requests with enhanced patterns
    """
    try:
        import re

        import requests

        product_url = f"https://www.aliexpress.com/item/{product_id}.html"

        # Enhanced headers to avoid detection
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }

        # Create session
        session = requests.Session()
        session.headers.update(headers)

        # Configure proxy if available
        if proxy_provider == "oxylabs" and OXYLABS_USERNAME and OXYLABS_PASSWORD:
            proxy_auth = f"{OXYLABS_USERNAME}:{OXYLABS_PASSWORD}"
            proxy_url = f"http://{proxy_auth}@{OXYLABS_ENDPOINT}"
            session.proxies = {"http": proxy_url, "https": proxy_url}

        # Make request with timeout
        response = session.get(product_url, timeout=15)

        if response.status_code == 200:
            html = response.text

            # Check for captcha/bot detection
            if any(
                indicator in html.lower()
                for indicator in ["captcha", "verify", "security check"]
            ):
                log_callback(
                    f"🚨 Captcha detected for {product_id}, extraction may be limited"
                )

            # Enhanced store extraction patterns
            store_name = None
            store_id = None
            store_url = None

            # Try multiple patterns for store name
            store_name_patterns = [
                r'"storeName"\s*:\s*"([^"]+)"',
                r'"sellerAdminSeq"\s*:\s*"([^"]+)"',
                r'"shopName"\s*:\s*"([^"]+)"',
                r'data-spm-anchor-id="[^"]*store[^"]*"[^>]*>([^<]+)',
                r"store.*?name[^>]*>([^<]+)",
                r"seller.*?name[^>]*>([^<]+)",
            ]

            for pattern in store_name_patterns:
                match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
                if match:
                    potential_name = match.group(1).strip()
                    if (
                        potential_name
                        and len(potential_name) > 2
                        and not potential_name.isdigit()
                    ):
                        store_name = potential_name
                        break

            # Try to find store ID and URL
            store_link_patterns = [
                r'href="([^"]*\/store\/(\d+)[^"]*)"',
                r'"storeUrl"\s*:\s*"([^"]*\/store\/(\d+)[^"]*)"',
            ]

            for pattern in store_link_patterns:
                match = re.search(pattern, html)
                if match:
                    store_url = match.group(1)
                    if store_url.startswith("/"):
                        store_url = f"https://www.aliexpress.com{store_url}"
                    store_id = match.group(2)
                    break

            return {
                "store_name": store_name,
                "store_id": store_id,
                "store_url": store_url,
            }
        else:
            log_callback(f"HTTP {response.status_code} for {product_id}")
            return {"store_name": None, "store_id": None, "store_url": None}

    except Exception as e:
        log_callback(f"Error fetching store for {product_id}: {str(e)}")
        return {"store_name": None, "store_id": None, "store_url": None}


def fetch_store_info_batch_basic(
    product_ids: list[str],
    session: Any,
    proxy_provider: str = "",
    log_callback: Callable[[str], None] = default_logger,
    max_workers: int = 3,
) -> dict[str, dict[str, str | None]]:
    """
    Fetches store information for multiple products using a shared browser pool.
    Much faster than fetching one product at a time.
    Returns a dict mapping product_id -> store_info.

    Note: Store info fetching uses Playwright with proxy authentication support.
    """
    if not product_ids:
        return {}

    log_callback(
        f"Fetching store info for {len(product_ids)} products using {max_workers} workers..."
    )

    # Shared browser pool to reuse browser instances
    store_results: dict[str, dict[str, str | None]] = {}

    def create_browser() -> dict[str, Any]:
        """Create a configured Playwright browser instance for store info extraction"""

        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-images",
                "--disable-plugins",
                "--disable-extensions",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        # Configure proxy settings based on provider
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"

        try:
            if proxy_provider == "oxylabs":
                log_callback(
                    f"Configured proxy: {OXYLABS_ENDPOINT} with user: {OXYLABS_USERNAME and OXYLABS_USERNAME[:10]}..."
                )

                context = browser.new_context(
                    user_agent=user_agent,
                    java_script_enabled=True,
                    proxy={
                        "server": f"http://{OXYLABS_ENDPOINT}",
                        "username": OXYLABS_USERNAME,
                        "password": OXYLABS_PASSWORD,
                    },
                )
            elif proxy_provider == "massive":
                # Add massive proxy configuration when implemented
                raise NotImplementedError(
                    "Massive proxy provider is not yet implemented"
                )
            else:
                log_callback("No proxy configured for store info fetching")
                context = browser.new_context(
                    user_agent=user_agent,
                    java_script_enabled=True,
                )
        except Exception as e:
            log_callback(
                f"WARNING: Failed to configure proxy, falling back to no proxy: {e}"
            )

            context = browser.new_context(
                user_agent=user_agent,
                java_script_enabled=True,
            )

        # Return both playwright instance and page for cleanup
        page = context.new_page()
        return {
            "playwright": playwright,
            "browser": browser,
            "context": context,
            "page": page,
        }

    def fetch_single_store_info(
        product_id: str, browser_obj: Any
    ) -> dict[str, str | None] | None:
        """Fetch store info for a single product using Playwright browser"""
        try:
            product_url = f"https://www.aliexpress.com/item/{product_id}.html"
            page = browser_obj["page"]

            if proxy_provider:
                log_callback(
                    f"Navigating to {product_url} with {proxy_provider} proxy..."
                )
            else:
                log_callback(f"Navigating to {product_url} (no proxy)...")

            # Navigate to the page with increased timeout
            page.goto(product_url, timeout=30000, wait_until="domcontentloaded")

            # Wait a moment for dynamic content to load
            page.wait_for_timeout(3000)

            # Get HTML content for analysis
            html_content = page.content()

            # Write the html_content to debug dir for debug
            with open(
                f"debug/playwright_debug_{product_id}.html", "w", encoding="utf-8"
            ) as f:
                f.write(html_content)

            # Debug: Check for bot challenge indicators
            if (
                "captcha" in html_content.lower()
                or "security" in html_content.lower()
                or "verify" in html_content.lower()
            ):
                log_callback("WARNING: Possible bot challenge detected in page content")

            # Check if we're on a "not found" or error page
            if (
                "not-found" in html_content
                or "unavailable in your location" in html_content
                or "Sorry, this item" in html_content
                or "item not found" in html_content.lower()
            ):
                log_callback(
                    f"ERROR: Product {product_id} shows item unavailable or not found"
                )
                log_callback(
                    "This could be due to: invalid URL, product no longer available, geographic restrictions, or need login"
                )

                return {
                    "store_name": "ERROR: Product unavailable",
                    "store_id": "ERROR: Product unavailable",
                    "store_url": "ERROR: Product unavailable",
                }

            # Look for store information in the HTML using regex patterns
            store_name = None
            store_id = None
            store_url = None

            try:
                import re

                # Pattern 1: Look for store name in various HTML structures
                store_patterns = [
                    r'<span class="store-detail--storeName[^"]*">([^<]+)</span>',  # Primary AliExpress pattern
                    r'data-pl="store-name">([^<]+)</a>',  # Secondary pattern
                    r"store-info--name[^>]*>[^>]*>([^<]+)</a>",  # Store info section
                    r'store["\']?\s*:\s*["\']([^"\']+)["\']',  # JSON-like patterns
                    r'storeName["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'seller["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'shop["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'sellerName["\']?\s*:\s*["\']([^"\']+)["\']',
                ]

                for pattern in store_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                    if match:
                        store_name = match.group(1).strip()
                        break

                # Pattern 2: Look for store ID in various locations
                store_id_patterns = [
                    r"storeId=(\d+)",  # URL parameter pattern
                    r"store/(\d+)",  # Store URL path pattern
                    r'storeId["\']?\s*:\s*["\']?(\d+)["\']?',  # JSON patterns
                    r'sellerId["\']?\s*:\s*["\']?(\d+)["\']?',
                    r'shopId["\']?\s*:\s*["\']?(\d+)["\']?',
                ]

                for pattern in store_id_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        store_id = match.group(1)
                        break

                # Pattern 3: Look for store URL in various locations
                store_url_patterns = [
                    r'href="[^"]*aliexpress\.com/store/(\d+)"',  # Direct href pattern
                    r'//[^"]*\.aliexpress\.com/store/(\d+)',  # Domain pattern
                    r'storeUrl["\']?\s*:\s*["\']([^"\']+)["\']',  # JSON pattern
                ]

                for pattern in store_url_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        if match.group(1).isdigit():
                            store_url = (
                                f"https://www.aliexpress.com/store/{match.group(1)}"
                            )
                        else:
                            store_url = match.group(1)
                        break

            except Exception as regex_error:
                log_callback(
                    f"Error in regex extraction for {product_id}: {regex_error}"
                )

            return {
                "store_name": store_name,
                "store_id": store_id,
                "store_url": store_url,
            }

        except Exception as e:
            log_callback(f"Error fetching store info for {product_id}: {e}")
            return None

    def worker_function(
        worker_id: int, product_batch: list[str]
    ) -> dict[str, dict[str, str | None]]:
        """Worker function that processes a batch of products"""
        browser: Any | None = None
        worker_results: dict[str, dict[str, str | None]] = {}

        try:
            browser = create_browser()
            log_callback(
                f"Worker {worker_id}: Processing {len(product_batch)} products"
            )

            for i, product_id in enumerate(product_batch):
                try:
                    store_info = fetch_single_store_info(product_id, browser)
                    worker_results[product_id] = store_info or {
                        "store_name": None,
                        "store_id": None,
                        "store_url": None,
                    }

                    if store_info:
                        log_callback(
                            f"Worker {worker_id}: Found store for {product_id}: {store_info.get('store_name', 'N/A')}"
                        )

                    # Small delay between requests to avoid overwhelming server
                    if i < len(product_batch) - 1:  # Don't delay after last item
                        time.sleep(0.2)

                except Exception as e:
                    log_callback(
                        f"Worker {worker_id}: Error processing {product_id}: {e}"
                    )
                    worker_results[product_id] = {
                        "store_name": None,
                        "store_id": None,
                        "store_url": None,
                    }

        except Exception as e:
            log_callback(f"Worker {worker_id}: Failed to create browser: {e}")
        finally:
            if browser:
                try:
                    # Properly cleanup Playwright resources
                    browser["context"].close()
                    browser["browser"].close()
                    browser["playwright"].stop()
                except:
                    pass

        return worker_results

    # Split products into batches for parallel processing
    batch_size = max(1, len(product_ids) // max_workers)
    product_batches = [
        product_ids[i : i + batch_size] for i in range(0, len(product_ids), batch_size)
    ]

    # Process batches in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: list[Any] = []
        for i, batch in enumerate(product_batches):
            future = executor.submit(worker_function, i + 1, batch)
            futures.append(future)

        # Collect results
        for future in as_completed(futures):
            try:
                worker_results = future.result()
                store_results.update(worker_results)
            except Exception as e:
                log_callback(f"Error in worker thread: {e}")

    successful_fetches = sum(
        1
        for result in store_results.values()
        if any(value is not None for value in result.values())
    )

    log_callback(
        f"Store info batch fetch complete: {successful_fetches}/{len(product_ids)} successful"
    )

    return store_results


def fetch_store_info_from_product_page(
    product_id: str,
    session: Any,
    proxy_provider: str = "",
    log_callback: Callable[[str], None] = default_logger,
) -> dict[str, str | None] | None:
    """
    Legacy function for backward compatibility.
    For better performance, use fetch_store_info_batch() instead.
    """
    if not product_id:
        return None

    # Use the batch function for single product
    results = fetch_store_info_batch(
        [product_id], session, proxy_provider, log_callback, max_workers=1
    )
    return results.get(product_id)


def extract_product_details(
    raw_products: list[dict[str, Any]],
    selected_fields: list[str],
    brand: str,
    proxy_provider: str = "",
    session: Any | None = None,
    fetch_store_info: bool = False,
    log_callback: Callable[[str], None] = default_logger,
) -> list[dict[str, Any]]:
    """
    Extracts and formats desired fields from the raw product data,
    based on the user's selection. Now uses batch processing for store info.
    """
    extracted_data: list[dict[str, Any]] = []
    if not raw_products or not selected_fields:
        log_callback("No raw products or selected fields for extraction.")
        return extracted_data

    log_callback(f"Extracting selected fields: {selected_fields}")

    # Collect all product IDs that need store info
    store_info_results: dict[str, dict[str, str | None]] = {}
    if fetch_store_info and session:
        store_fields_requested = any(
            field in selected_fields
            for field in ["Store Name", "Store ID", "Store URL"]
        )
        if store_fields_requested:
            product_ids: list[str] = [
                str(product.get("productId"))
                for product in raw_products
                if product.get("productId")
            ]
            if product_ids:
                log_callback(
                    f"Batch fetching store info for {len(product_ids)} products..."
                )
                store_info_results = fetch_store_info_batch(
                    product_ids, session, proxy_provider, log_callback, max_workers=3
                )

    for product in raw_products:
        # --- Extract ALL possible fields first ---
        product_id = product.get("productId")
        title = product.get("title", {}).get("displayTitle")
        image_url = product.get("image", {}).get("imgUrl")
        if image_url and not image_url.startswith("http"):
            image_url = "https:" + image_url
        prices_info = product.get("prices", {})
        sale_price_info = prices_info.get("salePrice", {})
        original_price_info = prices_info.get("originalPrice", {})
        sale_price = sale_price_info.get("formattedPrice")
        original_price = original_price_info.get("formattedPrice")
        currency = sale_price_info.get("currencyCode")
        discount = sale_price_info.get("discount")

        # Get store info from batch results
        store_name = None
        store_id = None
        store_url = None

        if product_id in store_info_results:
            store_info = store_info_results[product_id]
            if store_info:
                store_name = store_info.get("store_name")
                store_id = store_info.get("store_id")
                store_url = store_info.get("store_url")

        trade_info = product.get("trade", {})
        orders_count = trade_info.get("realTradeCount")
        rating = product.get("evaluation", {}).get("starRating")
        product_url = (
            f"https://www.aliexpress.com/item/{product_id}.html" if product_id else None
        )

        # --- Store all potentially extractable data in a temporary dict ---
        full_details: dict[str, Any] = {
            "Product ID": product_id,
            "Title": title,
            "Sale Price": sale_price,
            "Original Price": original_price,
            "Discount (%)": discount,
            "Currency": currency,
            "Rating": rating,
            "Orders Count": orders_count,
            "Store Name": store_name,
            "Store ID": store_id,
            "Store URL": store_url,
            "Product URL": product_url,
            "Image URL": image_url,
            "Brand": brand,
        }

        filtered_item: dict[str, Any] = {
            field: full_details.get(field) for field in selected_fields
        }

        extracted_data.append(filtered_item)

    log_callback(
        f"Extracted data for {len(extracted_data)} products with selected fields."
    )
    return extracted_data


def save_results(
    keyword: str,
    data: list[dict[str, Any]],
    selected_fields: list[str],
    log_callback: Callable[[str], None] = default_logger,
) -> tuple[str | None, str | None]:
    """
    Saves the extracted data to JSON and CSV files, named using the keyword.
    Uses selected_fields for CSV headers.
    """
    if not data:
        log_callback("No data to save.")
        return None, None
    if not selected_fields:
        log_callback("No fields selected for saving.")
        return None, None

    os.makedirs(RESULTS_DIR, exist_ok=True)
    keyword_safe_name = "".join(c if c.isalnum() else "_" for c in keyword)
    json_filename = os.path.join(
        RESULTS_DIR, f"aliexpress_{keyword_safe_name}_extracted.json"
    )
    csv_filename = os.path.join(
        RESULTS_DIR, f"aliexpress_{keyword_safe_name}_extracted.csv"
    )

    try:
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        fieldnames = selected_fields
        with open(csv_filename, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)

        log_callback(f"JSON and CSV results saved to: {json_filename}, {csv_filename}")

        return json_filename, csv_filename

    except Exception as e:
        log_callback(f"Error saving results to file: {e}")
        return None, None


class StreamLogger:
    def __init__(self) -> None:
        self.message_queue: Queue[str] = Queue()
        self.active: bool = True

    def log(self, message: str) -> None:
        if self.active:
            self.message_queue.put(message)

    def stream_messages(self) -> Generator[str, None, None]:
        while self.active or not self.message_queue.empty():
            try:
                message = self.message_queue.get(timeout=0.1)
                yield f"data: {message}\n\n"
                self.message_queue.task_done()
            except:
                continue
        yield "data: PROCESS_COMPLETE\n\n"

    def stop(self) -> None:
        self.active = False


def run_scrape_job(
    keyword: str,
    pages: int,
    brand: str,
    apply_discount: bool,
    free_shipping: bool,
    min_price: float | None,
    max_price: float | None,
    selected_fields: list[str],
    proxy_provider: str = "",
    delay: float = 1.0,
) -> Generator[str, None, None]:
    """
    Generator function that orchestrates the scraping process with real-time logging.
    """
    logger = StreamLogger()

    def scrape_task() -> None:
        try:
            cookies, user_agent = initialize_session_data(
                keyword, proxy_provider, log_callback=logger.log
            )

            logger.log(f"Starting scraping for {pages} pages...")
            raw_products, session = scrape_aliexpress_data(
                keyword=keyword,
                max_pages=pages,
                cookies=cookies,
                user_agent=user_agent,
                proxy_provider=proxy_provider,
                apply_discount_filter=apply_discount,
                apply_free_shipping_filter=free_shipping,
                min_price=min_price,
                max_price=max_price,
                delay=delay,
                log_callback=logger.log,
            )

            # Check if store information is requested
            store_fields_requested = any(
                field in selected_fields
                for field in ["Store Name", "Store ID", "Store URL"]
            )
            if store_fields_requested:
                logger.log(
                    "Store information requested - fetching store details from product pages..."
                )

            logger.log("Extracting product details...")
            extracted_data = extract_product_details(
                raw_products,
                selected_fields,
                brand,
                proxy_provider,
                session=session,
                fetch_store_info=store_fields_requested,
                log_callback=logger.log,
            )

            logger.log("Saving results...")
            save_results(
                keyword, extracted_data, selected_fields, log_callback=logger.log
            )

        except Exception as e:
            logger.log(f"ERROR: {str(e)}")
        finally:
            logger.stop()

    threading.Thread(target=scrape_task, daemon=True).start()

    yield from logger.stream_messages()


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="AliExpress Product Scraper - Extract product data from AliExpress search results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --keyword "lego batman" --brand "LEGO" --pages 3
  %(prog)s --keyword "gaming mouse" --brand "Razer" --pages 5 --discount --free-shipping --proxy-provider oxylabs
  %(prog)s --keyword "bluetooth headphones" --brand "Sony" --pages 2 --min-price 20 --max-price 100
        """,
    )

    # Required arguments
    parser.add_argument(
        "--keyword",
        "-k",
        required=True,
        help="Product keyword to search for on AliExpress",
    )

    parser.add_argument(
        "--brand",
        "-b",
        required=True,
        help="Brand name to associate with the scraped products",
    )

    # Optional arguments
    parser.add_argument(
        "--pages",
        "-p",
        type=int,
        default=1,
        choices=range(1, 61),
        metavar="[1-60]",
        help="Number of pages to scrape (default: 1, max: 60)",
    )

    parser.add_argument(
        "--discount", "-d", action="store_true", help="Apply 'Big Sale' discount filter"
    )

    parser.add_argument(
        "--free-shipping",
        "-f",
        action="store_true",
        help="Apply 'Free Shipping' filter",
    )

    parser.add_argument("--min-price", type=float, help="Minimum price filter")

    parser.add_argument("--max-price", type=float, help="Maximum price filter")

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)",
    )

    parser.add_argument(
        "--fields",
        nargs="+",
        choices=[
            "Product ID",
            "Title",
            "Sale Price",
            "Original Price",
            "Discount (%)",
            "Currency",
            "Rating",
            "Orders Count",
            "Store Name",
            "Store ID",
            "Store URL",
            "Product URL",
            "Image URL",
            "Brand",
        ],
        default=[
            "Product ID",
            "Title",
            "Sale Price",
            "Original Price",
            "Discount (%)",
            "Currency",
            "Rating",
            "Orders Count",
            "Store Name",
            "Store ID",
            "Store URL",
            "Product URL",
            "Image URL",
            "Brand",
        ],
        help="Fields to extract (default: all fields)",
    )

    parser.add_argument(
        "--proxy-provider",
        choices=["oxylabs", "massive"],
        default="",
        help="Proxy provider to use (default: None)",
    )

    parser.add_argument(
        "--enable-store-retry",
        action="store_true",
        help="Automatically retry missing store information after scraping",
    )

    parser.add_argument(
        "--store-retry-batch-size",
        type=int,
        default=5,
        help="Batch size for store retry operations (default: 5)",
    )

    parser.add_argument(
        "--store-retry-delay",
        type=float,
        default=2.0,
        help="Delay between store retry batches in seconds (default: 2.0)",
    )

    return parser


async def auto_retry_store_info(
    json_file: str,
    products: list[dict[str, Any]],
    proxy_provider: str = "",
    batch_size: int = 5,
    delay: float = 2.0,
) -> None:
    """
    Automatically retry missing store information for the regular scraper.

    Args:
        json_file: Path to the saved JSON file
        products: List of scraped products
        proxy_provider: Proxy provider to use
        batch_size: Batch size for processing
        delay: Delay between batches
    """
    try:
        # Import the store retry functionality
        from store_integration import get_store_integration

        # Find products with missing store info
        missing_products: List[Dict[str, Any]] = []
        for product in products:
            store_name = product.get("Store Name")
            store_id = product.get("Store ID")
            store_url = product.get("Store URL")
            product_url = product.get("Product URL")

            # Check if store information is missing
            needs_retry = False
            if not store_name or store_name in [None, "null", "", "N/A"]:
                needs_retry = True
            if not store_id or store_id in [None, "null", "", "N/A"]:
                needs_retry = True
            if not store_url or store_url in [None, "null", "", "N/A"]:
                needs_retry = True

            if needs_retry and product_url:
                missing_products.append(product)

        if not missing_products:
            return

        # Extract URLs for retry with explicit typing
        urls_to_retry: List[str] = [
            p["Product URL"] for p in missing_products if p.get("Product URL")
        ]

        if not urls_to_retry:
            return

        # Get store integration and retry
        integration = get_store_integration(proxy_provider=proxy_provider)

        # Process in batches
        all_retry_results: Dict[str, Any] = {}

        for i in range(0, len(urls_to_retry), batch_size):
            batch_urls: List[str] = urls_to_retry[i : i + batch_size]

            try:
                batch_results = await integration.fetch_store_info_enhanced(batch_urls)
                all_retry_results.update(batch_results)

            except Exception:
                pass  # Silent failure

            # Delay between batches
            if i + batch_size < len(urls_to_retry) and delay > 0:
                import asyncio

                await asyncio.sleep(delay)

        # Update products with retry results
        updated_products: List[Dict[str, Any]] = []
        successful_updates = 0

        for product in products:
            product_url = product.get("Product URL")

            if product_url in all_retry_results:
                store_info: Dict[str, Any] = all_retry_results[product_url]

                updated_product = product.copy()
                updated = False

                if store_info.get("store_name"):
                    updated_product["Store Name"] = store_info["store_name"]
                    updated = True

                if store_info.get("store_id"):
                    updated_product["Store ID"] = store_info["store_id"]
                    updated = True

                if store_info.get("store_url"):
                    updated_product["Store URL"] = store_info["store_url"]
                    updated = True

                if updated:
                    successful_updates += 1

                updated_products.append(updated_product)
            else:
                updated_products.append(product)

        # Save updated results if there were successful updates
        if successful_updates > 0:
            # Update the JSON file with new data
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(updated_products, f, indent=2, ensure_ascii=False)

            # Also update CSV if we have it
            csv_file = json_file.replace(".json", ".csv")
            if csv_file != json_file:  # Make sure we actually have a CSV path
                try:
                    import pandas as pd

                    df = pd.DataFrame(updated_products)
                    df.to_csv(csv_file, index=False)
                except ImportError:
                    pass  # Silent failure
                except Exception:
                    pass  # Silent failure

    except ImportError:
        pass  # Silent failure
    except Exception:
        pass  # Silent failure


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Validate price range
    if args.min_price is not None and args.max_price is not None:
        if args.min_price > args.max_price:
            parser.error("--min-price cannot be greater than --max-price")

    print(f"🔍 Starting AliExpress scraper for: '{args.keyword}'")
    print(f"📦 Brand: {args.brand}")
    print(f"📄 Pages to scrape: {args.pages}")

    if args.proxy_provider:
        print(f"🌐 Proxy provider: {args.proxy_provider}")
    else:
        print("🌐 Proxy provider: None (direct connection)")

    if args.discount:
        print("💰 Big Sale discount filter: ON")
    if args.free_shipping:
        print("🚚 Free shipping filter: ON")
    if args.min_price is not None:
        print(f"💵 Min price: ${args.min_price}")
    if args.max_price is not None:
        print(f"💵 Max price: ${args.max_price}")

    print("=" * 50)

    try:
        # Validate proxy credentials if proxy provider is specified
        if args.proxy_provider:
            validate_proxy_credentials(args.proxy_provider)

        # Initialize session
        fresh_cookies, fresh_user_agent = initialize_session_data(
            args.keyword, args.proxy_provider
        )

        # Scrape data
        raw_products, session = scrape_aliexpress_data(
            keyword=args.keyword,
            max_pages=args.pages,
            cookies=fresh_cookies,
            user_agent=fresh_user_agent,
            proxy_provider=args.proxy_provider,
            apply_discount_filter=args.discount,
            apply_free_shipping_filter=args.free_shipping,
            min_price=args.min_price,
            max_price=args.max_price,
            delay=args.delay,
        )

        # Check if store information is requested
        store_fields_requested = any(
            field in args.fields for field in ["Store Name", "Store ID", "Store URL"]
        )

        if store_fields_requested:
            print("🏪 Store information requested - fetching store details...")

        # Extract product details
        extracted_products = extract_product_details(
            raw_products,
            args.fields,
            args.brand,
            args.proxy_provider,
            session=session,
            fetch_store_info=store_fields_requested,
        )

        # Save results
        json_file, csv_file = save_results(
            args.keyword, extracted_products, args.fields
        )

        # Auto-retry store information if enabled
        if args.enable_store_retry:
            import asyncio

            print(f"\n🔄 Auto-retry enabled: Checking for missing store information...")

            try:
                # Run the store retry process if json_file is available
                if json_file:
                    asyncio.run(
                        auto_retry_store_info(
                            json_file=json_file,
                            products=extracted_products,
                            proxy_provider=args.proxy_provider,
                            batch_size=args.store_retry_batch_size,
                            delay=args.store_retry_delay,
                        )
                    )
            except Exception as e:
                print(f"⚠️ Auto-retry failed: {e}")

        print("\n✅ Scraping completed successfully!")
        print(f"📊 Total products extracted: {len(extracted_products)}")
        if json_file:
            print(f"💾 JSON file: {json_file}")
        if csv_file:
            print(f"📋 CSV file: {csv_file}")

    except KeyboardInterrupt:
        print("\n⚠️ Scraping interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during scraping: {e}")
        raise


if __name__ == "__main__":
    main()
