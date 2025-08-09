#!/usr/bin/env python3
"""
Enhanced AliExpress Scraper with Captcha Solver Integration
===========================================================

Extends the original scraper with automatic captcha solving capabilities,
intelligent retry logic, and comprehensive logging.

Features:
- Automatic captcha detection and solving
- Session caching with expiration management
- Enhanced store information extraction with retry
- Streaming mode for memory-efficient processing
- Comprehensive logging with progress tracking
- Proxy support for improved reliability
"""

import argparse
import asyncio
import csv
import datetime
import json
import os
import time
from typing import Any, Callable, cast
from urllib.parse import quote_plus

from ..core.captcha_solver import CaptchaSolverContext, CaptchaSolverIntegration
from ..core.scraper import (
    CACHE_EXPIRATION_SECONDS,
    OXYLABS_ENDPOINT,
    OXYLABS_PASSWORD,
    OXYLABS_USERNAME,
    SESSION_CACHE_FILE,
    default_logger,
    initialize_session_data,
    scrape_aliexpress_data,
    validate_proxy_credentials,
)

# Import enhanced store scraper integration
try:
    from ..store.store_integration import (
        enhance_existing_scraper_with_store_integration,
    )

    # Apply the enhanced store integration to existing scraper functions
    enhance_existing_scraper_with_store_integration()
    pass  # Silent integration
except ImportError as e:
    print(f"⚠️ Enhanced store integration not available: {e}")
except Exception as e:
    print(f"❌ Error applying store integration: {e}")


class EnhancedAliExpressScraper:
    """Enhanced scraper with captcha solving capabilities"""

    def __init__(
        self,
        proxy_provider: str = "",
        enable_captcha_solver: bool = True,
        captcha_solver_headless: bool = True,
        enable_store_retry: bool = False,
        store_retry_batch_size: int = 5,
        store_retry_delay: float = 2.0,
        log_callback: Callable[[str], None] = default_logger,
    ):
        """
        Initialize enhanced scraper

        Args:
            proxy_provider: Proxy provider ("oxylabs", "massive", or "" for none)
            enable_captcha_solver: Whether to enable automatic captcha solving
            captcha_solver_headless: Whether to run captcha solver in headless mode
            enable_store_retry: Whether to automatically retry missing store information
            store_retry_batch_size: Batch size for store retry operations
            store_retry_delay: Delay between store retry batches
            log_callback: Logging function
        """
        self.proxy_provider = proxy_provider
        self.enable_captcha_solver = enable_captcha_solver
        self.captcha_solver_headless = captcha_solver_headless
        self.enable_store_retry = enable_store_retry
        self.store_retry_batch_size = store_retry_batch_size
        self.store_retry_delay = store_retry_delay
        self.log_callback = log_callback
        self.proxy_config = self._get_proxy_config()

    def _get_proxy_config(self) -> dict[str, str] | None:
        """Get proxy configuration for captcha solver"""
        if self.proxy_provider == "oxylabs":
            if OXYLABS_USERNAME and OXYLABS_PASSWORD:
                return {
                    "server": f"http://{OXYLABS_ENDPOINT}",
                    "username": OXYLABS_USERNAME,
                    "password": OXYLABS_PASSWORD,
                }
        elif self.proxy_provider == "massive":
            # Add massive proxy config when implemented
            pass
        return None

    async def initialize_session_with_captcha_solving(
        self, keyword: str
    ) -> tuple[dict[str, Any], str]:
        """
        Initialize session with automatic captcha solving if needed

        Args:
            keyword: Search keyword for building URL

        Returns:
            Tuple of (cookies, user_agent)
        """
        self.log_callback(f"🔧 Initializing enhanced session for keyword: '{keyword}'")

        # Validate proxy credentials if needed
        if self.proxy_provider:
            self.log_callback(f"🌐 Using proxy provider: {self.proxy_provider}")
            validate_proxy_credentials(self.proxy_provider)

        # Check cache first
        cached_data = self._check_cache()
        if cached_data:
            self.log_callback("💾 Using cached session data")
            return cached_data["cookies"], cached_data["user_agent"]

        # If captcha solver is disabled, fall back to original method
        if not self.enable_captcha_solver:
            self.log_callback(
                "⚠️  Captcha solver disabled - using standard session initialization"
            )
            return initialize_session_data(
                keyword, self.proxy_provider, self.log_callback
            )

        # Use captcha solver for session initialization
        search_url = f"https://www.aliexpress.us/w/wholesale-{quote_plus(keyword)}.html"
        self.log_callback(f"🔗 Target URL: {search_url}")

        try:
            self.log_callback("🛡️  Starting captcha-aware session initialization...")

            (
                success,
                session_data,
            ) = await CaptchaSolverIntegration.solve_captcha_and_get_session(
                url=search_url,
                proxy_config=self.proxy_config,
                headless=self.captcha_solver_headless,
                max_attempts=5,
            )

            if success and session_data:
                cookies = session_data.get("cookies", {})
                user_agent = session_data.get("user_agent", "")

                # Cache the session data
                self._cache_session_data(cookies, user_agent)

                self.log_callback(
                    f"✅ Session initialized successfully via captcha solver"
                )
                self.log_callback(f"📊 Retrieved {len(cookies)} cookies from session")

                return cookies, user_agent
            else:
                self.log_callback(
                    "⚠️  Captcha solver failed - falling back to standard method"
                )
                return initialize_session_data(
                    keyword, self.proxy_provider, self.log_callback
                )

        except Exception as e:
            self.log_callback(f"❌ Captcha solver initialization error: {str(e)}")
            self.log_callback("🔄 Falling back to standard session initialization")
            return initialize_session_data(
                keyword, self.proxy_provider, self.log_callback
            )

    def _check_cache(self) -> dict[str, Any] | None:
        """Check for valid cached session data"""
        if not os.path.exists(SESSION_CACHE_FILE):
            self.log_callback("📁 No session cache file found")
            return None

        try:
            with open(SESSION_CACHE_FILE, "r") as f:
                cached_data = json.load(f)

            saved_timestamp = cached_data.get("timestamp", 0)
            current_timestamp = time.time()
            cache_age = current_timestamp - saved_timestamp

            if cache_age < CACHE_EXPIRATION_SECONDS:
                self.log_callback(
                    f"✅ Using cached session data (age: {int(cache_age)}s)"
                )
                return cached_data
            else:
                self.log_callback(
                    f"⏰ Session cache expired (age: {int(cache_age)}s, max: {CACHE_EXPIRATION_SECONDS}s)"
                )

        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            self.log_callback(f"⚠️  Error reading session cache: {e}")

        return None

    def _cache_session_data(self, cookies: dict[str, Any], user_agent: str) -> None:
        """Cache session data"""
        try:
            cache_content: dict[str, Any] = {
                "timestamp": time.time(),
                "cookies": cookies,
                "user_agent": user_agent,
            }

            with open(SESSION_CACHE_FILE, "w") as f:
                json.dump(cache_content, f, indent=4)

            self.log_callback(
                f"💾 Session data cached successfully ({len(cookies)} cookies)"
            )

        except IOError as e:
            self.log_callback(f"⚠️  Failed to save session cache: {e}")

    async def scrape_with_captcha_handling(
        self,
        keyword: str,
        brand: str,
        max_pages: int = 1,
        apply_discount_filter: bool = False,
        apply_free_shipping_filter: bool = False,
        min_price: float | None = None,
        max_price: float | None = None,
        delay: float = 1.0,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Scrape with automatic captcha handling and retry logic

        Args:
            keyword: Search keyword
            brand: Brand name to associate with products
            max_pages: Maximum pages to scrape
            apply_discount_filter: Apply discount filter
            apply_free_shipping_filter: Apply free shipping filter
            min_price: Minimum price filter
            max_price: Maximum price filter
            delay: Delay between requests
            max_retries: Maximum retry attempts if captcha encountered

        Returns:
            Scraping results dictionary
        """
        attempt = 0

        while attempt < max_retries:
            try:
                self.log_callback(
                    f"🚀 Starting scrape attempt {attempt + 1}/{max_retries} for keyword: '{keyword}'"
                )

                # Get session data (with captcha solving if needed)
                (
                    cookies,
                    user_agent,
                ) = await self.initialize_session_with_captcha_solving(keyword)

                self.log_callback(f"🔍 Scraping {max_pages} page(s) for products...")

                # Perform the actual scraping
                raw_products, session = scrape_aliexpress_data(
                    keyword=keyword,
                    max_pages=max_pages,
                    cookies=cookies,
                    user_agent=user_agent,
                    proxy_provider=self.proxy_provider,
                    apply_discount_filter=apply_discount_filter,
                    apply_free_shipping_filter=apply_free_shipping_filter,
                    min_price=min_price,
                    max_price=max_price,
                    delay=delay,
                    log_callback=self.log_callback,
                )

                self.log_callback(
                    f"📦 Retrieved {len(raw_products)} raw products from API"
                )

                # Use the original scraper's detailed extraction function
                from ..core.scraper import extract_product_details

                # Define all available fields that can be extracted
                all_fields = [
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
                ]

                self.log_callback("🏗️  Extracting detailed product information...")

                # Extract detailed product information with store data
                extracted_products = extract_product_details(
                    raw_products=raw_products,
                    selected_fields=all_fields,
                    brand=brand,  # Use the provided brand parameter
                    proxy_provider=self.proxy_provider,
                    session=session,
                    fetch_store_info=True,  # Enable store info fetching
                    log_callback=self.log_callback,
                )

                self.log_callback(
                    f"✅ Extracted {len(extracted_products)} detailed products"
                )

                # Format results to match expected structure
                # Don't include session object in results as it's not JSON serializable
                results: dict[str, Any] = {
                    "products": extracted_products,
                    "keyword": keyword,
                    "total_pages": max_pages,
                    "scraping_method": "enhanced_with_captcha_solver",
                }

                # Check if we got valid results
                if self._validate_results(results):
                    self.log_callback(
                        f"✅ Scraping completed successfully on attempt {attempt + 1}"
                    )
                    return results
                else:
                    self.log_callback(
                        f"⚠️  Invalid results on attempt {attempt + 1} - retrying..."
                    )

            except Exception as e:
                self.log_callback(f"❌ Scraping attempt {attempt + 1} failed: {str(e)}")

            attempt += 1

            if attempt < max_retries:
                self.log_callback(
                    f"⏳ Retrying in 5 seconds... (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(5)

        self.log_callback(
            f"❌ All scraping attempts failed after {max_retries} retries"
        )
        return {
            "error": f"Scraping failed after {max_retries} attempts",
            "products": [],
        }

    def _validate_results(self, results: dict[str, Any]) -> bool:
        """Validate scraping results"""
        products = results.get("products", [])

        # Check if we have products and they look valid
        if not products or len(products) == 0:
            self.log_callback("⚠️  No products found in results")
            return False

        # Check if products have essential fields
        valid_count = 0
        for product in products[:3]:  # Check first 3 products
            if not isinstance(product, dict):
                continue
            product_dict = cast(dict[str, Any], product)
            if product_dict.get("Title") or product_dict.get("title"):
                valid_count += 1

        if valid_count == 0:
            self.log_callback("⚠️  No valid products found (missing titles)")
            return False

        self.log_callback(f"✅ Results validation passed ({len(products)} products)")
        return True

    async def run_enhanced_scraper(
        self,
        keyword: str,
        brand: str,
        max_pages: int = 1,
        save_to_file: bool = True,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Run the enhanced scraper with detailed product extraction and optional file saving

        Args:
            keyword: Search keyword
            brand: Brand name to associate with products
            max_pages: Maximum pages to scrape
            save_to_file: Whether to save results to JSON file
            **kwargs: Additional arguments for scrape_with_captcha_handling

        Returns:
            Scraping results dictionary
        """
        self.log_callback(f"🚀 Starting enhanced scraper for keyword: '{keyword}'")
        self.log_callback(
            f"📊 Configuration: {max_pages} pages, streaming: {stream}, save: {save_to_file}"
        )

        # Common fields for extraction/saving
        all_fields = [
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
        ]

        if stream:
            self.log_callback("🌊 Starting streaming mode scraper...")
            # Streaming mode: produce a JSON array incrementally + CSV row-by-row
            from ..core.scraper import RESULTS_DIR, extract_product_details

            # Safe path helper (backup existing files)
            def ensure_safe_path(path: str) -> str:
                if not os.path.exists(path):
                    return path
                base, ext = os.path.splitext(path)
                n = 1
                while True:
                    candidate = f"{base}.bak{n}{ext}"
                    if not os.path.exists(candidate):
                        try:
                            os.rename(path, candidate)
                        except Exception:
                            pass
                        return path
                    n += 1

            # Stable file names (no timestamps) per keyword + date
            # For streaming mode, use keyword to avoid overwriting between queries
            keyword_safe = (
                "".join(c.lower() if c.isalnum() else "_" for c in keyword)
                if keyword
                else "unknown"
            )
            date_str = datetime.datetime.now().strftime("%Y%m%d")
            os.makedirs(RESULTS_DIR, exist_ok=True)
            json_path = os.path.join(
                RESULTS_DIR, f"aliexpress_{keyword_safe}_{date_str}.json"
            )
            csv_path = os.path.join(
                RESULTS_DIR, f"aliexpress_{keyword_safe}_{date_str}.csv"
            )
            json_path = ensure_safe_path(json_path)
            csv_path = ensure_safe_path(csv_path)

            self.log_callback(
                f"📁 Output files: JSON={os.path.basename(json_path)}, CSV={os.path.basename(csv_path)}"
            )

            # Initialize session (captcha-aware)
            self.log_callback("🔧 Initializing session for streaming...")
            cookies, user_agent = await self.initialize_session_with_captcha_solving(
                keyword
            )

            total_written = 0
            first_row = True

            # We write '[' then objects separated by commas, then ']' at end
            self.log_callback("📝 Starting streaming data write...")
            with (
                open(json_path, "w", encoding="utf-8") as jf,
                open(csv_path, "w", encoding="utf-8", newline="") as cf,
            ):
                jf.write("[\n")
                csv_writer = csv.DictWriter(
                    cf, fieldnames=all_fields, extrasaction="ignore"
                )
                csv_writer.writeheader()

                def on_page(page_num: int, items: list[dict[str, Any]]) -> None:
                    nonlocal total_written, first_row
                    if not items:
                        self.log_callback(f"📄 Page {page_num}: No items found")
                        return

                    self.log_callback(
                        f"📄 Page {page_num}: Processing {len(items)} items..."
                    )
                    extracted = extract_product_details(
                        items,
                        all_fields,
                        brand,
                        self.proxy_provider,
                        session=None,
                        fetch_store_info=False,  # Avoid extra requests while streaming
                        log_callback=self.log_callback,
                    )
                    for row in extracted:
                        # JSON array punctuation management
                        if not first_row:
                            jf.write(",\n")
                        jf.write(json.dumps(row, ensure_ascii=False))
                        first_row = False
                        csv_writer.writerow(row)
                        total_written += 1
                    cf.flush()
                    jf.flush()
                    self.log_callback(
                        f"📄 Page {page_num}: Wrote {len(extracted)} products to files"
                    )

                # Run underlying scrape in executor (keeps event loop free)
                self.log_callback("⚡ Starting parallel page fetching...")
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: scrape_aliexpress_data(
                        keyword=keyword,
                        max_pages=max_pages,
                        cookies=cookies,
                        user_agent=user_agent,
                        proxy_provider=self.proxy_provider,
                        apply_discount_filter=kwargs.get(
                            "apply_discount_filter", False
                        ),
                        apply_free_shipping_filter=kwargs.get(
                            "apply_free_shipping_filter", False
                        ),
                        min_price=kwargs.get("min_price"),
                        max_price=kwargs.get("max_price"),
                        delay=kwargs.get("delay", 1.0),
                        log_callback=self.log_callback,
                        on_page=on_page,
                    ),
                )

                # Close JSON array
                jf.write("\n]\n")

            self.log_callback(
                f"✅ Streaming completed: {total_written} products written to files"
            )
            return {
                "products": [],  # Not held in memory
                "json_file": json_path,
                "csv_file": csv_path,
                "total_streamed": total_written,
                "stream": True,
            }

        # Non-streaming: run regular enhanced flow and save if requested
        self.log_callback("🔄 Starting standard (non-streaming) scraping mode...")
        results = await self.scrape_with_captcha_handling(
            keyword=keyword, brand=brand, max_pages=max_pages, **kwargs
        )

        if results.get("error"):
            self.log_callback(f"❌ Scraping failed: {results['error']}")
            return results

        products = results.get("products", [])
        self.log_callback(f"📦 Retrieved {len(products)} products for processing")

        if save_to_file and products:
            self.log_callback("💾 Saving results to files...")
            from ..core.scraper import RESULTS_DIR, save_results

            os.makedirs(RESULTS_DIR, exist_ok=True)

            json_file, csv_file = save_results(
                keyword=keyword,
                data=products,
                selected_fields=all_fields,
                brand=brand,
                log_callback=self.log_callback,
            )

            results["json_file"] = json_file
            results["csv_file"] = csv_file

            if json_file:
                self.log_callback(f"📄 Saved JSON: {os.path.basename(json_file)}")
            if csv_file:
                self.log_callback(f"📄 Saved CSV: {os.path.basename(csv_file)}")

            if self.enable_store_retry and json_file:
                self.log_callback("🏪 Starting automatic store information retry...")
                await self._auto_retry_store_info(json_file, products)

        return results

    async def _auto_retry_store_info(
        self, json_file: str, products: list[dict[str, Any]]
    ) -> None:
        """
        Automatically retry missing store information and update the saved file.

        Args:
            json_file: Path to the saved JSON file
            products: List of scraped products
        """
        try:
            # Import the store retry functionality
            from ..store.store_integration import get_store_integration

            self.log_callback("🔍 Analyzing products for missing store information...")

            # Analyze products for missing store info
            missing_products: list[dict[str, Any]] = []
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
                self.log_callback(
                    "✅ All products already have complete store information"
                )
                return

            self.log_callback(
                f"🔄 Found {len(missing_products)} products needing store info retry"
            )

            # Extract URLs for retry with explicit typing
            urls_to_retry: list[str] = [
                p["Product URL"] for p in missing_products if p.get("Product URL")
            ]

            if not urls_to_retry:
                self.log_callback("⚠️  No valid product URLs found for retry")
                return

            self.log_callback(
                f"🏪 Retrying store info for {len(urls_to_retry)} products..."
            )

            # Get store integration and retry
            integration = get_store_integration(proxy_provider=self.proxy_provider)

            # Process in batches
            all_retry_results: dict[str, Any] = {}
            total_batches = (
                len(urls_to_retry) + self.store_retry_batch_size - 1
            ) // self.store_retry_batch_size

            for i in range(0, len(urls_to_retry), self.store_retry_batch_size):
                batch_num = (i // self.store_retry_batch_size) + 1
                batch_urls: list[str] = urls_to_retry[
                    i : i + self.store_retry_batch_size
                ]

                self.log_callback(
                    f"📦 Processing batch {batch_num}/{total_batches} ({len(batch_urls)} URLs)..."
                )

                try:
                    batch_results = await integration.fetch_store_info_enhanced(
                        batch_urls
                    )
                    all_retry_results.update(batch_results)
                    self.log_callback(f"✅ Batch {batch_num} completed successfully")

                except Exception as e:
                    self.log_callback(f"⚠️  Batch {batch_num} failed: {str(e)}")

                # Delay between batches
                if (
                    i + self.store_retry_batch_size < len(urls_to_retry)
                    and self.store_retry_delay > 0
                ):
                    self.log_callback(
                        f"⏳ Waiting {self.store_retry_delay}s before next batch..."
                    )
                    await asyncio.sleep(self.store_retry_delay)

            # Update products with retry results
            self.log_callback("🔄 Updating products with retry results...")
            updated_products: list[dict[str, Any]] = []
            successful_updates = 0

            for product in products:
                product_url = product.get("Product URL")

                if product_url in all_retry_results:
                    store_info: dict[str, Any] = all_retry_results[product_url]

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
                        # Add retry metadata
                        updated_product["_auto_retry_info"] = {
                            "retry_successful": True,
                            "retry_timestamp": time.time(),
                            "retrieved_store_name": store_info.get("store_name"),
                        }

                    updated_products.append(updated_product)
                else:
                    updated_products.append(product)

            # Save updated results if there were successful updates
            if successful_updates > 0:
                self.log_callback(
                    f"💾 Updating files with {successful_updates} enhanced products..."
                )
                # Update the JSON file with new data
                import json

                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(updated_products, f, indent=2, ensure_ascii=False)

                # Also update CSV if we have it
                csv_file = json_file.replace(".json", ".csv")
                if csv_file != json_file:  # Make sure we actually have a CSV path
                    try:
                        import pandas as pd

                        df = pd.DataFrame(updated_products)
                        df.to_csv(csv_file, index=False)
                        self.log_callback(
                            "✅ Both JSON and CSV files updated successfully"
                        )
                    except ImportError:
                        self.log_callback(
                            "⚠️  CSV update skipped (pandas not available)"
                        )
                    except Exception:
                        self.log_callback("⚠️  CSV update failed")
                else:
                    self.log_callback("✅ JSON file updated successfully")
            else:
                self.log_callback(
                    "ℹ️  No store information could be retrieved for any products"
                )

        except ImportError:
            self.log_callback(
                "⚠️  Store integration not available - skipping auto-retry"
            )
        except Exception as e:
            self.log_callback(f"⚠️  Auto-retry failed: {str(e)}")

    async def solve_captcha_for_product_details(
        self, product_urls: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Solve captchas for product detail pages and extract session data

        Args:
            product_urls: List of product URLs to process

        Returns:
            Dictionary mapping URLs to session data
        """
        if not self.enable_captcha_solver:
            self.log_callback(
                "⚠️  Captcha solver disabled - skipping product detail processing"
            )
            return {}

        self.log_callback(
            f"🛡️  Processing {len(product_urls)} product URLs for captcha solving..."
        )

        results: dict[str, dict[str, Any]] = {}

        async with CaptchaSolverContext(
            headless=self.captcha_solver_headless, proxy_config=self.proxy_config
        ) as solver:
            for i, url in enumerate(product_urls, 1):
                try:
                    self.log_callback(
                        f"🔍 Processing product {i}/{len(product_urls)}: {url[:50]}..."
                    )

                    success, session_data = await solver.solve_captcha_on_url(
                        url, max_attempts=3
                    )

                    if success:
                        results[url] = session_data
                        self.log_callback(f"✅ Product {i} captcha solved successfully")
                    else:
                        self.log_callback(f"⚠️  Product {i} captcha solving failed")

                    # Small delay between products
                    if i < len(product_urls):
                        await asyncio.sleep(2)

                except Exception as e:
                    self.log_callback(f"❌ Error processing product {i}: {str(e)}")

        success_rate = (len(results) / len(product_urls) * 100) if product_urls else 0
        self.log_callback(
            f"📊 Captcha solving completed: {len(results)}/{len(product_urls)} successful ({success_rate:.1f}%)"
        )
        return results


# Convenience functions for backwards compatibility and easy usage
async def enhanced_scrape_aliexpress(
    keyword: str,
    brand: str,
    max_pages: int = 1,
    proxy_provider: str = "",
    enable_captcha_solver: bool = True,
    captcha_solver_headless: bool = True,
    apply_discount_filter: bool = False,
    apply_free_shipping_filter: bool = False,
    min_price: float | None = None,
    max_price: float | None = None,
    delay: float = 1.0,
    max_retries: int = 3,
    log_callback: Callable[[str], None] = default_logger,
) -> dict[str, Any]:
    """
    Enhanced scraping function with captcha solving

    This is a convenience function that creates an EnhancedAliExpressScraper
    and performs the scraping with all the enhanced features.
    """
    scraper = EnhancedAliExpressScraper(
        proxy_provider=proxy_provider,
        enable_captcha_solver=enable_captcha_solver,
        captcha_solver_headless=captcha_solver_headless,
        log_callback=log_callback,
    )

    return await scraper.scrape_with_captcha_handling(
        keyword=keyword,
        brand=brand,
        max_pages=max_pages,
        apply_discount_filter=apply_discount_filter,
        apply_free_shipping_filter=apply_free_shipping_filter,
        min_price=min_price,
        max_price=max_price,
        delay=delay,
        max_retries=max_retries,
    )


async def solve_captcha_for_urls(
    urls: list[str],
    proxy_provider: str = "",
    headless: bool = True,
    log_callback: Callable[[str], None] = default_logger,
) -> dict[str, dict[str, Any]]:
    """
    Solve captchas for a list of URLs and return session data

    Args:
        urls: List of URLs to process
        proxy_provider: Proxy provider to use
        headless: Whether to run browser in headless mode
        log_callback: Logging function

    Returns:
        Dictionary mapping URLs to session data
    """
    scraper = EnhancedAliExpressScraper(
        proxy_provider=proxy_provider,
        enable_captcha_solver=True,
        captcha_solver_headless=headless,
        log_callback=log_callback,
    )

    return await scraper.solve_captcha_for_product_details(urls)


if __name__ == "__main__":

    async def main():
        parser = argparse.ArgumentParser(
            description="Enhanced AliExpress Scraper with Captcha Solving"
        )
        parser.add_argument("--keyword", "-k", required=True, help="Search keyword")
        parser.add_argument(
            "--brand", "-b", required=True, help="Brand name to associate with products"
        )
        parser.add_argument(
            "--max-pages", type=int, default=1, help="Maximum pages to scrape"
        )
        parser.add_argument(
            "--proxy-provider",
            choices=["", "oxylabs", "massive"],
            default="",
            help="Proxy provider to use",
        )
        parser.add_argument(
            "--disable-captcha-solver",
            action="store_true",
            help="Disable automatic captcha solving",
        )
        parser.add_argument(
            "--captcha-solver-visible",
            action="store_true",
            help="Run captcha solver in visible mode (not headless)",
        )
        parser.add_argument(
            "--discount-filter", action="store_true", help="Apply discount filter"
        )
        parser.add_argument(
            "--free-shipping-filter",
            action="store_true",
            help="Apply free shipping filter",
        )
        parser.add_argument("--min-price", type=float, help="Minimum price filter")
        parser.add_argument("--max-price", type=float, help="Maximum price filter")
        parser.add_argument(
            "--delay", type=float, default=1.0, help="Delay between requests"
        )
        parser.add_argument(
            "--max-retries", type=int, default=3, help="Maximum retry attempts"
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

        args = parser.parse_args()

        print("🚀 Enhanced AliExpress Scraper with Captcha Solving")
        print("=" * 60)
        print(f"🔍 Keyword: {args.keyword}")
        print(f"🏷️  Brand: {args.brand}")
        print(f"📄 Max pages: {args.max_pages}")
        print(f"🌐 Proxy: {args.proxy_provider if args.proxy_provider else 'None'}")
        print(
            f"🛡️  Captcha solver: {'Enabled' if not args.disable_captcha_solver else 'Disabled'}"
        )
        print(f"🏪 Store retry: {'Enabled' if args.enable_store_retry else 'Disabled'}")
        print("-" * 60)

        # Create scraper instance
        scraper = EnhancedAliExpressScraper(
            proxy_provider=args.proxy_provider,
            enable_captcha_solver=not args.disable_captcha_solver,
            captcha_solver_headless=not args.captcha_solver_visible,
            enable_store_retry=args.enable_store_retry,
            store_retry_batch_size=args.store_retry_batch_size,
            store_retry_delay=args.store_retry_delay,
        )

        # Run enhanced scraper with detailed extraction and automatic saving
        results = await scraper.run_enhanced_scraper(
            keyword=args.keyword,
            brand=args.brand,
            max_pages=args.max_pages,
            save_to_file=True,
            apply_discount_filter=args.discount_filter,
            apply_free_shipping_filter=args.free_shipping_filter,
            min_price=args.min_price,
            max_price=args.max_price,
            delay=args.delay,
            max_retries=args.max_retries,
        )

        if "error" not in results:
            products = results.get("products", [])
            total_products = (
                len(products)
                if not results.get("stream")
                else results.get("total_streamed", 0)
            )

            print(f"\n✅ Enhanced scraping completed successfully!")
            print(f"📊 Total products scraped: {total_products}")

            # Print file paths if saved
            if results.get("json_file"):
                print(f"� JSON file: {os.path.basename(results['json_file'])}")
            if results.get("csv_file"):
                print(f"📄 CSV file: {os.path.basename(results['csv_file'])}")

            if results.get("stream"):
                print("🌊 Results were streamed directly to files")

        else:
            print(f"\n❌ Enhanced scraping failed: {results['error']}")

    # Run the async main function
    asyncio.run(main())
