#!/usr/bin/env python3
"""
Enhanced Store Scraper Integration
==================================

This module integrates the new dependency injection store scraper framework
with the existing enhanced_scraper.py and scraper.py modules, providing
seamless backwards compatibility while adding new capabilities.
"""

import asyncio
import logging
from typing import Any, Callable

# Import implementations to register them
# These imports are required for the decorators to execute and register the scrapers
from . import (
    mcp_store_scraper,  # pyright: ignore[reportUnusedImport]
    traditional_store_scraper,  # pyright: ignore[reportUnusedImport]
)

# Import the dependency injection framework
from .scraper_interface import (
    StoreScrapingMethod,
    setup_default_fallback_chain,
    store_scraper_manager,
)

logger = logging.getLogger(__name__)


class EnhancedStoreInfoIntegration:
    """
    Integration class that bridges the new store scraper framework
    with existing scraper implementations.
    """

    def __init__(
        self,
        preferred_method: StoreScrapingMethod | None = None,
        proxy_provider: str = "",
        log_callback: Callable[[str], None] | None = None,
    ):
        """
        Initialize the enhanced store info integration

        Args:
            preferred_method: Preferred scraping method
            proxy_provider: Proxy provider ("oxylabs", "massive", or "")
            log_callback: Logging callback function
        """
        self.preferred_method = preferred_method
        self.proxy_provider = proxy_provider
        self.log_callback = log_callback or self._default_logger

        # Setup default fallback chain
        setup_default_fallback_chain()

        # Configure proxy settings
        self.proxy_config = self._get_proxy_config()

    def _default_logger(self, message: str) -> None:
        """Default logging function"""
        logger.debug(message)

    def _get_proxy_config(self) -> dict[str, Any]:
        """Get proxy configuration"""
        config: dict[str, Any] = {}

        if self.proxy_provider == "oxylabs":
            import os

            username = os.getenv("OXYLABS_USERNAME")
            password = os.getenv("OXYLABS_PASSWORD")
            endpoint = os.getenv("OXYLABS_ENDPOINT", "pr.oxylabs.io:7777")

            if username and password:
                config.update(
                    {
                        "use_oxylabs_proxy": True,
                        "proxy_username": username,
                        "proxy_password": password,
                        "proxy_endpoint": endpoint,
                    }
                )

        return config

    async def fetch_store_info_enhanced(
        self, product_urls: list[str], **kwargs: Any
    ) -> dict[str, dict[str, str | None]]:
        """
        Enhanced store info fetching using the new framework.

        This method replaces the traditional fetch_store_info_batch() function
        with support for multiple scraping methods and automatic fallbacks.

        Args:
            product_urls: list of product URLs to scrape
            **kwargs: Additional configuration options

        Returns:
            Dictionary mapping URLs to store info dictionaries
        """
        if not product_urls:
            return {}

        # Merge proxy config with kwargs
        scraping_config = {**self.proxy_config, **kwargs}

        try:
            # Use the dependency injection framework
            store_results = (
                await store_scraper_manager.scrape_multiple_stores_with_fallback(
                    product_urls=product_urls,
                    preferred_method=self.preferred_method,
                    **scraping_config,
                )
            )

            # Convert to the format expected by existing code
            legacy_format_results: dict[str, dict[str, str | None]] = {}

            for url, store_info in store_results.items():
                legacy_format_results[url] = {
                    "store_name": store_info.store_name,
                    "store_id": store_info.store_id,
                    "store_url": store_info.store_url,
                }

            successful_count = sum(
                1
                for result in legacy_format_results.values()
                if result.get("store_name")
            )

            self.log_callback(
                f"✅ Enhanced store info fetch complete: {successful_count}/{len(product_urls)} successful"
            )

            return legacy_format_results

        except Exception:
            # Return empty results in case of failure
            return {
                url: {"store_name": None, "store_id": None, "store_url": None}
                for url in product_urls
            }

    async def fetch_single_store_info(
        self, product_url: str, **kwargs: Any
    ) -> dict[str, str | None]:
        """
        Fetch store info for a single product URL

        Args:
            product_url: Product URL to scrape
            **kwargs: Additional configuration options

        Returns:
            Dictionary with store information
        """
        results = await self.fetch_store_info_enhanced([product_url], **kwargs)
        return results.get(
            product_url, {"store_name": None, "store_id": None, "store_url": None}
        )


# Global integration instance
_store_integration: EnhancedStoreInfoIntegration | None = None


def get_store_integration(
    proxy_provider: str = "", log_callback: Callable[[str], None] | None = None
) -> EnhancedStoreInfoIntegration:
    """
    Get or create the global store integration instance

    Args:
        proxy_provider: Proxy provider to use
        log_callback: Logging callback function

    Returns:
        EnhancedStoreInfoIntegration instance
    """
    global _store_integration

    if _store_integration is None:
        # Determine preferred method based on environment
        preferred_method = None
        try:
            # Try to detect if MCP functions are available
            import inspect

            frame = inspect.currentframe()
            while frame:
                if "mcp_playwright_browser_navigate" in frame.f_globals:
                    preferred_method = StoreScrapingMethod.MCP_PLAYWRIGHT
                    break
                frame = frame.f_back
        except:
            pass

        if preferred_method is None:
            # Default to traditional Playwright
            preferred_method = StoreScrapingMethod.TRADITIONAL_PLAYWRIGHT

        _store_integration = EnhancedStoreInfoIntegration(
            preferred_method=preferred_method,
            proxy_provider=proxy_provider,
            log_callback=log_callback,
        )

    return _store_integration


def enhance_existing_scraper_with_store_integration():
    """
    Monkey patch existing scraper functions to use the enhanced store integration.

    This function modifies the existing fetch_store_info_batch and related functions
    to use the new dependency injection framework while maintaining compatibility.
    """
    try:
        # Import existing scraper modules
        from ..core import scraper
        from ..scrapers import enhanced_scraper

        # Create async wrapper for the existing synchronous interface
        def create_async_wrapper(
            integration_instance: "EnhancedStoreInfoIntegration",
        ) -> Callable[..., Any]:
            def async_fetch_store_info_batch(
                product_ids: list[str],
                session: Any,
                proxy_provider: str = "",
                log_callback: Callable[[str], None] = scraper.default_logger,
                max_workers: int = 3,
            ) -> dict[str, dict[str, str | None]]:
                """
                Enhanced replacement for fetch_store_info_batch that uses async methods
                """
                # Convert product IDs to URLs
                product_urls = [
                    f"https://www.aliexpress.com/item/{product_id}.html"
                    for product_id in product_ids
                    if product_id
                ]

                # Run the async method
                loop = None
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    # If we're already in an async context, we need to handle this differently
                    # Create a new event loop in a thread
                    import concurrent.futures

                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(
                                integration_instance.fetch_store_info_enhanced(
                                    product_urls,
                                    proxy_provider=proxy_provider,
                                    max_workers=max_workers,
                                )
                            )
                        finally:
                            new_loop.close()

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_in_thread)
                        results = future.result()
                else:
                    results = loop.run_until_complete(
                        integration_instance.fetch_store_info_enhanced(
                            product_urls,
                            proxy_provider=proxy_provider,
                            max_workers=max_workers,
                        )
                    )

                # Convert URL-based results back to product ID-based results
                final_results: dict[str, dict[str, Any]] = {}
                for i, product_id in enumerate(product_ids):
                    if i < len(product_urls):
                        url = product_urls[i]
                        final_results[product_id] = results.get(
                            url,
                            {"store_name": None, "store_id": None, "store_url": None},
                        )
                    else:
                        final_results[product_id] = {
                            "store_name": None,
                            "store_id": None,
                            "store_url": None,
                        }

                return final_results

            return async_fetch_store_info_batch

        # Get integration instance
        integration = get_store_integration()

        # Replace the fetch_store_info_batch function
        enhanced_fetch_function = create_async_wrapper(integration)

        # Monkey patch both modules
        scraper.fetch_store_info_batch = enhanced_fetch_function  # type: ignore
        if hasattr(enhanced_scraper, "fetch_store_info_batch"):
            enhanced_scraper.fetch_store_info_batch = enhanced_fetch_function  # type: ignore

        pass  # Silent integration

    except ImportError as e:
        print(f"⚠️ Could not enhance existing scrapers: {e}")
    except Exception as e:
        print(f"❌ Error applying store integration: {e}")


# Convenience functions for direct usage
async def scrape_stores_for_products(
    products: list[dict[str, Any]],
    url_field: str = "url",
    proxy_provider: str = "",
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Scrape store information for a list of products and enhance them

    Args:
        products: list of product dictionaries
        url_field: Field name containing the product URL
        proxy_provider: Proxy provider to use
        **kwargs: Additional scraping parameters

    Returns:
        list of products enhanced with store information
    """
    if not products:
        return []

    # Extract URLs
    product_urls: list[str] = []
    for product in products:
        url = product.get(url_field)
        if url:
            product_urls.append(url)

    if not product_urls:
        logger.warning("No valid URLs found in products")
        return products

    # Get integration instance
    integration = get_store_integration(proxy_provider=proxy_provider)

    # Scrape store information
    store_results = await integration.fetch_store_info_enhanced(product_urls, **kwargs)

    # Enhance products with store information
    enhanced_products: list[dict[str, Any]] = []
    for product in products:
        enhanced_product = product.copy()
        url = product.get(url_field)

        if url and url in store_results:
            store_info = store_results[url]
            if store_info.get("store_name"):
                enhanced_product.update(
                    {
                        "store_name": store_info["store_name"],
                        "store_id": store_info["store_id"],
                        "store_url": store_info["store_url"],
                    }
                )

        enhanced_products.append(enhanced_product)

    return enhanced_products


def configure_store_scraping_method(method: StoreScrapingMethod) -> None:
    """
    Configure the preferred store scraping method globally

    Args:
        method: Preferred scraping method
    """
    global _store_integration

    if _store_integration:
        _store_integration.preferred_method = method

    store_scraper_manager.set_default_method(method)
    print(f"✅ Configured default store scraping method: {method.value}")


def list_available_store_methods() -> list[str]:
    """
    list all available store scraping methods

    Returns:
        list of available method names
    """
    from .scraper_interface import store_scraper_registry

    available_methods = store_scraper_registry.list_available_methods()
    return [method.value for method in available_methods]


def retry_missing_store_info(
    products: list[dict[str, Any]],
    proxy_provider: str = "",
    batch_size: int = 5,
    delay: float = 2.0,
) -> list[dict[str, Any]]:
    """
    Simple function to retry missing store information for products

    Args:
        products: list of product dictionaries
        proxy_provider: Proxy provider to use
        batch_size: Batch size for processing
        delay: Delay between batches

    Returns:
        list of products with updated store information
    """
    import asyncio

    # Remove unused time import

    async def _async_retry():
        # Find products with missing store info
        missing_products: list[dict[str, Any]] = []
        for product in products:
            store_name = product.get("Store Name")
            product_url = product.get("Product URL")

            if (
                not store_name or store_name in [None, "null", "", "N/A"]
            ) and product_url:
                missing_products.append(product)

        if not missing_products:
            return products

        # Extract URLs for retry with explicit typing
        urls_to_retry: list[str] = [
            p["Product URL"] for p in missing_products if p.get("Product URL")
        ]

        if not urls_to_retry:
            return products

        # Get integration and retry silently
        integration = get_store_integration(proxy_provider=proxy_provider)

        # Process in batches
        all_retry_results: dict[str, Any] = {}

        for i in range(0, len(urls_to_retry), batch_size):
            batch_urls: list[str] = urls_to_retry[i : i + batch_size]

            try:
                batch_results = await integration.fetch_store_info_enhanced(batch_urls)
                all_retry_results.update(batch_results)
            except:
                pass  # Silent failure

            # Delay between batches
            if i + batch_size < len(urls_to_retry) and delay > 0:
                await asyncio.sleep(delay)

        # Update products with retry results
        updated_products: list[dict[str, Any]] = []

        for product in products:
            product_url = product.get("Product URL")

            if product_url in all_retry_results:
                store_info: dict[str, Any] = all_retry_results[product_url]
                updated_product = product.copy()

                if store_info.get("store_name"):
                    updated_product["Store Name"] = store_info["store_name"]

                if store_info.get("store_id"):
                    updated_product["Store ID"] = store_info["store_id"]

                if store_info.get("store_url"):
                    updated_product["Store URL"] = store_info["store_url"]

                updated_products.append(updated_product)
            else:
                updated_products.append(product)

        return updated_products

    # Run async function
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, create new thread
            import concurrent.futures

            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(_async_retry())
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        else:
            return loop.run_until_complete(_async_retry())
    except RuntimeError:
        # No event loop, create new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_async_retry())
        finally:
            loop.close()


# Auto-apply integration when module is imported
try:
    enhance_existing_scraper_with_store_integration()
except Exception as e:
    logger.warning(f"Could not auto-apply store integration: {e}")
