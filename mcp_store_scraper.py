#!/usr/bin/env python3
"""
MCP Playwright Store Scraper Implementation
==========================================

This module implements the StoreScraperInterface using MCP Playwright functions
for use within VS Code with the MCP Playwright extension.
"""

import asyncio
import logging
from typing import Any, Dict, List, cast

from store_scraper_interface import (
    StoreInfo,
    StoreScraperInterface,
    StoreScrapingMethod,
    register_store_scraper,
)

logger = logging.getLogger(__name__)


@register_store_scraper(StoreScrapingMethod.MCP_PLAYWRIGHT)
class MCPPlaywrightStoreScraper(StoreScraperInterface):
    """
    Store scraper implementation using MCP Playwright functions

    This implementation uses the MCP (Model Context Protocol) Playwright functions
    that are available when running in VS Code with the MCP Playwright extension.
    """

    def __init__(
        self,
        use_oxylabs_proxy: bool = False,
        extraction_timeout: int = 10,
        navigation_timeout: int = 30,
        retry_attempts: int = 3,
        **kwargs: Any,
    ):
        """
        Initialize MCP Playwright store scraper

        Args:
            use_oxylabs_proxy: Whether to use Oxylabs proxy configuration
            extraction_timeout: Timeout for store data extraction (seconds)
            navigation_timeout: Timeout for page navigation (seconds)
            retry_attempts: Number of retry attempts for failed extractions
            **kwargs: Additional configuration options
        """
        self.use_oxylabs_proxy = use_oxylabs_proxy
        self.extraction_timeout = extraction_timeout
        self.navigation_timeout = navigation_timeout
        self.retry_attempts = retry_attempts
        self.config = kwargs

    @property
    def method_name(self) -> StoreScrapingMethod:
        """Get the scraping method name"""
        return StoreScrapingMethod.MCP_PLAYWRIGHT

    @property
    def supports_batch_processing(self) -> bool:
        """MCP Playwright supports efficient batch processing"""
        return True

    def get_scraper_info(self) -> Dict[str, Any]:
        """Get scraper information"""
        return {
            "method": self.method_name.value,
            "description": "MCP Playwright store scraper for VS Code",
            "supports_batch": self.supports_batch_processing,
            "proxy_enabled": self.use_oxylabs_proxy,
            "extraction_timeout": self.extraction_timeout,
            "navigation_timeout": self.navigation_timeout,
            "retry_attempts": self.retry_attempts,
            "config": self.config,
        }

    async def scrape_single_store(self, product_url: str, **kwargs: Any) -> StoreInfo:
        """
        Scrape store information from a single product URL using MCP Playwright
        """
        logger.info(f"🔍 Scraping store info from: {product_url}")

        if self.use_oxylabs_proxy:
            logger.info("🌐 Oxylabs proxy should be configured at browser launch level")
            logger.info("📡 Proxy endpoint: pr.oxylabs.io:7777")
            logger.info("💡 To use proxy, launch the browser with proxy configuration")

        try:
            # Navigate to the product page
            logger.debug(f"📡 Navigating to: {product_url}")
            await self._navigate_to_url(product_url)

            # Wait for page to load
            await self._wait_for_page_ready()

            # Extract store information using multiple methods
            store_info = await self._extract_store_info_with_fallback(product_url)

            if store_info.is_valid:
                logger.info(f"✅ Successfully extracted store: {store_info.store_name}")
            else:
                logger.warning(
                    f"⚠️ Failed to extract valid store info: {store_info.error}"
                )

            return store_info

        except Exception as e:
            error_msg = f"Error scraping store info from {product_url}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return StoreInfo(
                source_url=product_url,
                error=error_msg,
                extraction_method="mcp_playwright_error",
            )

    async def scrape_multiple_stores(
        self, product_urls: List[str], **kwargs: Any
    ) -> Dict[str, StoreInfo]:
        """
        Scrape store information from multiple URLs with batch optimization
        """
        if not product_urls:
            return {}

        logger.info(
            f"🚀 Batch scraping {len(product_urls)} store pages with MCP Playwright"
        )

        results: Dict[str, StoreInfo] = {}

        # Process URLs with controlled concurrency
        batch_size = kwargs.get("batch_size", 5)
        delay_between_batches = kwargs.get("delay_between_batches", 2.0)

        for i in range(0, len(product_urls), batch_size):
            batch = product_urls[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(product_urls) + batch_size - 1) // batch_size

            logger.info(
                f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} URLs)"
            )

            # Process batch concurrently
            batch_tasks = [self.scrape_single_store(url, **kwargs) for url in batch]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Collect results
            for url, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Error processing {url}: {result}")
                    results[url] = StoreInfo(
                        source_url=url,
                        error=str(result),
                        extraction_method="mcp_playwright_batch_error",
                    )
                else:
                    # Type assertion: result is StoreInfo here after isinstance check
                    results[url] = cast(StoreInfo, result)

            # Delay between batches to avoid overwhelming the server
            if i + batch_size < len(product_urls):
                logger.debug(
                    f"⏳ Waiting {delay_between_batches}s before next batch..."
                )
                await asyncio.sleep(delay_between_batches)

        successful_count = sum(1 for result in results.values() if result.is_valid)
        logger.info(
            f"✅ Batch complete: {successful_count}/{len(product_urls)} successful"
        )

        return results

    async def _navigate_to_url(self, url: str) -> None:
        """Navigate to URL using MCP Playwright"""
        try:
            # Note: This function will be available when running in VS Code with MCP Playwright
            await mcp_playwright_browser_navigate(url=url)  # type: ignore
            logger.debug(f"✅ Navigated to: {url}")
        except NameError:
            raise RuntimeError(
                "MCP Playwright functions not available. "
                "This scraper requires VS Code with MCP Playwright extension."
            )

    async def _wait_for_page_ready(self) -> None:
        """Wait for page to be ready for scraping"""
        try:
            # Wait for a reasonable time for the page to load
            await asyncio.sleep(2)
            logger.debug("✅ Page ready for scraping")
        except Exception as e:
            logger.warning(f"⚠️ Error waiting for page: {e}")

    async def _extract_store_info_with_fallback(self, product_url: str) -> StoreInfo:
        """
        Extract store information using multiple fallback methods
        """
        # Primary XPath method
        store_info = await self._extract_store_name_with_xpath(product_url)
        if store_info.is_valid:
            return store_info

        # Fallback to CSS selector method
        store_info = await self._extract_store_name_with_css(product_url)
        if store_info.is_valid:
            return store_info

        # Fallback to alternative XPath
        store_info = await self._extract_store_name_alternative(product_url)
        if store_info.is_valid:
            return store_info

        # All methods failed
        return StoreInfo(
            source_url=product_url,
            error="All extraction methods failed to find store information",
            extraction_method="mcp_playwright_all_failed",
        )

    async def _extract_store_name_with_xpath(self, product_url: str) -> StoreInfo:
        """Extract store name using the primary XPath selector"""
        try:
            # Use the specified XPath for store name extraction
            xpath_selector = '//*[@id="root"]/div/div[1]/div/div[2]/div/div/a/div[2]'

            js_code = f"""
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
            """

            result = await mcp_playwright_browser_evaluate(function=js_code)  # type: ignore

            # Type hint for result from MCP evaluate
            result_dict = cast(Dict[str, Any], result) if result else {}

            if result_dict and result_dict.get("found"):
                logger.debug("✅ Store info extracted using XPath method")
                return StoreInfo(
                    store_name=result_dict.get("store_name"),
                    store_id=result_dict.get("store_id"),
                    store_url=result_dict.get("store_url"),
                    source_url=product_url,
                    extraction_method="mcp_playwright_xpath",
                )
            else:
                return StoreInfo(
                    source_url=product_url,
                    error="XPath selector did not find store element",
                    extraction_method="mcp_playwright_xpath_failed",
                )

        except Exception as e:
            return StoreInfo(
                source_url=product_url,
                error=f"XPath extraction error: {str(e)}",
                extraction_method="mcp_playwright_xpath_error",
            )

    async def _extract_store_name_with_css(self, product_url: str) -> StoreInfo:
        """Extract store name using CSS selectors as fallback"""
        try:
            js_code = """
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
            """

            result = await mcp_playwright_browser_evaluate(function=js_code)  # type: ignore

            # Type hint for result from MCP evaluate
            result_dict = cast(Dict[str, Any], result) if result else {}

            if result_dict and result_dict.get("found"):
                logger.debug(
                    f"✅ Store info extracted using CSS selector: {result_dict.get('selector')}"
                )
                return StoreInfo(
                    store_name=result_dict.get("store_name"),
                    store_id=result_dict.get("store_id"),
                    store_url=result_dict.get("store_url"),
                    source_url=product_url,
                    extraction_method="mcp_playwright_css",
                    metadata={"css_selector": result_dict.get("selector")},
                )
            else:
                return StoreInfo(
                    source_url=product_url,
                    error="CSS selectors did not find store element",
                    extraction_method="mcp_playwright_css_failed",
                )

        except Exception as e:
            return StoreInfo(
                source_url=product_url,
                error=f"CSS extraction error: {str(e)}",
                extraction_method="mcp_playwright_css_error",
            )

    async def _extract_store_name_alternative(self, product_url: str) -> StoreInfo:
        """Extract store name using alternative methods"""
        try:
            js_code = """
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
            """

            result = await mcp_playwright_browser_evaluate(function=js_code)  # type: ignore

            # Type hint for result from MCP evaluate
            result_dict = cast(Dict[str, Any], result) if result else {}

            if result_dict and result_dict.get("found"):
                logger.debug(
                    f"✅ Store info extracted using alternative method: {result_dict.get('method')}"
                )
                return StoreInfo(
                    store_name=result_dict.get("store_name"),
                    store_id=result_dict.get("store_id"),
                    store_url=result_dict.get("store_url"),
                    source_url=product_url,
                    extraction_method="mcp_playwright_alternative",
                    metadata={"method": result_dict.get("method")},
                )
            else:
                return StoreInfo(
                    source_url=product_url,
                    error="Alternative methods did not find store element",
                    extraction_method="mcp_playwright_alternative_failed",
                )

        except Exception as e:
            return StoreInfo(
                source_url=product_url,
                error=f"Alternative extraction error: {str(e)}",
                extraction_method="mcp_playwright_alternative_error",
            )


# Export convenience functions that match the original store_scraper.py interface
async def scrape_store_from_url(
    product_url: str, use_oxylabs_proxy: bool = False, **kwargs: Any
) -> Dict[str, Any]:
    """
    Convenience function that matches the original store_scraper.py interface

    Args:
        product_url: URL of the product page
        use_oxylabs_proxy: Whether to use Oxylabs proxy
        **kwargs: Additional scraping parameters

    Returns:
        Dictionary with store information (compatible with original interface)
    """
    scraper = MCPPlaywrightStoreScraper(use_oxylabs_proxy=use_oxylabs_proxy, **kwargs)  # type: ignore

    store_info = await scraper.scrape_single_store(product_url, **kwargs)
    return store_info.to_dict()


async def enhance_products_with_store_info(
    products: List[Dict[str, Any]],
    url_field: str = "url",
    use_oxylabs_proxy: bool = False,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Enhance a list of products with store information

    Args:
        products: List of product dictionaries
        url_field: Field name containing the product URL
        use_oxylabs_proxy: Whether to use Oxylabs proxy
        **kwargs: Additional scraping parameters

    Returns:
        List of products enhanced with store information
    """
    if not products:
        return []

    # Extract URLs
    product_urls: List[str] = []
    for product in products:
        url = product.get(url_field)
        if url:
            product_urls.append(url)

    if not product_urls:
        logger.warning("No valid URLs found in products")
        return products

    # Scrape store information
    scraper = MCPPlaywrightStoreScraper(use_oxylabs_proxy=use_oxylabs_proxy, **kwargs)  # type: ignore

    store_results = await scraper.scrape_multiple_stores(product_urls, **kwargs)

    # Enhance products with store information
    enhanced_products: List[Dict[str, Any]] = []
    for product in products:
        enhanced_product = product.copy()
        url = product.get(url_field)

        if url and url in store_results:
            store_info = store_results[url]
            if store_info.is_valid:
                enhanced_product.update(
                    {
                        "store_name": store_info.store_name,
                        "store_id": store_info.store_id,
                        "store_url": store_info.store_url,
                    }
                )

        enhanced_products.append(enhanced_product)

    return enhanced_products


if __name__ == "__main__":
    # Test the scraper (when MCP functions are available)
    async def test_mcp_scraper():
        print("🧪 Testing MCP Playwright Store Scraper")
        print("=" * 50)

        test_url = "https://www.aliexpress.com/item/3256809329880105.html"

        try:
            # Test single URL scraping
            result = await scrape_store_from_url(test_url, use_oxylabs_proxy=True)
            print(f"✅ Single URL result: {result}")

            # Test batch scraping
            test_products = [
                {"url": test_url, "title": "Test Product 1"},
                {
                    "url": "https://www.aliexpress.com/item/1234567890.html",
                    "title": "Test Product 2",
                },
            ]

            enhanced = await enhance_products_with_store_info(test_products)
            print(f"✅ Enhanced products: {enhanced}")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            print("Note: This requires VS Code with MCP Playwright extension")

    asyncio.run(test_mcp_scraper())
