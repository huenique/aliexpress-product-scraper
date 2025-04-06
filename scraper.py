import time
import json
import os
import csv
from urllib.parse import quote_plus, urlencode
from DrissionPage import WebPage, SessionPage, ChromiumOptions
import datetime
from typing import Generator
import threading
from queue import Queue
import time
import math # Import math for floor/ceil if needed, or just int()

# --- Configuration ---
API_URL = 'https://www.aliexpress.com/fn/search-pc/index'
RESULTS_DIR = "results"
FAILED_RESPONSES_DIR = os.path.join(RESULTS_DIR, "failed_responses")
SESSION_CACHE_FILE = "session_cache.json"
CACHE_EXPIRATION_SECONDS = 30 * 60
# Filenames will now include the keyword for better organization

# --- Base Headers (User-Agent will be updated from browser or cache) ---
BASE_HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'bx-v': '2.5.28',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.aliexpress.com',
    'priority': 'u=1, i',
    # 'Referer': Will be added dynamically in the loop
    'sec-ch-ua': '', # Will be set by browser
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '', # Will be set by browser
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 ...',  # Placeholder, will be updated dynamically
}

# --- Helper function for logging ---
def default_logger(message):
    print(message)

def initialize_session_data(keyword, log_callback=default_logger):
    """
    Checks for cached session data first. If valid cache exists, uses it.
    Otherwise, launches a browser with stealth options in headless mode,
    visits the search page using eager load mode + delay, extracts cookies
    and user agent, saves them to cache, and then closes the browser.
    Uses a specific User-Agent and blocks images and CSS for faster initialization.
    """
    log_callback(f"Initializing session for keyword: '{keyword}'")
    cached_data = None
    cache_valid = False

    # --- Try loading from cache ---
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
        # log_callback("No session cache file found. Will fetch fresh session.") # Removed: Verbose
        pass # Keep the flow

    # --- Cache Miss or Expired: Launch Browser ---
    log_callback("Fetching fresh session data using headless browser...")
    browser_page = None
    try:
        # --- Configure Stealth Options ---
        log_callback("Configuring browser options for stealth and headless mode...")
        co = ChromiumOptions()
        # --- Block Images ---
        # log_callback("Blocking image loading...") # Removed: Verbose
        co.no_imgs(True)
        # --- Block CSS ---
        # log_callback("Blocking CSS loading...") # Removed: Verbose
        co.set_pref('permissions.default.stylesheet', 2)
        # --- Add Headless Mode ---
        co.headless()
        # --- Set Specific User Agent ---
        user_agent_string = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        # log_callback(f"Setting User-Agent to: {user_agent_string}") # Removed: Verbose
        co.set_user_agent(user_agent_string)
        # --- Other Stealth Options ---
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_pref('credentials_enable_service', False)
        co.set_pref('profile.password_manager_enabled', False)
        co.set_argument("--excludeSwitches", "enable-automation")
        # ---------------------------------

        # log_callback("Launching headless browser...") # Removed: Verbose
        browser_page = WebPage(chromium_options=co)

        # --- Use 'eager' load mode ---
        # log_callback("Setting load mode to 'eager'...") # Removed: Verbose
        browser_page.set.load_mode.eager()
        # -----------------------------

        search_url = f'https://www.aliexpress.com/w/wholesale-{quote_plus(keyword)}.html'
        log_callback(f"Visiting initial search page (eager load, images and CSS blocked): {search_url}")
        browser_page.get(search_url)

        # --- Add explicit delay after eager load ---
        # delay_seconds = 2
        # log_callback(f"Waiting for {delay_seconds} seconds after eager load...")
        # time.sleep(delay_seconds)
        # -----------------------------------------

        # log_callback("Headless browser session established (eager load, images and CSS blocked).") # Removed: Verbose

        log_callback("Extracting fresh cookies and user agent...")
        fresh_cookies = browser_page.cookies().as_dict()
        fresh_user_agent = browser_page.user_agent
        log_callback(f"Using User-Agent: {fresh_user_agent}")
        log_callback(f"Extracted {len(fresh_cookies)} cookies.")

        # --- Save to Cache ---
        log_callback(f"Saving fresh session data to {SESSION_CACHE_FILE}...")
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
            # log_callback("Closing the headless browser...") # Removed: Verbose
            browser_page.quit()
            # log_callback("Headless browser closed.") # Removed: Verbose

def scrape_aliexpress_data(keyword, max_pages, cookies, user_agent,
                           apply_discount_filter=False, apply_free_shipping_filter=False,
                           min_price=None, max_price=None, log_callback=default_logger):
    """
    Uses SessionPage and extracted session data to scrape product results
    for the given keyword via direct API calls, optionally applying filters.
    """
    log_callback(f"\nCreating SessionPage for API calls for '{keyword}'...")
    session_page = SessionPage()
    session_page.set.cookies(cookies)

    # Update base headers with the fresh user agent
    current_base_headers = BASE_HEADERS.copy()
    current_base_headers['user-agent'] = user_agent

    all_products_raw = []
    keyword_safe_name = "".join(c if c.isalnum() else "_" for c in keyword)
    failed_dir_for_keyword = os.path.join(FAILED_RESPONSES_DIR, keyword_safe_name)
    os.makedirs(failed_dir_for_keyword, exist_ok=True)

    for current_page_num in range(1, max_pages + 1):
        log_callback(f"Attempting to fetch page {current_page_num} for '{keyword}' via API...")

        # --- Build Filters ---
        active_switches = []
        if apply_discount_filter:
            log_callback("Applying 'Big Sale' discount filter...")
            active_switches.append("filterCode:bigsale")
        if apply_free_shipping_filter:
            log_callback("Applying 'Free Shipping' filter...")
            active_switches.append("filterCode:freeshipping")

        # --- Handle Price Filter ---
        price_range_str = None
        min_price_int = int(min_price) if min_price is not None and min_price >= 0 else None
        max_price_int = int(max_price) if max_price is not None and max_price >= 0 else None

        if min_price_int is not None and max_price_int is not None:
            # Ensure min is less than or equal to max if both provided
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
        # --- End Price Filter ---

        # Prepare Headers for THIS request
        request_headers = current_base_headers.copy()
        referer_keyword_part = quote_plus(keyword)
        # Start building the referer URL (base parts)
        referer_url = f'https://www.aliexpress.com/w/wholesale-{referer_keyword_part}.html?page={current_page_num}&g=y&SearchText={referer_keyword_part}'
        # Conditionally add the combined filter switches
        if active_switches:
            switches_value = ",".join(active_switches)
            referer_url += f'&selectedSwitches={quote_plus(switches_value)}'
        # Conditionally add the price filter
        if price_range_str:
            referer_url += f'&pr={price_range_str}' # Add price range to referer
        request_headers['Referer'] = referer_url

        # Prepare the JSON payload - Start with base payload
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

        # Conditionally add the combined filter switches
        if active_switches:
            payload['data']['selectedSwitches'] = ",".join(active_switches)
        # Conditionally add the price filter
        if price_range_str:
            payload['data']['pr'] = price_range_str # Add price range to payload

        # Make the POST request
        success = session_page.post(API_URL, json=payload, headers=request_headers)

        # Check for request failure
        if not success or not session_page.response or session_page.response.status_code != 200:
            status = session_page.response.status_code if session_page.response else 'N/A'
            log_callback(f"Failed to fetch page {current_page_num}. Status code: {status}")
            if session_page.response:
                log_callback(f"Response text sample: {session_page.response.text[:200]}") # Log sample
            break  # Stop if a page fails

        # Process the successful response
        try:
            json_data = session_page.json
            if not isinstance(json_data, dict):
                log_callback(f"Unexpected response format for page {current_page_num}. Expected JSON dict.")
                log_callback(f"Response text sample: {session_page.html[:200]}") # Log sample
                break  # Stop if format is wrong

            # Extract items list
            items_list = json_data.get('data', {}).get('result', {}).get('mods', {}).get('itemList', {}).get('content', [])

            if not items_list:
                log_callback(f"No items found using path 'data.result.mods.itemList.content' on page {current_page_num}.")
                # Save failed response
                file_path = os.path.join(failed_dir_for_keyword, f"failed_page_{current_page_num}.json")
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=2)
                    log_callback(f"Received JSON data saved to: {file_path}")
                except Exception as e:
                    log_callback(f"Error saving failed response JSON to {file_path}: {e}")

                # Decide whether to stop based on page number
                if current_page_num > 1:
                    log_callback("Stopping due to empty item list on subsequent page.")
                    break
                else:
                    log_callback("Continuing to next page (in case only page 1 structure differs).")
            else:
                # Items found, add them
                log_callback(f"Found {len(items_list)} items on page {current_page_num}.")
                all_products_raw.extend(items_list)

        except json.JSONDecodeError:
            log_callback(f"Failed to decode JSON response for page {current_page_num}.")
            log_callback(f"Response text sample: {session_page.html[:200]}") # Log sample
            break  # Stop on JSON error
        except Exception as e:
            log_callback(f"An error occurred processing page {current_page_num}: {e}")
            break  # Stop on other errors

        # Delay between requests (still inside the loop)
        time.sleep(1.5)

    log_callback(f"\nAPI Scraping finished for '{keyword}'. Total raw products collected: {len(all_products_raw)}")
    return all_products_raw

def extract_product_details(raw_products, selected_fields, log_callback=default_logger):
    """
    Extracts and formats desired fields from the raw product data,
    based on the user's selection.
    """
    extracted_data = []
    if not raw_products or not selected_fields: # Check if fields selected
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

        # --- Filter the details based on selected_fields ---
        filtered_item = {field: full_details.get(field) for field in selected_fields}
        # Ensure keys exist even if value is None using .get() ^

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
        return None, None # Return None for filenames if no data
    if not selected_fields:
        log_callback("No fields selected for saving.")
        return None, None # Return None

    os.makedirs(RESULTS_DIR, exist_ok=True)
    keyword_safe_name = "".join(c if c.isalnum() else "_" for c in keyword)
    json_filename = os.path.join(RESULTS_DIR, f'aliexpress_{keyword_safe_name}_extracted.json')
    csv_filename = os.path.join(RESULTS_DIR, f'aliexpress_{keyword_safe_name}_extracted.csv')

    try:
        # Save as JSON (already contains only selected fields from extraction)
        # log_callback(f"Saving JSON results to {json_filename}...") # Removed: Will consolidate
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # log_callback("JSON results saved.") # Removed: Will consolidate

        # Save as CSV - Use selected_fields as headers
        # log_callback(f"Saving CSV results to {csv_filename}...") # Removed: Will consolidate
        # Use the passed selected_fields directly for fieldnames
        fieldnames = selected_fields
        with open(csv_filename, 'w', encoding='utf-8', newline='') as f:
            # Use extrasaction='ignore' in case data somehow has extra keys (shouldn't happen)
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data) # data already contains dicts with only selected keys
        # log_callback("CSV results saved.") # Removed: Will consolidate
        
        # Consolidated success message
        log_callback(f"JSON and CSV results saved to: {json_filename}, {csv_filename}")

        return json_filename, csv_filename # Return filenames on success

    except Exception as e:
        log_callback(f"Error saving results to file: {e}")
        return None, None # Return None on error

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

def run_scrape_job(keyword, pages, apply_discount, free_shipping, min_price, max_price, selected_fields):
    """
    Generator function that orchestrates the scraping process with real-time logging.
    """
    logger = StreamLogger()
    
    def scrape_task():
        try:
            logger.log(f"Initializing session for keyword: '{keyword}'")
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
            
            logger.log(f"Scraping complete! Results saved to:\n- {json_file}\n- {csv_file}")
            
        except Exception as e:
            logger.log(f"ERROR: {str(e)}")
        finally:
            logger.stop()
    
    # Start the scraping in a separate thread
    threading.Thread(target=scrape_task, daemon=True).start()
    
    # Stream messages as they come
    yield from logger.stream_messages()

# --- Main Execution ---
if __name__ == "__main__":
    # Get keyword from user
    search_keyword_input = input("Enter the product keyword to search for on AliExpress: ").strip()

    if not search_keyword_input:
        print("Error: No search keyword provided. Exiting.")
    else:
        # Get number of pages from user and validate
        num_pages_to_scrape = 0
        while True:
            try:
                num_pages_input = input("Enter the number of pages to scrape (1-60): ").strip()
                if not num_pages_input.isdigit():
                    print("Invalid input. Please enter a number.")
                    continue

                num_pages_to_scrape = int(num_pages_input)
                if 1 <= num_pages_to_scrape <= 60:
                    break  # Valid input, exit loop
                else:
                    print("Invalid number. Please enter a number between 1 and 60.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        # Pass the user input to the functions
        fresh_cookies, fresh_user_agent = initialize_session_data(search_keyword_input)
        # Use the validated number of pages from user input
        raw_products = scrape_aliexpress_data(search_keyword_input, num_pages_to_scrape,
                                             fresh_cookies, fresh_user_agent)
        # Use all fields for direct run (or define a default list here)
        all_fields_for_direct_run = [
            'Product ID', 'Title', 'Sale Price', 'Original Price', 'Discount (%)',
            'Currency', 'Rating', 'Orders Count', 'Store Name', 'Store ID',
            'Store URL', 'Product URL', 'Image URL'
        ]
        extracted_products = extract_product_details(raw_products, all_fields_for_direct_run)
        # Pass keyword to save_results for filename generation
        save_results(search_keyword_input, extracted_products, all_fields_for_direct_run)
        print("\nScript finished.")
