import time
import json
import os
import csv
from urllib.parse import quote_plus
from DrissionPage import WebPage, SessionPage, ChromiumOptions
import datetime
from typing import Generator
import threading
from queue import Queue
import time

API_URL = 'https://www.aliexpress.com/fn/search-pc/index'
RESULTS_DIR = "results"
SESSION_CACHE_FILE = "session_cache.json"
CACHE_EXPIRATION_SECONDS = 30 * 60

# --- Base Headers (User-Agent will be updated from browser or cache) ---
BASE_HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'bx-v': '2.5.28',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.aliexpress.com',
    'priority': 'u=1, i',
    'sec-ch-ua': '',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 ...',
}

def default_logger(message):
    print(message)

def initialize_session_data(keyword, log_callback=default_logger):
    """
    Checks for cached session data first. If valid cache exists, uses it.
    Otherwise, launches a browser with stealth options in headless mode,
    visits the search page using eager load mode, extracts cookies
    and user agent, saves them to cache, and then closes the browser.
    """
    log_callback(f"Initializing session for product: '{keyword}'")
    cached_data = None
    cache_valid = False

    if os.path.exists(SESSION_CACHE_FILE):
        try:
            with open(SESSION_CACHE_FILE, 'r') as f:
                cached_data = json.load(f)
            saved_timestamp = cached_data.get('timestamp', 0)
            current_timestamp = time.time()
            cache_age = current_timestamp - saved_timestamp

            if cache_age < CACHE_EXPIRATION_SECONDS:
                cache_valid = True
                log_callback(f"Using cached session data (Age: {datetime.timedelta(seconds=int(cache_age))}).")
                return cached_data['cookies'], cached_data['user_agent']
            else:
                log_callback(f"Cached session data expired (Age: {datetime.timedelta(seconds=int(cache_age))}).")

        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            log_callback(f"Error reading cache file or cache invalid ({e}). Will fetch fresh session.")
            cached_data = None
    else:
        pass

    # --- Cache Miss or Expired: Launch Browser ---
    log_callback("Fetching fresh session data using headless browser...")
    browser_page = None
    try:
        co = ChromiumOptions()
        co.no_imgs(True)
        # --- Block CSS ---
        co.set_pref('permissions.default.stylesheet', 2)
        co.headless()
        user_agent_string = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        co.set_user_agent(user_agent_string)
        # --- Other Stealth Options ---
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_pref('credentials_enable_service', False)
        co.set_pref('profile.password_manager_enabled', False)
        co.set_argument("--excludeSwitches", "enable-automation")

        browser_page = WebPage(chromium_options=co)
        browser_page.set.load_mode.eager()

        search_url = f'https://www.aliexpress.com/w/wholesale-{quote_plus(keyword)}.html'
        log_callback(f"Visiting initial search page (eager load, images and CSS blocked): {search_url}")
        browser_page.get(search_url)

        log_callback("Extracting fresh cookies and user agent...")
        fresh_cookies = browser_page.cookies().as_dict()
        fresh_user_agent = browser_page.user_agent
        log_callback(f"Using User-Agent: {fresh_user_agent}")
        log_callback(f"Extracted {len(fresh_cookies)} cookies.")

        cache_content = {
            'timestamp': time.time(),
            'cookies': fresh_cookies,
            'user_agent': fresh_user_agent
        }
        try:
            with open(SESSION_CACHE_FILE, 'w') as f:
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
        if browser_page:
            browser_page.quit()

def scrape_aliexpress_data(keyword, max_pages, cookies, user_agent,
                           apply_discount_filter=False, apply_free_shipping_filter=False,
                           min_price=None, max_price=None, delay=1.0, log_callback=default_logger):
    """
    Uses SessionPage and extracted session data to scrape product results
    for the given keyword via direct API calls, optionally applying filters.
    """
    log_callback(f"\nCreating SessionPage for API calls for product: '{keyword}'")
    session_page = SessionPage()
    session_page.set.cookies(cookies)

    current_base_headers = BASE_HEADERS.copy()
    current_base_headers['user-agent'] = user_agent

    all_products_raw = []
    keyword_safe_name = "".join(c if c.isalnum() else "_" for c in keyword)

    active_switches = []
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
            log_callback("Warning: Min price is greater than max price. Ignoring price filter.")
    elif min_price_int is not None:
        price_range_str = f"{min_price_int}-"
        log_callback(f"Applying Price Filter: Min {min_price_int}")
    elif max_price_int is not None:
        price_range_str = f"-{max_price_int}"
        log_callback(f"Applying Price Filter: Max {max_price_int}")

    for current_page_num in range(1, max_pages + 1):
        log_callback(f"Attempting to fetch page {current_page_num} for product: '{keyword}' via API...")

        request_headers = current_base_headers.copy()
        referer_keyword_part = quote_plus(keyword)
        referer_url = f'https://www.aliexpress.com/w/wholesale-{referer_keyword_part}.html?page={current_page_num}&g=y&SearchText={referer_keyword_part}'
        if active_switches:
            switches_value = ",".join(active_switches)
            referer_url += f'&selectedSwitches={quote_plus(switches_value)}'
        if price_range_str:
            referer_url += f'&pr={price_range_str}'
        request_headers['Referer'] = referer_url


        payload = {
            "pageVersion": "7ece9c0cc9cf2052db74f0d1b26b7033",
            "target": "root",
            "data": {
                "page": current_page_num,
                "g": "y",
                "SearchText": keyword,
                "origin": "y"
            },
            "eventName": "onChange",
            "dependency": []
        }

        if active_switches:
            payload['data']['selectedSwitches'] = ",".join(active_switches)
        if price_range_str:
            payload['data']['pr'] = price_range_str

        # Make the POST request
        success = session_page.post(API_URL, json=payload, headers=request_headers)

        if not success or not session_page.response or session_page.response.status_code != 200:
            status = session_page.response.status_code if session_page.response else 'N/A'
            log_callback(f"Failed to fetch page {current_page_num}. Status code: {status}")
            if session_page.response:
                log_callback(f"Response text sample: {session_page.response.text[:200]}")
            break

        try:
            json_data = session_page.json
            if not isinstance(json_data, dict):
                log_callback(f"Unexpected response format for page {current_page_num}. Expected JSON dict.")
                log_callback(f"Response text sample: {session_page.html[:200]}")
                break

            items_list = json_data.get('data', {}).get('result', {}).get('mods', {}).get('itemList', {}).get('content', [])

            if not items_list:
                log_callback(f"No items found using path 'data.result.mods.itemList.content' on page {current_page_num}.")
                if current_page_num == max_pages:
                    log_callback(f"Reached requested page limit ({max_pages}) with no items found on this last page.")
                    break
                elif current_page_num > 1:
                    log_callback(f"Stopping search: No items found on page {current_page_num} (before requested limit of {max_pages} pages).")
                    break
                else:
                    log_callback("Continuing to next page (in case only page 1 structure differs).")
            else:
                log_callback(f"Found {len(items_list)} items on page {current_page_num}.")
                all_products_raw.extend(items_list)

        except json.JSONDecodeError:
            log_callback(f"Failed to decode JSON response for page {current_page_num}.")
            log_callback(f"Response text sample: {session_page.html[:200]}")
            break
        except Exception as e:
            log_callback(f"An error occurred processing page {current_page_num}: {e}")
            break

        # Delay between requests
        time.sleep(delay)

    log_callback(f"\nAPI Scraping finished for product: '{keyword}'. Total raw products collected: {len(all_products_raw)}")
    return all_products_raw

def extract_product_details(raw_products, selected_fields, log_callback=default_logger):
    """
    Extracts and formats desired fields from the raw product data,
    based on the user's selection.
    """
    extracted_data = []
    if not raw_products or not selected_fields:
        log_callback("No raw products or selected fields for extraction.")
        return extracted_data

    log_callback(f"Extracting selected fields: {selected_fields}")
    for product in raw_products:
        # --- Extract ALL possible fields first ---
        product_id = product.get('productId')
        title = product.get('title', {}).get('displayTitle')
        image_url = product.get('image', {}).get('imgUrl')
        if image_url and not image_url.startswith('http'):
            image_url = 'https:' + image_url
        prices_info = product.get('prices', {})
        sale_price_info = prices_info.get('salePrice', {})
        original_price_info = prices_info.get('originalPrice', {})
        sale_price = sale_price_info.get('formattedPrice')
        original_price = original_price_info.get('formattedPrice')
        currency = sale_price_info.get('currencyCode')
        discount = sale_price_info.get('discount')
        store_info = product.get('store', {})
        store_name = store_info.get('storeName')
        store_id = store_info.get('storeId')
        store_url = store_info.get('storeUrl')
        if store_url and not store_url.startswith('http'):
            store_url = 'https:' + store_url
        trade_info = product.get('trade', {})
        orders_count = trade_info.get('realTradeCount')
        rating = product.get('evaluation', {}).get('starRating')
        product_url = f"https://www.aliexpress.com/item/{product_id}.html" if product_id else None

        # --- Store all potentially extractable data in a temporary dict ---
        full_details = {
            'Product ID': product_id,
            'Title': title,
            'Sale Price': sale_price,
            'Original Price': original_price,
            'Discount (%)': discount,
            'Currency': currency,
            'Rating': rating,
            'Orders Count': orders_count,
            'Store Name': store_name,
            'Store ID': store_id,
            'Store URL': store_url,
            'Product URL': product_url,
            'Image URL': image_url,
        }

        filtered_item = {field: full_details.get(field) for field in selected_fields}

        extracted_data.append(filtered_item)

    log_callback(f"Extracted data for {len(extracted_data)} products with selected fields.")
    return extracted_data

def save_results(keyword, data, selected_fields, log_callback=default_logger):
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
    json_filename = os.path.join(RESULTS_DIR, f'aliexpress_{keyword_safe_name}_extracted.json')
    csv_filename = os.path.join(RESULTS_DIR, f'aliexpress_{keyword_safe_name}_extracted.csv')

    try:
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        fieldnames = selected_fields
        with open(csv_filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
        
        log_callback(f"JSON and CSV results saved to: {json_filename}, {csv_filename}")

        return json_filename, csv_filename

    except Exception as e:
        log_callback(f"Error saving results to file: {e}")
        return None, None

class StreamLogger:
    def __init__(self):
        self.message_queue = Queue()
        self.active = True
    
    def log(self, message):
        if self.active:
            self.message_queue.put(message)
    
    def stream_messages(self):
        while self.active or not self.message_queue.empty():
            try:
                message = self.message_queue.get(timeout=0.1)
                yield f"data: {message}\n\n"
                self.message_queue.task_done()
            except:
                continue
        yield "data: PROCESS_COMPLETE\n\n"
    
    def stop(self):
        self.active = False

def run_scrape_job(keyword, pages, apply_discount, free_shipping, min_price, max_price, selected_fields, delay=1.0):
    """
    Generator function that orchestrates the scraping process with real-time logging.
    """
    logger = StreamLogger()
    
    def scrape_task():
        try:
            cookies, user_agent = initialize_session_data(
                keyword,
                log_callback=logger.log
            )
            
            logger.log(f"Starting scraping for {pages} pages...")
            raw_products = scrape_aliexpress_data(
                keyword=keyword,
                max_pages=pages,
                cookies=cookies,
                user_agent=user_agent,
                apply_discount_filter=apply_discount,
                apply_free_shipping_filter=free_shipping,
                min_price=min_price,
                max_price=max_price,
                delay=delay,
                log_callback=logger.log
            )
            
            logger.log("Extracting product details...")
            extracted_data = extract_product_details(
                raw_products,
                selected_fields,
                log_callback=logger.log
            )
            
            logger.log("Saving results...")
            json_file, csv_file = save_results(
                keyword,
                extracted_data,
                selected_fields,
                log_callback=logger.log
            )
            
        except Exception as e:
            logger.log(f"ERROR: {str(e)}")
        finally:
            logger.stop()
    
    threading.Thread(target=scrape_task, daemon=True).start()
    
    yield from logger.stream_messages()


if __name__ == "__main__":
    # Get keyword from user
    search_keyword_input = input("Enter the product to search for on AliExpress: ").strip()

    if not search_keyword_input:
        print("Error: No search product provided. Exiting.")
    else:
        num_pages_to_scrape = 0
        while True:
            try:
                num_pages_input = input("Enter the number of pages to scrape (1-60): ").strip()
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
        raw_products = scrape_aliexpress_data(search_keyword_input, num_pages_to_scrape,
                                             fresh_cookies, fresh_user_agent)
        all_fields_for_direct_run = [
            'Product ID', 'Title', 'Sale Price', 'Original Price', 'Discount (%)',
            'Currency', 'Rating', 'Orders Count', 'Store Name', 'Store ID',
            'Store URL', 'Product URL', 'Image URL'
        ]
        extracted_products = extract_product_details(raw_products, all_fields_for_direct_run)
        save_results(search_keyword_input, extracted_products, all_fields_for_direct_run)
        print("\nScript finished.")
