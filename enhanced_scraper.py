#!/usr/bin/env python3
"""
Enhanced AliExpress Scraper with Captcha Solver Integration
Extends the original scraper with automatic captcha solving capabilities
"""

import argparse
import asyncio
import json
import os
import time
from typing import Any, Callable, Dict, Optional, Tuple, cast
from urllib.parse import quote_plus

from captcha_solver import CaptchaSolverContext, CaptchaSolverIntegration
from scraper import (
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


class EnhancedAliExpressScraper:
    """Enhanced scraper with captcha solving capabilities"""

    def __init__(
        self,
        proxy_provider: str = "",
        enable_captcha_solver: bool = True,
        captcha_solver_headless: bool = True,
        log_callback: Callable[[str], None] = default_logger,
    ):
        """
        Initialize enhanced scraper

        Args:
            proxy_provider: Proxy provider ("oxylabs", "massive", or "" for none)
            enable_captcha_solver: Whether to enable automatic captcha solving
            captcha_solver_headless: Whether to run captcha solver in headless mode
            log_callback: Logging function
        """
        self.proxy_provider = proxy_provider
        self.enable_captcha_solver = enable_captcha_solver
        self.captcha_solver_headless = captcha_solver_headless
        self.log_callback = log_callback
        self.proxy_config = self._get_proxy_config()

    def _get_proxy_config(self) -> Optional[Dict[str, str]]:
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
    ) -> Tuple[Dict[str, Any], str]:
        """
        Initialize session with automatic captcha solving if needed

        Args:
            keyword: Search keyword for building URL

        Returns:
            Tuple of (cookies, user_agent)
        """
        self.log_callback(f"Initializing enhanced session for: '{keyword}'")

        # Validate proxy credentials if needed
        if self.proxy_provider:
            validate_proxy_credentials(self.proxy_provider)

        # Check cache first
        cached_data = self._check_cache()
        if cached_data:
            return cached_data["cookies"], cached_data["user_agent"]

        # If captcha solver is disabled, fall back to original method
        if not self.enable_captcha_solver:
            self.log_callback(
                "Captcha solver disabled, using original session initialization"
            )
            return initialize_session_data(
                keyword, self.proxy_provider, self.log_callback
            )

        # Use captcha solver for session initialization
        search_url = (
            f"https://www.aliexpress.com/w/wholesale-{quote_plus(keyword)}.html"
        )

        try:
            self.log_callback(
                "🛡️ Starting session initialization with captcha solver..."
            )

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
                    f"✅ Captcha solver session initialized successfully!"
                )
                self.log_callback(f"📊 Extracted {len(cookies)} cookies")

                return cookies, user_agent
            else:
                self.log_callback(
                    "⚠️ Captcha solver failed, falling back to original method"
                )
                return initialize_session_data(
                    keyword, self.proxy_provider, self.log_callback
                )

        except Exception as e:
            self.log_callback(
                f"❌ Error in captcha solver session initialization: {str(e)}"
            )
            self.log_callback("🔄 Falling back to original session initialization")
            return initialize_session_data(
                keyword, self.proxy_provider, self.log_callback
            )

    def _check_cache(self) -> Optional[Dict[str, Any]]:
        """Check for valid cached session data"""
        if not os.path.exists(SESSION_CACHE_FILE):
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
                    f"⏰ Cached session data expired (age: {int(cache_age)}s)"
                )

        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            self.log_callback(f"⚠️ Error reading cache: {e}")

        return None

    def _cache_session_data(self, cookies: Dict[str, Any], user_agent: str) -> None:
        """Cache session data"""
        try:
            cache_content: Dict[str, Any] = {
                "timestamp": time.time(),
                "cookies": cookies,
                "user_agent": user_agent,
            }

            with open(SESSION_CACHE_FILE, "w") as f:
                json.dump(cache_content, f, indent=4)

            self.log_callback("💾 Session data cached successfully")

        except IOError as e:
            self.log_callback(f"⚠️ Error saving session cache: {e}")

    async def scrape_with_captcha_handling(
        self,
        keyword: str,
        brand: str,
        max_pages: int = 1,
        apply_discount_filter: bool = False,
        apply_free_shipping_filter: bool = False,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        delay: float = 1.0,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
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
                    f"🚀 Starting scrape attempt {attempt + 1}/{max_retries}"
                )

                # Get session data (with captcha solving if needed)
                (
                    cookies,
                    user_agent,
                ) = await self.initialize_session_with_captcha_solving(keyword)

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

                # Use the original scraper's detailed extraction function
                from scraper import extract_product_details

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

                # Extract detailed product information with store data
                extracted_products = extract_product_details(
                    raw_products=raw_products,
                    selected_fields=all_fields,
                    brand=brand,  # Use the provided brand parameter
                    proxy_provider=self.proxy_provider,
                    session=session,
                    fetch_store_info=True,  # Enable store info fetching
                    log_callback=lambda msg: self.log_callback(f"🔍 {msg}"),
                )

                # Format results to match expected structure
                # Don't include session object in results as it's not JSON serializable
                results: Dict[str, Any] = {
                    "products": extracted_products,
                    "keyword": keyword,
                    "total_pages": max_pages,
                    "scraping_method": "enhanced_with_captcha_solver",
                }

                # Check if we got valid results
                if self._validate_results(results):
                    self.log_callback(
                        f"✅ Scraping successful on attempt {attempt + 1}"
                    )
                    return results
                else:
                    self.log_callback(
                        f"⚠️ Invalid results on attempt {attempt + 1}, retrying..."
                    )

            except Exception as e:
                self.log_callback(f"❌ Error on attempt {attempt + 1}: {str(e)}")

            attempt += 1

            if attempt < max_retries:
                self.log_callback(
                    f"🔄 Retrying in 5 seconds... (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(5)

        self.log_callback(f"❌ Scraping failed after {max_retries} attempts")
        return {
            "error": f"Scraping failed after {max_retries} attempts",
            "products": [],
        }

    def _validate_results(self, results: Dict[str, Any]) -> bool:
        """Validate scraping results"""
        products = results.get("products", [])

        # Check if we have products and they look valid
        if not products or len(products) == 0:
            return False

        # Check if products have essential fields
        for product in products[:3]:  # Check first 3 products
            if not isinstance(product, dict):
                return False
            product_dict = cast(Dict[str, Any], product)
            if not product_dict.get("Title") and not product_dict.get("title"):
                return False

        return True

    async def run_enhanced_scraper(
        self,
        keyword: str,
        brand: str,
        max_pages: int = 1,
        save_to_file: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
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

        # Run the scraping with captcha handling
        results = await self.scrape_with_captcha_handling(
            keyword=keyword, brand=brand, max_pages=max_pages, **kwargs
        )

        if results.get("error"):
            return results

        products = results.get("products", [])

        if save_to_file and products:
            # Save results using the original scraper's save function
            import os

            from scraper import RESULTS_DIR, save_results

            # Ensure results directory exists
            os.makedirs(RESULTS_DIR, exist_ok=True)

            # Define all available fields for saving
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

            json_file, csv_file = save_results(
                keyword=keyword,
                data=products,
                selected_fields=all_fields,
                log_callback=self.log_callback,
            )

            if json_file:
                self.log_callback(f"📄 Results saved to: {json_file}")
            if csv_file:
                self.log_callback(f"📊 Results saved to: {csv_file}")

            # Add file paths to results
            results["json_file"] = json_file
            results["csv_file"] = csv_file

        return results

    async def solve_captcha_for_product_details(
        self, product_urls: list[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Solve captchas for product detail pages and extract session data

        Args:
            product_urls: List of product URLs to process

        Returns:
            Dictionary mapping URLs to session data
        """
        if not self.enable_captcha_solver:
            self.log_callback("Captcha solver disabled for product details")
            return {}

        self.log_callback(
            f"🛡️ Processing {len(product_urls)} product URLs for captcha solving..."
        )

        results: Dict[str, Dict[str, Any]] = {}

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
                        self.log_callback(f"✅ Product {i} processed successfully")
                    else:
                        self.log_callback(f"⚠️ Failed to process product {i}")

                    # Small delay between products
                    if i < len(product_urls):
                        await asyncio.sleep(2)

                except Exception as e:
                    self.log_callback(f"❌ Error processing product {i}: {str(e)}")

        self.log_callback(
            f"📊 Successfully processed {len(results)}/{len(product_urls)} product URLs"
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
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    delay: float = 1.0,
    max_retries: int = 3,
    log_callback: Callable[[str], None] = default_logger,
) -> Dict[str, Any]:
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
) -> Dict[str, Dict[str, Any]]:
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
        parser.add_argument(
            "--keyword", "-k", required=True, help="Search keyword"
        )
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

        args = parser.parse_args()

        print("🚀 Enhanced AliExpress Scraper with Captcha Solving")
        print("=" * 60)

        # Create scraper instance
        scraper = EnhancedAliExpressScraper(
            proxy_provider=args.proxy_provider,
            enable_captcha_solver=not args.disable_captcha_solver,
            captcha_solver_headless=not args.captcha_solver_visible,
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
            print(
                f"\n✅ Successfully scraped {len(products)} products with detailed information!"
            )

            # Print file paths if saved
            if results.get("json_file"):
                print(f"📄 JSON saved to: {results['json_file']}")
            if results.get("csv_file"):
                print(f"📄 CSV saved to: {results['csv_file']}")

            # Print first few products with detailed fields
            for i, product in enumerate(products[:3], 1):
                title = product.get("Title", "No title")
                price = product.get("Sale Price", "No price")
                store = product.get("Store Name", "Unknown store")
                rating = product.get("Rating", "No rating")
                orders = product.get("Orders Count", "No orders data")

                print(f"\n{i}. {title[:60]}...")
                print(f"   💰 Price: {price}")
                print(f"   🏪 Store: {store}")
                print(f"   ⭐ Rating: {rating} | 📦 Orders: {orders}")

        else:
            print(f"\n❌ Scraping failed: {results['error']}")

    # Run the async main function
    asyncio.run(main())
