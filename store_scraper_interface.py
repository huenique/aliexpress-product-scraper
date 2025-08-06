#!/usr/bin/env python3
"""
Store Scraper Interface and Dependency Injection Framework
==========================================================

This module provides a flexible interface for different store scraping implementations,
allowing easy integration of multiple store scrapers with dependency injection.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Set, Type

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StoreScrapingMethod(Enum):
    """Available store scraping methods"""

    MCP_PLAYWRIGHT = "mcp_playwright"
    TRADITIONAL_PLAYWRIGHT = "traditional_playwright"
    REQUESTS_BASED = "requests_based"
    SELENIUM = "selenium"
    CAPTCHA_SOLVER = "captcha_solver"


class StoreInfo:
    """Data class for store information"""

    def __init__(
        self,
        store_name: str | None = None,
        store_id: str | None = None,
        store_url: str | None = None,
        source_url: str | None = None,
        extraction_method: str | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.store_name = store_name
        self.store_id = store_id
        self.store_url = store_url
        self.source_url = source_url
        self.extraction_method = extraction_method
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "store_name": self.store_name,
            "store_id": self.store_id,
            "store_url": self.store_url,
            "source_url": self.source_url,
            "extraction_method": self.extraction_method,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoreInfo":
        """Create from dictionary"""
        return cls(
            store_name=data.get("store_name"),
            store_id=data.get("store_id"),
            store_url=data.get("store_url"),
            source_url=data.get("source_url"),
            extraction_method=data.get("extraction_method"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )

    @property
    def is_valid(self) -> bool:
        """Check if store info is valid (has at least store name or ID)"""
        return bool(self.store_name or self.store_id) and not self.error

    def __repr__(self) -> str:
        return f"StoreInfo(name='{self.store_name}', id='{self.store_id}', method='{self.extraction_method}')"


class StoreScraperInterface(ABC):
    """Abstract interface for store scrapers"""

    @abstractmethod
    async def scrape_single_store(self, product_url: str, **kwargs: Any) -> StoreInfo:
        """
        Scrape store information from a single product URL

        Args:
            product_url: URL of the product page
            **kwargs: Additional scraper-specific parameters

        Returns:
            StoreInfo object with scraped data
        """
        pass

    @abstractmethod
    async def scrape_multiple_stores(
        self, product_urls: list[str], **kwargs: Any
    ) -> dict[str, StoreInfo]:
        """
        Scrape store information from multiple product URLs

        Args:
            product_urls: list of product URLs
            **kwargs: Additional scraper-specific parameters

        Returns:
            Dictionary mapping URLs to StoreInfo objects
        """
        pass

    @abstractmethod
    def get_scraper_info(self) -> dict[str, Any]:
        """
        Get information about this scraper implementation

        Returns:
            Dictionary with scraper metadata
        """
        pass

    @property
    @abstractmethod
    def method_name(self) -> StoreScrapingMethod:
        """Get the scraping method used by this implementation"""
        pass

    @property
    @abstractmethod
    def supports_batch_processing(self) -> bool:
        """Whether this scraper supports efficient batch processing"""
        pass


class StoreScraperRegistry:
    """Registry for store scraper implementations"""

    def __init__(self):
        self._scrapers: dict[StoreScrapingMethod, Type[StoreScraperInterface]] = {}
        self._instances: dict[StoreScrapingMethod, StoreScraperInterface] = {}

    def register(
        self, method: StoreScrapingMethod, scraper_class: Type[StoreScraperInterface]
    ) -> None:
        """Register a store scraper implementation"""
        self._scrapers[method] = scraper_class
        logger.debug(f"Registered store scraper: {method.value}")

    def get_scraper(
        self, method: StoreScrapingMethod, **kwargs: Any
    ) -> StoreScraperInterface:
        """Get a scraper instance for the specified method"""
        if method not in self._scrapers:
            raise ValueError(f"Store scraper not registered: {method.value}")

        # Return cached instance or create new one
        if method not in self._instances:
            scraper_class = self._scrapers[method]
            self._instances[method] = scraper_class(**kwargs)

        return self._instances[method]

    def list_available_methods(self) -> list[StoreScrapingMethod]:
        """list all registered scraping methods"""
        return list(self._scrapers.keys())

    def clear_instances(self) -> None:
        """Clear all cached scraper instances"""
        self._instances.clear()


class StoreScraperManager:
    """
    Manager class for orchestrating store scraping with fallback strategies
    """

    def __init__(self, registry: StoreScraperRegistry | None = None):
        self.registry = registry or StoreScraperRegistry()
        self.fallback_chain: list[StoreScrapingMethod] = []
        self.default_method: StoreScrapingMethod | None = None

    def set_default_method(self, method: StoreScrapingMethod) -> None:
        """Set the default scraping method"""
        self.default_method = method

    def set_fallback_chain(self, methods: list[StoreScrapingMethod]) -> None:
        """
        Set the fallback chain - methods will be tried in order if previous ones fail
        """
        self.fallback_chain = methods.copy()

    async def scrape_store_with_fallback(
        self,
        product_url: str,
        preferred_method: StoreScrapingMethod | None = None,
        **kwargs: Any,
    ) -> StoreInfo:
        """
        Scrape store info with automatic fallback to other methods if primary fails
        """
        methods_to_try: list[StoreScrapingMethod] = []

        # Add preferred method first
        if preferred_method:
            methods_to_try.append(preferred_method)
        elif self.default_method:
            methods_to_try.append(self.default_method)

        # Add fallback chain
        methods_to_try.extend(self.fallback_chain)

        # Remove duplicates while preserving order
        seen: Set[StoreScrapingMethod] = set()
        unique_methods: list[StoreScrapingMethod] = []
        for method in methods_to_try:
            if method not in seen:
                unique_methods.append(method)
                seen.add(method)

        last_error = None

        for method in unique_methods:
            try:
                if method not in self.registry.list_available_methods():
                    logger.warning(f"Scraper not available: {method.value}, skipping")
                    continue

                scraper = self.registry.get_scraper(method, **kwargs)
                logger.info(f"Trying store scraping with: {method.value}")

                result = await scraper.scrape_single_store(product_url, **kwargs)

                if result.is_valid:
                    logger.info(f"Successfully scraped store with: {method.value}")
                    return result
                else:
                    logger.warning(f"No valid store data from: {method.value}")
                    last_error = result.error or "No valid store data returned"

            except Exception as e:
                logger.warning(f"Error with {method.value}: {str(e)}")
                last_error = str(e)
                continue

        # All methods failed
        return StoreInfo(
            source_url=product_url,
            error=f"All scraping methods failed. Last error: {last_error}",
            extraction_method="fallback_failed",
        )

    async def scrape_multiple_stores_with_fallback(
        self,
        product_urls: list[str],
        preferred_method: StoreScrapingMethod | None = None,
        **kwargs: Any,
    ) -> dict[str, StoreInfo]:
        """
        Scrape multiple stores with fallback, optimizing for batch processing when possible
        """
        if not product_urls:
            return {}

        # Try batch processing first with preferred method
        method_to_use = preferred_method or self.default_method
        if method_to_use and method_to_use in self.registry.list_available_methods():
            try:
                scraper = self.registry.get_scraper(method_to_use, **kwargs)
                if scraper.supports_batch_processing:
                    logger.info(f"Using batch processing with: {method_to_use.value}")
                    return await scraper.scrape_multiple_stores(product_urls, **kwargs)
            except Exception as e:
                logger.warning(
                    f"Batch processing failed with {method_to_use.value}: {e}"
                )

        # Fall back to individual scraping with fallback for each URL
        logger.info(
            f"Using individual scraping with fallback for {len(product_urls)} URLs"
        )
        results: dict[str, StoreInfo] = {}

        # Process URLs concurrently but with limits to avoid overwhelming
        semaphore = asyncio.Semaphore(3)  # Limit concurrent requests

        async def scrape_single_with_semaphore(url: str) -> tuple[str, StoreInfo]:
            async with semaphore:
                result = await self.scrape_store_with_fallback(
                    url, preferred_method, **kwargs
                )
                return url, result

        tasks = [scrape_single_with_semaphore(url) for url in product_urls]
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed_results:
            if isinstance(result, Exception):
                logger.error(f"Task failed: {result}")
                continue
            if isinstance(result, tuple) and len(result) == 2:
                url, store_info = result
                results[url] = store_info

        return results


# Global registry instance
store_scraper_registry = StoreScraperRegistry()

# Default manager instance
store_scraper_manager = StoreScraperManager(store_scraper_registry)


def register_store_scraper(
    method: StoreScrapingMethod,
) -> Callable[[Type[StoreScraperInterface]], Type[StoreScraperInterface]]:
    """
    Decorator for registering store scraper implementations

    Usage:
        @register_store_scraper(StoreScrapingMethod.MCP_PLAYWRIGHT)
        class MCPPlaywrightStoreScraper(StoreScraperInterface):
            ...
    """

    def decorator(
        scraper_class: Type[StoreScraperInterface],
    ) -> Type[StoreScraperInterface]:
        store_scraper_registry.register(method, scraper_class)
        return scraper_class

    return decorator


# Convenience functions for easy integration
async def scrape_store_info(
    product_url: str, method: StoreScrapingMethod | None = None, **kwargs: Any
) -> StoreInfo:
    """
    Convenience function to scrape store info from a single URL
    """
    return await store_scraper_manager.scrape_store_with_fallback(
        product_url, method, **kwargs
    )


async def scrape_multiple_store_info(
    product_urls: list[str], method: StoreScrapingMethod | None = None, **kwargs: Any
) -> dict[str, StoreInfo]:
    """
    Convenience function to scrape store info from multiple URLs
    """
    return await store_scraper_manager.scrape_multiple_stores_with_fallback(
        product_urls, method, **kwargs
    )


def setup_default_fallback_chain() -> None:
    """
    Set up a sensible default fallback chain for store scraping methods
    """
    fallback_methods = [
        StoreScrapingMethod.MCP_PLAYWRIGHT,  # Best option in VS Code
        StoreScrapingMethod.CAPTCHA_SOLVER,  # Good for handling captchas
        StoreScrapingMethod.TRADITIONAL_PLAYWRIGHT,  # Reliable fallback
        StoreScrapingMethod.REQUESTS_BASED,  # Fastest but may be blocked
    ]

    store_scraper_manager.set_fallback_chain(fallback_methods)
    store_scraper_manager.set_default_method(StoreScrapingMethod.MCP_PLAYWRIGHT)
