import csv
import datetime
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple
from urllib.parse import quote_plus

from dotenv import load_dotenv
from DrissionPage import ChromiumOptions, SessionPage, WebPage
from playwright.sync_api import sync_playwright

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

# Validate required proxy credentials
if not OXYLABS_USERNAME or not OXYLABS_PASSWORD:
    raise ValueError(
        "Missing Oxylabs credentials! Please ensure OXYLABS_USERNAME and OXYLABS_PASSWORD "
        "are set in your .env file or environment variables."
    )

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


def initialize_session_data(
    keyword: str, log_callback: Callable[[str], None] = default_logger
) -> Tuple[Dict[str, Any], str]:
    """
    Checks for cached session data first. If valid cache exists, uses it.
    Otherwise, when proxy is configured, uses predefined US-region defaults
    to ensure USD currency. When no proxy is configured, launches a browser
    to extract session data.
    """
    log_callback(f"Initializing session for product: '{keyword}'")

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
    log_callback(
        "Fetching fresh session data using headless browser with Oxylabs U.S. residential proxy..."
    )
    browser_page = None
    try:
        co = ChromiumOptions()
        # Set the browser path to snap-installed Chromium
        co.set_browser_path("/snap/bin/chromium")
        co.no_imgs(True)
        # --- Block CSS ---
        co.set_pref("permissions.default.stylesheet", 2)
        co.headless()
        user_agent_string = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        co.set_user_agent(user_agent_string)

        # --- Configure Oxylabs U.S. Residential Proxy ---
        proxy_auth = f"{OXYLABS_USERNAME}:{OXYLABS_PASSWORD}"
        proxy_server = f"http://{proxy_auth}@{OXYLABS_ENDPOINT}"
        co.set_proxy(proxy_server)
        log_callback(f"Configured Oxylabs U.S. residential proxy: {OXYLABS_ENDPOINT}")

        # --- Other Stealth Options ---
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_pref("credentials_enable_service", False)
        co.set_pref("profile.password_manager_enabled", False)
        co.set_argument("--excludeSwitches", "enable-automation")

        browser_page = WebPage(chromium_options=co)  # type: ignore
        browser_page.set.load_mode.eager()

        search_url = (
            f"https://www.aliexpress.com/w/wholesale-{quote_plus(keyword)}.html"
        )
        log_callback(
            f"Visiting initial search page (eager load, images and CSS blocked): {search_url}"
        )
        browser_page.get(search_url)  # type: ignore

        log_callback("Extracting fresh cookies and user agent...")
        fresh_cookies = browser_page.cookies().as_dict()  # type: ignore
        fresh_user_agent = browser_page.user_agent
        log_callback(f"Using User-Agent: {fresh_user_agent}")
        log_callback(f"Extracted {len(fresh_cookies)} cookies.")  # type: ignore

        cache_content: Dict[str, Any] = {
            "timestamp": time.time(),
            "cookies": fresh_cookies,  # type: ignore
            "user_agent": fresh_user_agent,
        }
        try:
            with open(SESSION_CACHE_FILE, "w") as f:
                json.dump(cache_content, f, indent=4)
            log_callback("Session data cached successfully.")
        except IOError as e:
            log_callback(f"Error saving session cache: {e}")

        return fresh_cookies, fresh_user_agent  # type: ignore

    except Exception as e:
        log_callback(f"An error occurred during browser initialization: {e}")
        raise
    finally:
        # --- Ensure browser is closed ---
        if browser_page:
            browser_page.quit()


def scrape_aliexpress_data(
    keyword: str,
    max_pages: int,
    cookies: Dict[str, Any],
    user_agent: str,
    apply_discount_filter: bool = False,
    apply_free_shipping_filter: bool = False,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    delay: float = 1.0,
    log_callback: Callable[[str], None] = default_logger,
) -> Tuple[List[Dict[str, Any]], Any]:
    """
    Uses SessionPage and extracted session data to scrape product results
    for the given keyword via direct API calls, optionally applying filters.
    Returns (raw_products, session_page) tuple.
    """
    log_callback(
        f"\nCreating SessionPage with Oxylabs U.S. residential proxy for API calls for product: '{keyword}'"
    )
    session_page = SessionPage()

    # Configure proxy for SessionPage
    proxy_auth = f"{OXYLABS_USERNAME}:{OXYLABS_PASSWORD}"
    proxy_url = f"http://{proxy_auth}@{OXYLABS_ENDPOINT}"

    session_page.set.proxies(http=proxy_url, https=proxy_url)
    session_page.set.cookies(cookies)

    current_base_headers = BASE_HEADERS.copy()
    current_base_headers["user-agent"] = user_agent

    all_products_raw: List[Dict[str, Any]] = []

    active_switches: List[str] = []
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

        payload: Dict[str, Any] = {
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

        # Make the POST request
        success = session_page.post(API_URL, json=payload, headers=request_headers)  # type: ignore

        if (
            not success
            or not session_page.response
            or session_page.response.status_code != 200
        ):
            status = (
                session_page.response.status_code if session_page.response else "N/A"
            )
            log_callback(
                f"Failed to fetch page {current_page_num}. Status code: {status}"
            )
            if session_page.response:
                log_callback(
                    f"Response text sample: {session_page.response.text[:200]}"
                )
            break

        try:
            json_data = session_page.json  # type: ignore
            if not isinstance(json_data, dict):
                log_callback(
                    f"Unexpected response format for page {current_page_num}. Expected JSON dict."
                )
                log_callback(f"Response text sample: {session_page.html[:200]}")
                break

            items_list = (  # type: ignore
                json_data.get("data", {})  # type: ignore
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
                    f"Found {len(items_list)} items on page {current_page_num}."  # type: ignore
                )
                all_products_raw.extend(items_list)  # type: ignore

        except json.JSONDecodeError:
            log_callback(f"Failed to decode JSON response for page {current_page_num}.")
            log_callback(f"Response text sample: {session_page.html[:200]}")
            break
        except Exception as e:
            log_callback(f"An error occurred processing page {current_page_num}: {e}")
            break

        # Delay between requests
        time.sleep(delay)

    log_callback(
        f"\nAPI Scraping finished for product: '{keyword}'. Total raw products collected: {len(all_products_raw)}"
    )
    return all_products_raw, session_page


def fetch_store_info_batch(
    product_ids: List[str],
    session_page: Any,
    log_callback: Callable[[str], None] = default_logger,
    max_workers: int = 3,
) -> Dict[str, Optional[Dict[str, Optional[str]]]]:
    """
    Fetches store information for multiple products using a shared browser pool.
    Much faster than fetching one product at a time.
    Returns a dict mapping product_id -> store_info.

    Note: Store info fetching will attempt to work with proxy authentication,
    but may have limitations due to DrissionPage WebPage proxy support.
    """
    if not product_ids:
        return {}

    log_callback(
        f"Fetching store info for {len(product_ids)} products using {max_workers} workers..."
    )

    # Shared browser pool to reuse browser instances
    store_results: Dict[str, Optional[Dict[str, Optional[str]]]] = {}

    def create_browser() -> Any:
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

        # Try to configure proxy settings for Oxylabs
        try:
            if OXYLABS_USERNAME and OXYLABS_PASSWORD:
                log_callback(
                    f"Configured proxy: {OXYLABS_ENDPOINT} with user: {OXYLABS_USERNAME[:10]}..."
                )

                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
                    proxy={
                        "server": f"http://{OXYLABS_ENDPOINT}",
                        "username": OXYLABS_USERNAME,
                        "password": OXYLABS_PASSWORD,
                    },
                )
            else:
                log_callback(
                    "WARNING: No proxy credentials found, creating context without proxy"
                )

                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
                )
        except Exception as e:
            log_callback(
                f"WARNING: Failed to configure proxy, falling back to no proxy: {e}"
            )

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
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
    ) -> Optional[Dict[str, Optional[str]]]:
        """Fetch store info for a single product using Playwright browser"""
        try:
            product_url = f"https://www.aliexpress.com/item/{product_id}.html"
            page = browser_obj["page"]

            log_callback(f"Navigating to {product_url} with Oxylabs proxy...")

            # Navigate to the page with increased timeout
            page.goto(product_url, timeout=30000, wait_until="domcontentloaded")

            # Wait a moment for dynamic content to load
            page.wait_for_timeout(3000)

            # Get HTML content for analysis
            html_content = page.content()

            # Write the html_content to file for debug
            # with open(f"playwright_debug_{product_id}.html", "w", encoding="utf-8") as f:
            #     f.write(html_content)

            log_callback(f"Page loaded successfully, HTML length: {len(html_content)}")

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

            log_callback(f"Extracted store info for {product_id}:")
            log_callback(f"  Store Name: {store_name}")
            log_callback(f"  Store ID: {store_id}")
            log_callback(f"  Store URL: {store_url}")

            return {
                "store_name": store_name,
                "store_id": store_id,
                "store_url": store_url,
            }

        except Exception as e:
            log_callback(f"Error fetching store info for {product_id}: {e}")
            return None

    def worker_function(
        worker_id: int, product_batch: List[str]
    ) -> Dict[str, Optional[Dict[str, Optional[str]]]]:
        """Worker function that processes a batch of products"""
        browser: Optional[Any] = None
        worker_results: Dict[str, Optional[Dict[str, Optional[str]]]] = {}

        try:
            browser = create_browser()
            log_callback(
                f"Worker {worker_id}: Processing {len(product_batch)} products"
            )

            for i, product_id in enumerate(product_batch):
                try:
                    store_info = fetch_single_store_info(product_id, browser)
                    worker_results[product_id] = store_info

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
                    worker_results[product_id] = None

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
        futures: List[Any] = []
        for i, batch in enumerate(product_batches):
            future = executor.submit(worker_function, i + 1, batch)
            futures.append(future)

        # Collect results
        for future in as_completed(futures):
            try:
                worker_results = future.result()
                store_results.update(worker_results)
            except Exception as e:
                log_callback(f"Worker failed: {e}")

    successful_fetches = sum(
        1 for result in store_results.values() if result is not None
    )
    log_callback(
        f"Store info batch fetch complete: {successful_fetches}/{len(product_ids)} successful"
    )

    return store_results


def fetch_store_info_from_product_page(
    product_id: str,
    session_page: Any,
    log_callback: Callable[[str], None] = default_logger,
) -> Optional[Dict[str, Optional[str]]]:
    """
    Legacy function for backward compatibility.
    For better performance, use fetch_store_info_batch() instead.
    """
    if not product_id:
        return None

    # Use the batch function for single product
    results = fetch_store_info_batch(
        [product_id], session_page, log_callback, max_workers=1
    )
    return results.get(product_id)


def extract_product_details(
    raw_products: List[Dict[str, Any]],
    selected_fields: List[str],
    session_page: Optional[Any] = None,
    fetch_store_info: bool = False,
    log_callback: Callable[[str], None] = default_logger,
) -> List[Dict[str, Any]]:
    """
    Extracts and formats desired fields from the raw product data,
    based on the user's selection. Now uses batch processing for store info.
    """
    extracted_data: List[Dict[str, Any]] = []
    if not raw_products or not selected_fields:
        log_callback("No raw products or selected fields for extraction.")
        return extracted_data

    log_callback(f"Extracting selected fields: {selected_fields}")

    # Collect all product IDs that need store info
    store_info_results: Dict[str, Optional[Dict[str, Optional[str]]]] = {}
    if fetch_store_info and session_page:
        store_fields_requested = any(
            field in selected_fields
            for field in ["Store Name", "Store ID", "Store URL"]
        )
        if store_fields_requested:
            product_ids: List[str] = [
                str(product.get("productId"))
                for product in raw_products
                if product.get("productId")
            ]
            if product_ids:
                log_callback(
                    f"Batch fetching store info for {len(product_ids)} products..."
                )
                store_info_results = fetch_store_info_batch(
                    product_ids, session_page, log_callback, max_workers=3
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
        full_details: Dict[str, Any] = {
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
        }

        filtered_item: Dict[str, Any] = {
            field: full_details.get(field) for field in selected_fields
        }

        extracted_data.append(filtered_item)

    log_callback(
        f"Extracted data for {len(extracted_data)} products with selected fields."
    )
    return extracted_data


def save_results(
    keyword: str,
    data: List[Dict[str, Any]],
    selected_fields: List[str],
    log_callback: Callable[[str], None] = default_logger,
) -> Tuple[Optional[str], Optional[str]]:
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
    apply_discount: bool,
    free_shipping: bool,
    min_price: Optional[float],
    max_price: Optional[float],
    selected_fields: List[str],
    delay: float = 1.0,
) -> Generator[str, None, None]:
    """
    Generator function that orchestrates the scraping process with real-time logging.
    """
    logger = StreamLogger()

    def scrape_task() -> None:
        try:
            cookies, user_agent = initialize_session_data(
                keyword, log_callback=logger.log
            )

            logger.log(f"Starting scraping for {pages} pages...")
            raw_products, session_page = scrape_aliexpress_data(
                keyword=keyword,
                max_pages=pages,
                cookies=cookies,
                user_agent=user_agent,
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
                session_page=session_page,
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


if __name__ == "__main__":
    # Get keyword from user
    search_keyword_input = input(
        "Enter the product to search for on AliExpress: "
    ).strip()

    if not search_keyword_input:
        print("Error: No search product provided. Exiting.")
    else:
        num_pages_to_scrape = 0
        while True:
            try:
                num_pages_input = input(
                    "Enter the number of pages to scrape (1-60): "
                ).strip()
                if not num_pages_input.isdigit():
                    print("Invalid input. Please enter a number.")
                    continue

                num_pages_to_scrape = int(num_pages_input)
                if 1 <= num_pages_to_scrape <= 60:
                    break
                else:
                    print("Invalid number. Please enter a number between 1 and 60.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        fresh_cookies, fresh_user_agent = initialize_session_data(search_keyword_input)
        raw_products, session_page = scrape_aliexpress_data(
            search_keyword_input, num_pages_to_scrape, fresh_cookies, fresh_user_agent
        )
        all_fields_for_direct_run = [
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
        ]

        # Enable store info fetching for direct run
        store_fields_requested = any(
            field in all_fields_for_direct_run
            for field in ["Store Name", "Store ID", "Store URL"]
        )

        extracted_products = extract_product_details(
            raw_products,
            all_fields_for_direct_run,
            session_page=session_page,
            fetch_store_info=store_fields_requested,
        )
        save_results(
            search_keyword_input, extracted_products, all_fields_for_direct_run
        )
        print("\nScript finished.")
