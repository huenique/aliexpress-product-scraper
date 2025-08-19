#!/usr/bin/env python3
"""
AliExpress Scraper CLI Router
============================

Central command-line interface for all AliExpress scraping operations.
This module provides a unified CLI to access all scraper and utility functionality.

Usage:
    python cli.py scrape basic --help
    python cli.py scrape enhanced --help
    python cli.py scrape multi --help
    python cli.py transform --help
    python cli.py store-retry --help
"""

import argparse
import asyncio
import concurrent.futures
import csv
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
from typing import Any, Optional, Protocol, cast, runtime_checkable

from .utils.logger import ScraperLogger


@runtime_checkable
class MultiScraperArgset(Protocol):
    """Structural type for multi-query scraper args used by run_single_scraper.

    This mirrors the attributes accessed on argparse.Namespace in multi mode,
    enabling precise type checking without tying to argparse directly.
    """

    # Common
    brand: str
    pages: int
    discount: bool
    free_shipping: bool
    min_price: Optional[float]
    max_price: Optional[float]
    delay: float
    fields: list[str]
    proxy_provider: str
    enable_store_retry: bool
    store_retry_batch_size: int
    store_retry_delay: float
    output_prefix: str
    scraper_type: str


def create_basic_scraper_parser(subparsers: Any) -> None:
    """Create parser for basic scraper functionality"""
    parser = subparsers.add_parser(
        "basic",
        help="Run basic AliExpress scraper",
        description="Basic AliExpress product scraper with API-based data collection",
    )

    # Required arguments
    parser.add_argument(
        "--keyword", "-k", required=True, help="Product keyword to search for"
    )
    parser.add_argument(
        "--brand", "-b", required=True, help="Brand name to associate with products"
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
        "--delay", type=float, default=1.0, help="Delay between requests (default: 1.0)"
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
        help="Legacy parameter - store extraction is disabled for faster processing",
    )
    parser.add_argument(
        "--store-retry-batch-size",
        type=int,
        default=5,
        help="Legacy parameter - store extraction is disabled",
    )
    parser.add_argument(
        "--store-retry-delay",
        type=float,
        default=2.0,
        help="Legacy parameter - store extraction is disabled",
    )

    parser.set_defaults(func=run_basic_scraper)


def create_enhanced_scraper_parser(subparsers: Any) -> None:
    """Create parser for enhanced scraper functionality"""
    parser = subparsers.add_parser(
        "enhanced",
        help="Run enhanced AliExpress scraper with captcha solving",
        description="Enhanced scraper with captcha solving and advanced store retry",
    )

    # Required arguments - make keyword and queries-file mutually exclusive
    keyword_group = parser.add_mutually_exclusive_group(required=True)
    keyword_group.add_argument("--keyword", "-k", help="Search keyword")
    keyword_group.add_argument(
        "--queries-file",
        "-q",
        help="Path to text file containing search queries (one per line)",
    )
    parser.add_argument(
        "--brand", "-b", required=True, help="Brand name to associate with products"
    )

    # Optional arguments
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Maximum pages to scrape (default: 0 for all pages, up to 1000)",
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
        "--free-shipping-filter", action="store_true", help="Apply free shipping filter"
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
        help="Legacy parameter - store extraction is disabled for faster processing",
    )
    parser.add_argument(
        "--store-retry-batch-size",
        type=int,
        default=5,
        help="Legacy parameter - store extraction is disabled",
    )
    parser.add_argument(
        "--store-retry-delay",
        type=float,
        default=2.0,
        help="Legacy parameter - store extraction is disabled",
    )

    # Streaming support for enhanced scraper
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream results directly to JSONL and CSV to reduce memory usage",
    )

    parser.set_defaults(func=run_enhanced_scraper)


def create_multi_scraper_parser(subparsers: Any) -> None:
    """Create parser for multi-query parallel scraping"""
    parser = subparsers.add_parser(
        "multi",
        help="Run parallel scraping for multiple queries from a file",
        description="Parallel scraping of multiple queries using all available CPU cores",
    )

    # Required arguments
    parser.add_argument(
        "--queries-dir",
        "-q",
        required=True,
        help="Path to text file containing search queries (one per line)",
    )
    parser.add_argument(
        "--brand", "-b", required=True, help="Brand name to associate with products"
    )

    # Scraper type selection
    parser.add_argument(
        "--scraper-type",
        choices=["basic", "enhanced"],
        default="basic",
        help="Type of scraper to use for each query (default: basic). Note: enhanced scraper is currently not supported in multi-query mode due to browser automation complexity.",
    )

    # Optional arguments for basic scraper
    parser.add_argument(
        "--pages",
        "-p",
        type=int,
        default=1,
        choices=range(1, 61),
        metavar="[1-60]",
        help="Number of pages to scrape per query (default: 1, max: 60)",
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
        "--delay", type=float, default=1.0, help="Delay between requests (default: 1.0)"
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
        help="Legacy parameter - store extraction is disabled for faster processing",
    )
    parser.add_argument(
        "--store-retry-batch-size",
        type=int,
        default=5,
        help="Legacy parameter - store extraction is disabled",
    )
    parser.add_argument(
        "--store-retry-delay",
        type=float,
        default=2.0,
        help="Legacy parameter - store extraction is disabled",
    )

    # Enhanced scraper specific options
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Maximum pages to scrape (for enhanced scraper)",
    )
    parser.add_argument(
        "--disable-captcha-solver",
        action="store_true",
        help="Disable automatic captcha solving (for enhanced scraper)",
    )
    parser.add_argument(
        "--captcha-solver-visible",
        action="store_true",
        help="Run captcha solver in visible mode (for enhanced scraper)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts (for enhanced scraper)",
    )

    # Multi-processing options
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Maximum number of parallel workers (default: number of CPU cores)",
    )
    parser.add_argument(
        "--output-prefix",
        default="aliexpress",
        help="Prefix for output files (default: aliexpress)",
    )

    parser.set_defaults(func=run_multi_scraper)


def create_transform_parser(subparsers: Any) -> None:
    """Create parser for data transformation functionality"""
    parser = subparsers.add_parser(
        "transform",
        help="Transform scraper results to Listing table format",
        description="Transform AliExpress scraper data to align with Listing table schema",
    )

    parser.add_argument(
        "input_file", help="Path to input JSON file with AliExpress data"
    )
    parser.add_argument(
        "output_file", nargs="?", help="Path to output CSV file (optional)"
    )
    parser.add_argument(
        "--source", default="aliexpress", help="Source identifier (default: aliexpress)"
    )
    parser.add_argument("--category", help="Product category to assign to all listings")
    parser.add_argument(
        "--tags", nargs="*", help="Additional tags to apply to listings"
    )

    parser.set_defaults(func=run_transform)


def create_store_retry_parser(subparsers: Any) -> None:
    """Create parser for standalone store retry functionality"""
    parser = subparsers.add_parser(
        "store-retry",
        help="Retry missing store information for existing data",
        description="Standalone tool to retry missing store info for products in JSON file",
    )

    parser.add_argument("input_file", help="Input JSON file with product data")
    parser.add_argument("output_file", nargs="?", help="Output JSON file (optional)")
    parser.add_argument(
        "--proxy-provider",
        choices=["", "oxylabs", "massive"],
        default="",
        help="Proxy provider to use",
    )
    parser.add_argument(
        "--batch-size", type=int, default=5, help="Batch size for processing"
    )
    parser.add_argument(
        "--delay", type=float, default=2.0, help="Delay between batches"
    )
    parser.add_argument(
        "--max-workers", type=int, default=3, help="Maximum concurrent workers"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Analyze only, don't process"
    )

    # Wire to handler (function is defined below in this module)
    parser.set_defaults(func=run_store_retry)


def run_basic_scraper(args: argparse.Namespace) -> None:
    """Run the basic scraper with provided arguments"""
    logger = ScraperLogger("CLI.Basic")

    try:
        # Import from the core module
        from aliexpress_scraper.core.scraper import main as scraper_main

        # Convert args to sys.argv format for the original main function
        sys.argv = ["scraper.py"]
        sys.argv.extend(["--keyword", args.keyword])
        sys.argv.extend(["--brand", args.brand])
        sys.argv.extend(["--pages", str(args.pages)])

        if args.discount:
            sys.argv.append("--discount")
        if args.free_shipping:
            sys.argv.append("--free-shipping")
        if args.min_price is not None:
            sys.argv.extend(["--min-price", str(args.min_price)])
        if args.max_price is not None:
            sys.argv.extend(["--max-price", str(args.max_price)])

        sys.argv.extend(["--delay", str(args.delay)])
        sys.argv.extend(["--fields"] + args.fields)

        if args.proxy_provider:
            sys.argv.extend(["--proxy-provider", args.proxy_provider])
        if args.enable_store_retry:
            sys.argv.append("--enable-store-retry")
        sys.argv.extend(["--store-retry-batch-size", str(args.store_retry_batch_size)])
        sys.argv.extend(["--store-retry-delay", str(args.store_retry_delay)])

        logger.start(
            "Basic scraper execution",
            f"keyword: '{args.keyword}', brand: '{args.brand}'",
        )

        # Run the main function
        scraper_main()

    except Exception as e:
        logger.error("Basic scraper execution failed", str(e))
        sys.exit(1)


def run_enhanced_scraper(args: argparse.Namespace) -> None:
    """Run the enhanced scraper with provided arguments"""
    logger = ScraperLogger("CLI.Enhanced")

    try:
        # Validate max_pages limit
        if args.max_pages > 1000:
            logger.error("Page limit exceeded", "Maximum pages limit is 1000")
            sys.exit(1)
        if args.max_pages < 0:
            logger.error(
                "Invalid page count",
                "max-pages must be 0 (for all pages) or a positive number",
            )
            sys.exit(1)

        # Import and run EnhancedAliExpressScraper directly (module's __main__ main isn't exported)
        from aliexpress_scraper.scrapers.enhanced_scraper import (
            EnhancedAliExpressScraper,
        )

        # Handle queries file vs single keyword
        queries = []
        if args.queries_file:
            queries = read_queries_from_file(args.queries_file)
            if not queries:
                logger.error(
                    "Query processing failed", "No valid queries found in file"
                )
                sys.exit(1)
        else:
            queries = [args.keyword]

        async def _runner() -> None:
            scraper = EnhancedAliExpressScraper(
                proxy_provider=args.proxy_provider,
                enable_captcha_solver=not args.disable_captcha_solver,
                captcha_solver_headless=not args.captcha_solver_visible,
                enable_store_retry=args.enable_store_retry,
                store_retry_batch_size=args.store_retry_batch_size,
                store_retry_delay=args.store_retry_delay,
            )

            all_results: list[dict[str, Any]] = []
            all_products: list[dict[str, Any]] = []
            created_files: list[str] = []
            total_products = 0

            for i, query in enumerate(queries, 1):
                logger.progress("Query processing", f"{i}/{len(queries)}: '{query}'")

                results = await scraper.run_enhanced_scraper(
                    keyword=query,
                    brand=args.brand,
                    max_pages=args.max_pages,
                    save_to_file=not getattr(args, "stream", False),
                    apply_discount_filter=args.discount_filter,
                    apply_free_shipping_filter=args.free_shipping_filter,
                    min_price=args.min_price,
                    max_price=args.max_price,
                    delay=args.delay,
                    max_retries=args.max_retries,
                    stream=getattr(args, "stream", False),
                )

                if "error" in results:
                    logger.error(f"Query '{query}' failed", results["error"])
                else:
                    products = results.get("products", [])
                    total_streamed = results.get("total_streamed", 0)
                    product_count = len(products) if products else total_streamed
                    total_products += product_count

                    # Collect products for merged file (non-streaming mode)
                    if products:
                        all_products.extend(products)

                    # Track created files for streaming merge
                    if results.get("json_file"):
                        created_files.append(results["json_file"])
                        logger.save("JSON saved", results["json_file"])
                    if results.get("csv_file"):
                        logger.save("CSV saved", results["csv_file"])

                    logger.success(
                        f"Query '{query}' completed", f"{product_count} products"
                    )

                all_results.append(results)

            # Create merged files if we have multiple queries
            if len(queries) > 1:
                logger.process(
                    "Merge operation", "Creating consolidated files for all queries"
                )

                # Common fields for merged file
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

                if getattr(args, "stream", False) and created_files:
                    # Streaming mode: merge from individual files
                    merged_products: list[dict[str, Any]] = []

                    for json_file in created_files:
                        if os.path.exists(json_file):
                            try:
                                with open(json_file, "r", encoding="utf-8") as f:
                                    file_data: Any = json.load(f)
                                    if isinstance(file_data, list):
                                        # Filter and type-cast valid product dictionaries
                                        product_count = 0
                                        item: Any
                                        for item in file_data:  # type: ignore
                                            if isinstance(item, dict):
                                                merged_products.append(item)  # type: ignore[arg-type]
                                                product_count += 1
                                        logger.info(
                                            f"✓ Merged {product_count} products from {os.path.basename(json_file)}"
                                        )
                                    else:
                                        logger.info(
                                            f"✓ Merged 0 products from {os.path.basename(json_file)}"
                                        )
                            except (json.JSONDecodeError, FileNotFoundError) as e:
                                logger.warning(f"⚠️ Could not read {json_file}: {e}")

                    if merged_products:
                        from aliexpress_scraper.core.scraper import save_results

                        merged_json_file, merged_csv_file = save_results(
                            keyword="merged",
                            data=merged_products,
                            selected_fields=all_fields,
                            brand=args.brand,
                            log_callback=logger.info,
                        )

                        if merged_json_file:
                            logger.save("Merged JSON saved", merged_json_file)
                        if merged_csv_file:
                            logger.save("Merged CSV saved", merged_csv_file)
                        logger.info(
                            f"📦 Total products in merged files: {len(merged_products)}"
                        )

                elif all_products:
                    # Non-streaming mode: use collected products
                    from aliexpress_scraper.core.scraper import save_results

                    merged_json_file, merged_csv_file = save_results(
                        keyword="merged",
                        data=all_products,
                        selected_fields=all_fields,
                        brand=args.brand,
                        log_callback=logger.info,
                    )

                    if merged_json_file:
                        logger.save("Merged JSON saved", merged_json_file)
                    if merged_csv_file:
                        logger.save("Merged CSV saved", merged_csv_file)

            # Summary for multiple queries
            if len(queries) > 1:
                successful_queries = sum(1 for r in all_results if "error" not in r)
                logger.summary(
                    [
                        ("Total queries", len(queries)),
                        ("Successful", successful_queries),
                        ("Failed", len(queries) - successful_queries),
                        ("Total products", total_products),
                    ]
                )

        asyncio.run(_runner())

    except Exception as e:
        logger.error("Enhanced scraper execution failed", str(e))
        sys.exit(1)


def run_transform(args: argparse.Namespace) -> None:
    """Run the data transformation utility"""
    logger = ScraperLogger("CLI.Transform")

    try:
        # Import from the utils module
        from aliexpress_scraper.utils.transform_to_listing import main as transform_main

        # Convert args to sys.argv format
        sys.argv = ["transform_to_listing.py", args.input_file]
        if args.output_file:
            sys.argv.append(args.output_file)
        sys.argv.extend(["--source", args.source])
        if args.category:
            sys.argv.extend(["--category", args.category])
        if args.tags:
            sys.argv.extend(["--tags"] + args.tags)

        logger.start("Data transformation", f"input: {args.input_file}")

        # Run the main function
        transform_main()

    except Exception as e:
        logger.error("Data transformation failed", str(e))
        sys.exit(1)


def run_store_retry(args: argparse.Namespace) -> None:
    """Run the standalone store retry utility"""
    logger = ScraperLogger("CLI.StoreRetry")

    try:
        # Import from the utils module
        from aliexpress_scraper.utils.standalone_store_retry import main as retry_main

        # Convert args to sys.argv format
        sys.argv = ["standalone_store_retry.py", args.input_file]
        if args.output_file:
            sys.argv.append(args.output_file)
        if args.proxy_provider:
            sys.argv.extend(["--proxy-provider", args.proxy_provider])
        sys.argv.extend(["--batch-size", str(args.batch_size)])
        sys.argv.extend(["--delay", str(args.delay)])
        sys.argv.extend(["--max-workers", str(args.max_workers)])
        if args.dry_run:
            sys.argv.append("--dry-run")

        logger.start("Store retry processing", f"input: {args.input_file}")

        # Run the async main function
        retry_main()

    except Exception as e:
        logger.error("Store retry processing failed", str(e))
        sys.exit(1)


def read_queries_from_file(file_path: str) -> list[str]:
    """Read search queries from a text file, one per line"""
    logger = ScraperLogger("CLI.QueryReader")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
        return queries
    except FileNotFoundError:
        logger.error("Queries file not found", file_path)
        sys.exit(1)
    except Exception as e:
        logger.error("Error reading queries file", str(e))
        sys.exit(1)


def generate_output_filename(query: str, prefix: str = "aliexpress") -> str:
    """Generate a stable output filename for a query (no timestamp)."""
    # Clean the query for filename use
    clean_query = "".join(
        c for c in query if c.isalnum() or c in (" ", "-", "_")
    ).rstrip()
    clean_query = clean_query.replace(" ", "_").lower()

    return f"{prefix}_{clean_query}.json"


def run_single_scraper(
    args: tuple[str, MultiScraperArgset, str],
) -> tuple[str, str, bool]:
    """Run a single scraper instance for one query"""
    query, scraper_args, scraper_type = args
    logger = ScraperLogger("CLI.MultiScraper")

    try:
        logger.process("Scraper starting", f"query: '{query}'")

        # Keep track of existing files before running scraper
        results_dir: str = "results"
        existing_files: set[str] = set()
        if os.path.exists(results_dir):
            existing_files = set(os.listdir(results_dir))

        if scraper_type == "basic":
            from aliexpress_scraper.core.scraper import main as scraper_main

            # Prepare sys.argv for the scraper
            original_argv = sys.argv.copy()
            sys.argv = ["scraper.py"]
            sys.argv.extend(["--keyword", query])
            sys.argv.extend(["--brand", scraper_args.brand])
            sys.argv.extend(["--pages", str(scraper_args.pages)])

            if scraper_args.discount:
                sys.argv.append("--discount")
            if scraper_args.free_shipping:
                sys.argv.append("--free-shipping")
            if scraper_args.min_price is not None:
                sys.argv.extend(["--min-price", str(scraper_args.min_price)])
            if scraper_args.max_price is not None:
                sys.argv.extend(["--max-price", str(scraper_args.max_price)])

            sys.argv.extend(["--delay", str(scraper_args.delay)])
            sys.argv.extend(["--fields"] + scraper_args.fields)

            if scraper_args.proxy_provider:
                sys.argv.extend(["--proxy-provider", scraper_args.proxy_provider])
            if scraper_args.enable_store_retry:
                sys.argv.append("--enable-store-retry")
            sys.argv.extend(
                ["--store-retry-batch-size", str(scraper_args.store_retry_batch_size)]
            )
            sys.argv.extend(
                ["--store-retry-delay", str(scraper_args.store_retry_delay)]
            )

            # Run the scraper
            scraper_main()
            sys.argv = original_argv

        elif scraper_type == "enhanced":
            # Enhanced scraper in multi-query mode is currently not supported due to complexity
            # of running async browser automation in parallel processes
            logger.warning(
                "Enhanced scraper not supported in multi-query mode",
                f"query: '{query}'",
            )
            logger.info(
                "Recommendation: Use --scraper-type basic for multi-query operations"
            )
            logger.info(
                f'Or run enhanced scraper individually: python main.py scrape enhanced --keyword "{query}" --brand "{scraper_args.brand}"'
            )
            return query, "", False

        # Find the newly created JSON and CSV files
        new_json_file: Optional[str] = None
        new_csv_file: Optional[str] = None
        if os.path.exists(results_dir):
            current_files: set[str] = set(os.listdir(results_dir))
            new_files: set[str] = current_files - existing_files
            json_files: list[str] = [f for f in new_files if f.endswith(".json")]
            csv_files: list[str] = [f for f in new_files if f.endswith(".csv")]

            if json_files:
                # Get the most recently created JSON file
                json_files.sort(
                    key=lambda x: os.path.getmtime(os.path.join(results_dir, x)),
                    reverse=True,
                )
                new_json_file = json_files[0]
            # Prefer the CSV with the same original base name as the JSON, fall back to latest CSV
            if new_json_file:
                candidate_csv = os.path.splitext(new_json_file)[0] + ".csv"
                if candidate_csv in current_files:
                    new_csv_file = candidate_csv
                elif csv_files:
                    csv_files.sort(
                        key=lambda x: os.path.getmtime(os.path.join(results_dir, x)),
                        reverse=True,
                    )
                    new_csv_file = csv_files[0]

        if new_json_file:
            # Generate new filename based on query (no timestamp)
            new_json_filename: str = generate_output_filename(
                query, scraper_args.output_prefix
            )
            base_no_ext, _ = os.path.splitext(new_json_filename)
            new_csv_filename: str = f"{base_no_ext}.csv"

            old_json_path: str = os.path.join(results_dir, new_json_file)
            new_json_path: str = os.path.join(results_dir, new_json_filename)

            # Rename the file to include the query
            os.rename(old_json_path, new_json_path)

            # Try to rename the corresponding CSV to match the same base name
            if new_csv_file:
                old_csv_path: str = os.path.join(results_dir, new_csv_file)
                new_csv_path: str = os.path.join(results_dir, new_csv_filename)
                try:
                    os.rename(old_csv_path, new_csv_path)
                except Exception as e:
                    logger.warning(
                        "Could not rename CSV file",
                        f"'{new_csv_file}' to '{new_csv_filename}': {e}",
                    )
            else:
                logger.warning("No CSV output file found to match the renamed JSON")

            logger.success(
                "Scraping completed", f"query: '{query}' -> {new_json_filename}"
            )
            return query, new_json_filename, True
        else:
            logger.warning("No JSON output file found", f"query: '{query}'")
            return query, "", False

    except subprocess.TimeoutExpired:
        logger.error("Scraper timeout", f"query '{query}' exceeded 15 minutes")
        return query, "", False
    except Exception as e:
        logger.error("Scraper error", f"query '{query}': {e}")
        return query, "", False


def merge_json_results_to_csv(
    json_files: list[str], output_prefix: str = "aliexpress"
) -> str:
    """Merge multiple JSON result files into a single CSV and emit a merged JSON as well."""
    logger = ScraperLogger("CLI.Merge")

    try:
        # Output filenames without timestamps for stability
        csv_filename = f"{output_prefix}_merged.csv"
        json_merged_filename = f"{output_prefix}_merged.json"

        all_data: list[dict[str, Any]] = []

        # Read all JSON files
        for json_file in json_files:
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data_obj: Any = json.load(f)
                        if isinstance(data_obj, list):
                            for d in cast(list[Any], data_obj):
                                if isinstance(d, dict):
                                    all_data.append(cast(dict[str, Any], d))
                        elif isinstance(data_obj, dict):
                            all_data.append(cast(dict[str, Any], data_obj))
                except Exception as e:
                    logger.warning("Could not read JSON file", f"{json_file}: {e}")
            else:
                logger.warning("File not found", json_file)

        if not all_data:
            logger.error("No data found in any JSON files")
            return ""

        # Get all unique keys for CSV headers
        all_keys: set[str] = set()
        for item in all_data:
            all_keys.update(item.keys())

        fieldnames: list[str] = sorted(list(all_keys))

        # Write merged JSON
        os.makedirs("results", exist_ok=True)
        json_path = os.path.join("results", json_merged_filename)
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(all_data, jf, ensure_ascii=False, indent=2)

        # Write merged CSV
        csv_path = os.path.join("results", csv_filename)
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for item in all_data:
                writer.writerow(item)

        logger.success("Merged results saved", csv_path)
        logger.info("Merged JSON saved", json_path)
        logger.info("Total records", str(len(all_data)))
        return csv_path

    except Exception as e:
        logger.error("Error merging results", str(e))
        return ""


def run_multi_scraper(args: argparse.Namespace) -> None:
    """Run parallel scraping for multiple queries"""
    logger = ScraperLogger("CLI.Multi")

    try:
        logger.start("Starting parallel scraping", f"queries from: {args.queries_dir}")

        # Read queries from file
        queries: list[str] = read_queries_from_file(args.queries_dir)
        if not queries:
            logger.error("No queries found in file")
            sys.exit(1)

        logger.info("Queries found", f"{len(queries)} to process")
        logger.info("Scraper type", args.scraper_type)

        # Determine number of workers
        max_workers: int = args.max_workers if args.max_workers else mp.cpu_count()
        logger.config("Parallel workers", str(max_workers))

        # Prepare arguments for each scraper
        # Cast args to MultiScraperArgset for typing purposes
        typed_args: MultiScraperArgset = cast(MultiScraperArgset, args)
        scraper_tasks: list[tuple[str, MultiScraperArgset, str]] = [
            (query, typed_args, args.scraper_type) for query in queries
        ]

        # Run scrapers in parallel using ProcessPoolExecutor
        results: list[tuple[str, bool]] = []
        json_files: list[str] = []

        start_time = time.time()

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=max_workers
        ) as executor:
            # Submit all tasks
            future_to_query: dict[
                concurrent.futures.Future[tuple[str, str, bool]], str
            ] = {
                executor.submit(run_single_scraper, task): task[0]
                for task in scraper_tasks
            }

            # Process completed tasks
            for future in concurrent.futures.as_completed(future_to_query):
                query: str = future_to_query[future]
                try:
                    query_result, output_file, success = future.result()
                    results.append((query_result, success))
                    if success and output_file:
                        json_files.append(os.path.join("results", output_file))
                except Exception as e:
                    logger.error("Exception for query", f"'{query}': {e}")
                    results.append((query, False))

        end_time = time.time()

        # Print summary
        successful: int = sum(1 for _, success in results if success)
        failed: int = len(results) - successful

        logger.summary(
            [
                ("✅ Successful", successful),
                ("❌ Failed", failed),
                ("⏱️ Total time", f"{end_time - start_time:.2f}s"),
            ]
        )

        # Merge results into CSV if we have successful results
        if json_files:
            logger.process("Merging results", f"{len(json_files)} result files")
            csv_file = merge_json_results_to_csv(json_files, args.output_prefix)
            if csv_file:
                logger.success("Final merged results", csv_file)
            else:
                logger.error("Failed to create merged CSV file")
        else:
            logger.warning("No successful results to merge")

    except Exception as e:
        logger.error("Error in multi-scraper", str(e))
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create the main CLI parser"""
    parser = argparse.ArgumentParser(
        description="AliExpress Scraper CLI - Unified interface for all scraping operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic scraping
  %(prog)s scrape basic --keyword "gaming mouse" --brand "Logitech" --pages 3

  # Enhanced scraping with captcha solving (single keyword)
  %(prog)s scrape enhanced --keyword "mechanical keyboard" --brand "Razer" --enable-store-retry

  # Enhanced scraping with query list file
  %(prog)s scrape enhanced --queries-file queries.txt --brand "InStyler" --max-pages 2 --stream

  # Multi-query parallel scraping (basic scraper only)
  %(prog)s scrape multi --queries-dir queries/instyler.txt --brand "InStyler" --scraper-type basic

  # Transform data to listing format
  %(prog)s transform aliexpress_data.json listings.csv --category "Electronics"

  # Retry missing store information
  %(prog)s store-retry aliexpress_data.json --batch-size 10 --proxy-provider oxylabs

  # Get help for specific commands
  %(prog)s scrape basic --help
  %(prog)s scrape enhanced --help
        """,
    )

    # Create subparsers for different operations
    subparsers = parser.add_subparsers(
        title="Available operations",
        description="Choose an operation to perform",
        dest="operation",
        help="Operation to perform",
    )

    # Create scrape subparser
    scrape_parser = subparsers.add_parser(
        "scrape", help="Scraping operations", description="Run various scraper types"
    )
    scrape_subparsers = scrape_parser.add_subparsers(
        title="Scraper types",
        description="Choose a scraper type",
        dest="scraper_type",
        help="Type of scraper to run",
    )

    # Add scraper parsers
    create_basic_scraper_parser(scrape_subparsers)
    create_enhanced_scraper_parser(scrape_subparsers)
    create_multi_scraper_parser(scrape_subparsers)

    # Add utility parsers
    create_transform_parser(subparsers)
    create_store_retry_parser(subparsers)

    return parser


def main() -> None:
    """Main entry point for the CLI application"""
    logger = ScraperLogger("CLI.Main")

    parser = create_parser()
    args = parser.parse_args()

    # Handle case where no operation is specified
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    # Print header
    logger.start("AliExpress Scraper CLI")
    print("=" * 50)

    # Execute the selected function
    try:
        args.func(args)
    except KeyboardInterrupt:
        logger.warning("Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
