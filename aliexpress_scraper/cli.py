#!/usr/bin/env python3
"""
AliExpress Scraper CLI Router
============================

Central command-line interface for all AliExpress scraping operations.
This module provides a unified CLI to access all scraper and utility functionality.

Usage:
    python cli.py scrape basic --help
    python cli.py scrape enhanced --help
    python cli.py transform --help
    python cli.py store-retry --help
"""

import argparse
import asyncio
import sys
from typing import Any


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
        help="Automatically retry missing store information",
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
        help="Delay between store retry batches (default: 2.0)",
    )

    parser.set_defaults(func=run_basic_scraper)


def create_enhanced_scraper_parser(subparsers: Any) -> None:
    """Create parser for enhanced scraper functionality"""
    parser = subparsers.add_parser(
        "enhanced",
        help="Run enhanced AliExpress scraper with captcha solving",
        description="Enhanced scraper with captcha solving and advanced store retry",
    )

    # Required arguments
    parser.add_argument("--keyword", "-k", required=True, help="Search keyword")
    parser.add_argument(
        "--brand", "-b", required=True, help="Brand name to associate with products"
    )

    # Optional arguments
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

    parser.set_defaults(func=run_enhanced_scraper)


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

    parser.set_defaults(func=run_store_retry)


def run_basic_scraper(args: argparse.Namespace) -> None:
    """Run the basic scraper with provided arguments"""
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

        # Run the main function
        scraper_main()

    except Exception as e:
        print(f"❌ Error running basic scraper: {e}")
        sys.exit(1)


def run_enhanced_scraper(args: argparse.Namespace) -> None:
    """Run the enhanced scraper with provided arguments"""
    try:
        # Import from the scrapers module
        from aliexpress_scraper.scrapers.enhanced_scraper import main as enhanced_main

        # Convert args to sys.argv format
        sys.argv = ["enhanced_scraper.py"]
        sys.argv.extend(["--keyword", args.keyword])
        sys.argv.extend(["--brand", args.brand])
        sys.argv.extend(["--max-pages", str(args.max_pages)])

        if args.proxy_provider:
            sys.argv.extend(["--proxy-provider", args.proxy_provider])
        if args.disable_captcha_solver:
            sys.argv.append("--disable-captcha-solver")
        if args.captcha_solver_visible:
            sys.argv.append("--captcha-solver-visible")
        if args.discount_filter:
            sys.argv.append("--discount-filter")
        if args.free_shipping_filter:
            sys.argv.append("--free-shipping-filter")
        if args.min_price is not None:
            sys.argv.extend(["--min-price", str(args.min_price)])
        if args.max_price is not None:
            sys.argv.extend(["--max-price", str(args.max_price)])

        sys.argv.extend(["--delay", str(args.delay)])
        sys.argv.extend(["--max-retries", str(args.max_retries)])

        if args.enable_store_retry:
            sys.argv.append("--enable-store-retry")
        sys.argv.extend(["--store-retry-batch-size", str(args.store_retry_batch_size)])
        sys.argv.extend(["--store-retry-delay", str(args.store_retry_delay)])

        # Run the main function
        asyncio.run(enhanced_main())

    except Exception as e:
        print(f"❌ Error running enhanced scraper: {e}")
        sys.exit(1)


def run_transform(args: argparse.Namespace) -> None:
    """Run the data transformation utility"""
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

        # Run the main function
        transform_main()

    except Exception as e:
        print(f"❌ Error running transform utility: {e}")
        sys.exit(1)


def run_store_retry(args: argparse.Namespace) -> None:
    """Run the standalone store retry utility"""
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

        # Run the async main function
        retry_main()

    except Exception as e:
        print(f"❌ Error running store retry utility: {e}")
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

  # Enhanced scraping with captcha solving
  %(prog)s scrape enhanced --keyword "mechanical keyboard" --brand "Razer" --enable-store-retry

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

    # Add utility parsers
    create_transform_parser(subparsers)
    create_store_retry_parser(subparsers)

    return parser


def main() -> None:
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()

    # Handle case where no operation is specified
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    # Print header
    print("🚀 AliExpress Scraper CLI")
    print("=" * 50)

    # Execute the selected function
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n⚠️ Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
