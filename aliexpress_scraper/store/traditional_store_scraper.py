#!/usr/bin/env python3
"""
Traditional Playwright Store Scraper Implementation
==================================================

This module implements the StoreScraperInterface using traditional Playwright
for environments where MCP Playwright is not available.
"""

import asyncio
import logging
from typing import Any, cast

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from .scraper_interface import (
    StoreInfo,
    StoreScraperInterface,
    StoreScrapingMethod,
    register_store_scraper,
)

logger = logging.getLogger(__name__)


@register_store_scraper(StoreScrapingMethod.TRADITIONAL_PLAYWRIGHT)
class TraditionalPlaywrightStoreScraper(StoreScraperInterface):
    """
    Store scraper implementation using traditional Playwright

    This implementation uses the standard Playwright library and can be used
    in any Python environment where Playwright is installed.
    """

    def __init__(
        self,
        use_oxylabs_proxy: bool = False,
        headless: bool = True,
        extraction_timeout: int = 10,
        navigation_timeout: int = 30,
        retry_attempts: int = 3,
        optimize_bandwidth: bool = True,
        track_bandwidth_savings: bool = False,
        enable_css: bool = False,
        **kwargs: Any,
    ):
        """
        Initialize Traditional Playwright store scraper

        Args:
            use_oxylabs_proxy: Whether to use Oxylabs proxy configuration
            headless: Whether to run browser in headless mode
            extraction_timeout: Timeout for store data extraction (seconds)
            navigation_timeout: Timeout for page navigation (seconds)
            retry_attempts: Number of retry attempts for failed extractions
            optimize_bandwidth: Whether to enable bandwidth optimization (block CSS, images, etc.)
            track_bandwidth_savings: Whether to track and log bandwidth savings statistics
            enable_css: Whether to allow CSS stylesheets to load (useful for visual inspection)
            **kwargs: Additional configuration options
        """
        self.use_oxylabs_proxy = use_oxylabs_proxy
        self.headless = headless
        self.extraction_timeout = extraction_timeout
        self.navigation_timeout = navigation_timeout
        self.retry_attempts = retry_attempts
        self.optimize_bandwidth = optimize_bandwidth
        self.track_bandwidth_savings = track_bandwidth_savings
        self.enable_css = enable_css
        self.config = kwargs

        # Manual wait configuration
        self.manual_wait = kwargs.get("manual_wait", False)
        self.browser_wait_seconds = kwargs.get("browser_wait_seconds", 3)

        # Browser instances for reuse
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

        # Bandwidth tracking
        self._total_requests = 0
        self._blocked_requests = 0

    @property
    def method_name(self) -> StoreScrapingMethod:
        """Get the scraping method name"""
        return StoreScrapingMethod.TRADITIONAL_PLAYWRIGHT

    @property
    def supports_batch_processing(self) -> bool:
        """Traditional Playwright supports efficient batch processing"""
        return True

    def get_scraper_info(self) -> dict[str, Any]:
        """Get scraper information"""
        scraper_info: dict[str, Any] = {
            "method": self.method_name.value,
            "description": "Traditional Playwright store scraper with bandwidth optimization",
            "supports_batch": self.supports_batch_processing,
            "proxy_enabled": self.use_oxylabs_proxy,
            "headless": self.headless,
            "extraction_timeout": self.extraction_timeout,
            "navigation_timeout": self.navigation_timeout,
            "retry_attempts": self.retry_attempts,
            "optimize_bandwidth": self.optimize_bandwidth,
            "track_bandwidth_savings": self.track_bandwidth_savings,
            "config": self.config,
        }

        # Add bandwidth savings statistics if tracking is enabled
        if self.track_bandwidth_savings and self._total_requests > 0:
            bandwidth_saved_percent = (
                self._blocked_requests / self._total_requests
            ) * 100
            scraper_info.update(
                {
                    "bandwidth_stats": {
                        "total_requests": self._total_requests,
                        "blocked_requests": self._blocked_requests,
                        "bandwidth_saved_percent": round(bandwidth_saved_percent, 1),
                    }
                }
            )

        return scraper_info

    async def _initialize_browser(self) -> None:
        """Initialize browser and context"""
        if self._browser and not self._browser.is_connected():
            await self._cleanup_browser()

        if not self._browser:
            self._playwright = await async_playwright().start()

            # Optimized browser arguments for store scraping with bandwidth optimization
            browser_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-blink-features=AutomationControlled",
                "--excludeSwitches=enable-automation",
                "--disable-web-security",  # Help with CORS issues
                "--disable-features=VizDisplayCompositor",
            ]

            self._browser = await self._playwright.chromium.launch(
                headless=self.headless, args=browser_args
            )

            # Configure context with proxy if needed
            context_options: dict[str, Any] = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                "java_script_enabled": True,
                "ignore_https_errors": True,
            }

            if self.use_oxylabs_proxy:
                # Configure Oxylabs proxy
                import os

                username = os.getenv("OXYLABS_USERNAME")
                password = os.getenv("OXYLABS_PASSWORD")
                endpoint = os.getenv("OXYLABS_ENDPOINT", "pr.oxylabs.io:7777")

                if username and password:
                    context_options["proxy"] = {
                        "server": f"http://{endpoint}",
                        "username": username,
                        "password": password,
                    }
                    logger.info(f"🌐 Configured Oxylabs proxy: {endpoint}")
                else:
                    logger.warning("⚠️ Oxylabs credentials not found in environment")

            self._context = await self._browser.new_context(**context_options)

            # Enhanced bandwidth optimization - block unnecessary resources (if enabled)
            if self.optimize_bandwidth:
                await self._context.route("**/*", self._handle_route)

    async def _handle_route(self, route: Any, request: Any) -> None:
        """
        Enhanced route handler for bandwidth optimization

        Blocks multiple resource types to reduce bandwidth usage:
        - CSS stylesheets (for faster loading, content still accessible)
        - Images (significant bandwidth savings)
        - Fonts (non-essential for data extraction)
        - Media files (audio/video)
        - WebSocket connections (not needed for scraping)
        - Third-party analytics and ads
        """
        # Track total requests if bandwidth tracking is enabled
        if self.track_bandwidth_savings:
            self._total_requests += 1

        # Skip blocking if bandwidth optimization is disabled
        if not self.optimize_bandwidth:
            await route.continue_()
            return

        # Resource types to block for bandwidth optimization (your approach)
        blocked_types = {"image", "font", "media", "websocket"}

        # Conditionally add stylesheet blocking (exclude if CSS is enabled)
        if not self.enable_css:
            blocked_types.add("stylesheet")

        # Additional patterns for analytics/ads (common third-party domains)
        blocked_patterns = [
            "googletagmanager.com",
            "google-analytics.com",
            "doubleclick.net",
            "facebook.com/tr",
            "adsystem.amazon.com",
            "googlesyndication.com",
            "scorecardresearch.com",
            "outbrain.com",
            "taboola.com",
            "mmstat.com",  # AliExpress analytics
        ]

        should_block = False

        # Check resource type (your approach - this is the core of your bandwidth optimization)
        if request.resource_type in blocked_types:
            should_block = True

        # Check URL patterns for analytics/ads
        elif any(pattern in request.url for pattern in blocked_patterns):
            should_block = True

        if should_block:
            if self.track_bandwidth_savings:
                self._blocked_requests += 1
            await route.abort()
            # Optional: log blocked resources in debug mode
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    f"🚫 BLOCKED [{request.resource_type}]: {request.url[:100]}..."
                )
        else:
            await route.continue_()

    def reset_bandwidth_tracking(self) -> None:
        """Reset bandwidth tracking counters"""
        self._total_requests = 0
        self._blocked_requests = 0

    def get_bandwidth_stats(self) -> dict[str, Any]:
        """Get current bandwidth usage statistics"""
        if self._total_requests == 0:
            return {
                "total_requests": 0,
                "blocked_requests": 0,
                "bandwidth_saved_percent": 0.0,
                "tracking_enabled": self.track_bandwidth_savings,
            }

        bandwidth_saved_percent = (self._blocked_requests / self._total_requests) * 100
        return {
            "total_requests": self._total_requests,
            "blocked_requests": self._blocked_requests,
            "bandwidth_saved_percent": round(bandwidth_saved_percent, 1),
            "tracking_enabled": self.track_bandwidth_savings,
        }

    async def _cleanup_browser(self) -> None:
        """Clean up browser resources"""
        # Log bandwidth stats before cleanup if tracking is enabled
        if self.track_bandwidth_savings and self._total_requests > 0:
            stats = self.get_bandwidth_stats()
            logger.info(
                f"📊 Bandwidth savings: {stats['blocked_requests']}/{stats['total_requests']} "
                f"requests blocked ({stats['bandwidth_saved_percent']}%)"
            )

        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self._initialize_browser()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit"""
        await self._cleanup_browser()

    async def scrape_single_store(self, product_url: str, **kwargs: Any) -> StoreInfo:
        """
        Scrape store information from a single product URL using traditional Playwright
        """
        logger.info(f"🔍 Scraping store info from: {product_url}")

        try:
            await self._initialize_browser()

            if not self._context:
                raise RuntimeError("Browser context not initialized")

            page = await self._context.new_page()

            try:
                # Navigate to the product page
                logger.debug(f"📡 Navigating to: {product_url}")
                await page.goto(
                    product_url,
                    timeout=self.navigation_timeout * 1000,
                    wait_until="domcontentloaded",
                )

                # Wait for page to be ready
                await page.wait_for_timeout(2000)

                # Extract store information using multiple methods
                store_info = await self._extract_store_info_with_fallback(
                    page, product_url
                )

                if store_info.is_valid:
                    logger.info(
                        f"✅ Successfully extracted store: {store_info.store_name}"
                    )
                else:
                    logger.warning(
                        f"⚠️ Failed to extract valid store info: {store_info.error}"
                    )

                # Print bandwidth stats for single scrape if tracking is enabled
                if self.track_bandwidth_savings:
                    stats = self.get_bandwidth_stats()
                    logger.info(
                        f"📊 Single scrape bandwidth: {stats['blocked_requests']}/{stats['total_requests']} "
                        f"requests blocked ({stats['bandwidth_saved_percent']}% savings)"
                    )

                # Manual wait for inspection if enabled and not headless
                if self.manual_wait and not self.headless:
                    logger.info(f"🛑 Manual wait mode activated for URL: {product_url}")
                    if store_info.is_valid:
                        print(
                            f"   🛑 Manual wait mode - browser will stay open for inspection"
                        )
                        print(
                            f"   ✅ Store extraction successful: {store_info.store_name}"
                        )
                        print(f"   💡 You can verify the extracted store information")
                        print(f"   ⏸️  Press Ctrl+C when ready to close browser...")
                    else:
                        print(
                            f"   🛑 Manual wait mode - browser will stay open for inspection"
                        )
                        print(f"   ❌ Store extraction failed - you can now:")
                        print(f"      - Solve any captchas manually")
                        print(f"      - Inspect the page state")
                        print(f"      - Check for store information")
                        print(f"   ⏸️  Press Ctrl+C when ready to close browser...")
                    try:
                        # Use an infinite sleep that can be interrupted by Ctrl+C
                        while True:
                            await asyncio.sleep(1)
                    except KeyboardInterrupt:
                        print(f"   ✅ Manual wait completed - closing browser...")
                    except Exception as e:
                        print(f"   ⚠️  Manual wait interrupted: {e}")

                return store_info

            finally:
                await page.close()

        except Exception as e:
            error_msg = f"Error scraping store info from {product_url}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return StoreInfo(
                source_url=product_url,
                error=error_msg,
                extraction_method="traditional_playwright_error",
            )

    async def scrape_multiple_stores(
        self, product_urls: list[str], **kwargs: Any
    ) -> dict[str, StoreInfo]:
        """
        Scrape store information from multiple URLs with batch optimization
        """
        if not product_urls:
            return {}

        logger.info(
            f"🚀 Batch scraping {len(product_urls)} store pages with Traditional Playwright"
        )

        results: dict[str, StoreInfo] = {}

        try:
            await self._initialize_browser()

            if not self._context:
                raise RuntimeError("Browser context not initialized")

            # Process URLs with controlled concurrency
            batch_size = kwargs.get("batch_size", 3)  # Lower for traditional Playwright
            delay_between_batches = kwargs.get("delay_between_batches", 3.0)

            for i in range(0, len(product_urls), batch_size):
                batch = product_urls[i : i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(product_urls) + batch_size - 1) // batch_size

                logger.info(
                    f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} URLs)"
                )

                # Process batch concurrently
                batch_tasks = [
                    self._scrape_single_with_page(url, **kwargs) for url in batch
                ]

                batch_results = await asyncio.gather(
                    *batch_tasks, return_exceptions=True
                )

                # Collect results
                for url, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"❌ Error processing {url}: {result}")
                        results[url] = StoreInfo(
                            source_url=url,
                            error=str(result),
                            extraction_method="traditional_playwright_batch_error",
                        )
                    else:
                        # Type assertion: result is StoreInfo here after isinstance check
                        results[url] = cast(StoreInfo, result)

                # Delay between batches
                if i + batch_size < len(product_urls):
                    logger.debug(
                        f"⏳ Waiting {delay_between_batches}s before next batch..."
                    )
                    await asyncio.sleep(delay_between_batches)

        finally:
            # Keep browser alive for potential reuse
            pass

        successful_count = sum(1 for result in results.values() if result.is_valid)
        logger.info(
            f"✅ Batch complete: {successful_count}/{len(product_urls)} successful"
        )

        # Print bandwidth stats if tracking is enabled
        if self.track_bandwidth_savings:
            stats = self.get_bandwidth_stats()
            logger.info(
                f"📊 Bandwidth stats: {stats['blocked_requests']}/{stats['total_requests']} "
                f"requests blocked ({stats['bandwidth_saved_percent']}% savings)"
            )

        return results

    async def _scrape_single_with_page(
        self, product_url: str, **kwargs: Any
    ) -> StoreInfo:
        """Scrape single URL with its own page instance"""
        if not self._context:
            raise RuntimeError("Browser context not initialized")

        page = await self._context.new_page()
        try:
            await page.goto(
                product_url,
                timeout=self.navigation_timeout * 1000,
                wait_until="domcontentloaded",
            )
            await page.wait_for_timeout(1500)
            return await self._extract_store_info_with_fallback(page, product_url)
        finally:
            await page.close()

    async def _extract_store_info_with_fallback(
        self, page: Page, product_url: str
    ) -> StoreInfo:
        """
        Extract store information using multiple fallback methods
        """
        # Primary XPath method
        store_info = await self._extract_store_name_with_xpath(page, product_url)
        if store_info.is_valid:
            return store_info

        # Fallback to CSS selector method
        store_info = await self._extract_store_name_with_css(page, product_url)
        if store_info.is_valid:
            return store_info

        # Fallback to alternative XPath
        store_info = await self._extract_store_name_alternative(page, product_url)
        if store_info.is_valid:
            return store_info

        # All methods failed
        return StoreInfo(
            source_url=product_url,
            error="All extraction methods failed to find store information",
            extraction_method="traditional_playwright_all_failed",
        )

    async def _extract_store_name_with_xpath(
        self, page: Page, product_url: str
    ) -> StoreInfo:
        """Extract store name using the primary XPath selector"""
        try:
            xpath_selector = '//*[@id="root"]/div/div[1]/div/div[2]/div/div/a/div[2]'

            result = await page.evaluate(f"""
                () => {{
                    const element = document.evaluate(
                        '{xpath_selector}',
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue;
                    
                    if (element) {{
                        const storeNameText = element.textContent?.trim();
                        
                        // Try to extract store ID from URL
                        const storeLink = element.closest('a')?.href;
                        let storeId = null;
                        let storeUrl = null;
                        
                        if (storeLink) {{
                            const storeIdMatch = storeLink.match(/store\\/([0-9]+)/);
                            if (storeIdMatch) {{
                                storeId = storeIdMatch[1];
                                storeUrl = storeLink;
                            }}
                        }}
                        
                        return {{
                            store_name: storeNameText,
                            store_id: storeId,
                            store_url: storeUrl,
                            found: true
                        }};
                    }}
                    
                    return {{ found: false }};
                }}
            """)

            if result and result.get("found"):
                logger.debug("✅ Store info extracted using XPath method")
                return StoreInfo(
                    store_name=result.get("store_name"),
                    store_id=result.get("store_id"),
                    store_url=result.get("store_url"),
                    source_url=product_url,
                    extraction_method="traditional_playwright_xpath",
                )
            else:
                return StoreInfo(
                    source_url=product_url,
                    error="XPath selector did not find store element",
                    extraction_method="traditional_playwright_xpath_failed",
                )

        except Exception as e:
            return StoreInfo(
                source_url=product_url,
                error=f"XPath extraction error: {str(e)}",
                extraction_method="traditional_playwright_xpath_error",
            )

    async def _extract_store_name_with_css(
        self, page: Page, product_url: str
    ) -> StoreInfo:
        """Extract store name using CSS selectors as fallback"""
        try:
            result = await page.evaluate("""
                () => {
                    // Try various CSS selectors for store information
                    const selectors = [
                        '[data-pl="store-name"]',
                        '.store-name',
                        '.seller-name',
                        '[class*="store"]',
                        '[class*="seller"]'
                    ];
                    
                    for (const selector of selectors) {
                        const element = document.querySelector(selector);
                        if (element) {
                            const storeNameText = element.textContent?.trim();
                            if (storeNameText) {
                                // Try to find store link
                                const storeLink = element.closest('a')?.href || 
                                                document.querySelector('a[href*="/store/"]')?.href;
                                
                                let storeId = null;
                                let storeUrl = null;
                                
                                if (storeLink) {
                                    const storeIdMatch = storeLink.match(/store\\/([0-9]+)/);
                                    if (storeIdMatch) {
                                        storeId = storeIdMatch[1];
                                        storeUrl = storeLink;
                                    }
                                }
                                
                                return {
                                    store_name: storeNameText,
                                    store_id: storeId,
                                    store_url: storeUrl,
                                    found: true,
                                    selector: selector
                                };
                            }
                        }
                    }
                    
                    return { found: false };
                }
            """)

            if result and result.get("found"):
                logger.debug(
                    f"✅ Store info extracted using CSS selector: {result.get('selector')}"
                )
                return StoreInfo(
                    store_name=result.get("store_name"),
                    store_id=result.get("store_id"),
                    store_url=result.get("store_url"),
                    source_url=product_url,
                    extraction_method="traditional_playwright_css",
                    metadata={"css_selector": result.get("selector")},
                )
            else:
                return StoreInfo(
                    source_url=product_url,
                    error="CSS selectors did not find store element",
                    extraction_method="traditional_playwright_css_failed",
                )

        except Exception as e:
            return StoreInfo(
                source_url=product_url,
                error=f"CSS extraction error: {str(e)}",
                extraction_method="traditional_playwright_css_error",
            )

    async def _extract_store_name_alternative(
        self, page: Page, product_url: str
    ) -> StoreInfo:
        """Extract store name using alternative methods"""
        try:
            result = await page.evaluate("""
                () => {
                    // Try to find store information in various ways
                    
                    // Method 1: Look for store links in the page
                    const storeLinks = document.querySelectorAll('a[href*="/store/"]');
                    for (const link of storeLinks) {
                        const text = link.textContent?.trim();
                        if (text && text.length > 0) {
                            const storeIdMatch = link.href.match(/store\\/([0-9]+)/);
                            if (storeIdMatch) {
                                return {
                                    store_name: text,
                                    store_id: storeIdMatch[1],
                                    store_url: link.href,
                                    found: true,
                                    method: 'store_link'
                                };
                            }
                        }
                    }
                    
                    // Method 2: Look for seller information in breadcrumbs or headers
                    const breadcrumbSelectors = [
                        '.breadcrumb a',
                        '[class*="breadcrumb"] a',
                        'nav a',
                        '.seller-info',
                        '.store-info'
                    ];
                    
                    for (const selector of breadcrumbSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const element of elements) {
                            const text = element.textContent?.trim();
                            if (text && (text.includes('Store') || text.includes('Shop'))) {
                                const href = element.href;
                                if (href && href.includes('/store/')) {
                                    const storeIdMatch = href.match(/store\\/([0-9]+)/);
                                    if (storeIdMatch) {
                                        return {
                                            store_name: text,
                                            store_id: storeIdMatch[1],
                                            store_url: href,
                                            found: true,
                                            method: 'breadcrumb'
                                        };
                                    }
                                }
                            }
                        }
                    }
                    
                    return { found: false };
                }
            """)

            if result and result.get("found"):
                logger.debug(
                    f"✅ Store info extracted using alternative method: {result.get('method')}"
                )
                return StoreInfo(
                    store_name=result.get("store_name"),
                    store_id=result.get("store_id"),
                    store_url=result.get("store_url"),
                    source_url=product_url,
                    extraction_method="traditional_playwright_alternative",
                    metadata={"method": result.get("method")},
                )
            else:
                return StoreInfo(
                    source_url=product_url,
                    error="Alternative methods did not find store element",
                    extraction_method="traditional_playwright_alternative_failed",
                )

        except Exception as e:
            return StoreInfo(
                source_url=product_url,
                error=f"Alternative extraction error: {str(e)}",
                extraction_method="traditional_playwright_alternative_error",
            )
