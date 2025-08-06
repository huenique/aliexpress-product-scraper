#!/usr/bin/env python3
"""
Standalone Store Retry Script

This script can be used independently to retry missing store information
for products in a JSON file that was previously scraped.

Usage:
    python standalone_store_retry.py input.json [output.json] [options]
"""

import argparse
import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

import mcp_store_scraper  # type: ignore  # noqa: F401

# Import scraper modules to register their decorators
import traditional_store_scraper  # type: ignore  # noqa: F401


def load_products_from_json(json_file: str) -> List[Dict[str, Any]]:
    """Load products from JSON file"""
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            products = json.load(f)
        print(f"✅ Loaded {len(products)} products from {json_file}")
        return products
    except Exception as e:
        print(f"❌ Error loading JSON file: {e}")
        sys.exit(1)


def save_products_to_json(products: List[Dict[str, Any]], output_file: str) -> None:
    """Save products to JSON file"""
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved {len(products)} products to {output_file}")
    except Exception as e:
        print(f"❌ Error saving JSON file: {e}")
        sys.exit(1)


def analyze_missing_store_info(products: List[Dict[str, Any]]) -> Dict[str, int]:
    """Analyze missing store information in products"""
    stats = {
        "total_products": len(products),
        "missing_store_name": 0,
        "missing_store_id": 0,
        "missing_store_url": 0,
        "missing_any_store_info": 0,
        "missing_all_store_info": 0,
    }

    for product in products:
        store_name = product.get("Store Name")
        store_id = product.get("Store ID")
        store_url = product.get("Store URL")

        missing_name = not store_name or store_name in [None, "null", "", "N/A"]
        missing_id = not store_id or store_id in [None, "null", "", "N/A"]
        missing_url = not store_url or store_url in [None, "null", "", "N/A"]

        if missing_name:
            stats["missing_store_name"] += 1
        if missing_id:
            stats["missing_store_id"] += 1
        if missing_url:
            stats["missing_store_url"] += 1
        if missing_name or missing_id or missing_url:
            stats["missing_any_store_info"] += 1
        if missing_name and missing_id and missing_url:
            stats["missing_all_store_info"] += 1

    return stats


def print_analysis(stats: Dict[str, int]) -> None:
    """Print analysis of missing store information"""
    print("\n📊 Store Information Analysis:")
    print(f"   Total products: {stats['total_products']}")
    print(f"   Missing store name: {stats['missing_store_name']}")
    print(f"   Missing store ID: {stats['missing_store_id']}")
    print(f"   Missing store URL: {stats['missing_store_url']}")
    print(f"   Missing any store info: {stats['missing_any_store_info']}")
    print(f"   Missing all store info: {stats['missing_all_store_info']}")


def test_full_store_scraping_process(
    url: str,
    proxy_provider: str = "",
    headless: bool = True,
    verbose: bool = True,
    browser_wait_seconds: int = 3,
    manual_wait: bool = False,
    enable_css: bool = False,
) -> Dict[str, Any]:
    """
    Test the full intended store scraping process using the actual TraditionalPlaywrightStoreScraper

    This ensures debugging behavior matches the real retry process exactly.

    Args:
        browser_wait_seconds: Seconds to wait before closing browser (useful for visual inspection in headed mode)
        manual_wait: If True, wait for user input before closing browser (useful for captcha solving)
        enable_css: If True, enable CSS loading for better visual inspection
    """
    try:
        from store_scraper_interface import StoreScrapingMethod, store_scraper_registry

        print(
            f"\n🎯 Full Store Scraping Process Test (Using Real TraditionalPlaywrightStoreScraper)"
        )
        print(f"   URL: {url}")
        print(f"   Headless: {headless}")
        print(f"   Proxy: {proxy_provider or 'None'}")
        print(f"   Manual Wait: {manual_wait}")
        print(f"   Enable CSS: {enable_css}")

        async def test_with_real_scraper() -> Dict[str, Any]:
            # Create the exact same scraper used in the retry process
            # For store retry, disable bandwidth optimization to allow reCAPTCHA images and resources
            scraper = store_scraper_registry.get_scraper(
                StoreScrapingMethod.TRADITIONAL_PLAYWRIGHT,
                use_oxylabs_proxy=(proxy_provider == "oxylabs"),
                headless=headless,
                extraction_timeout=15,
                navigation_timeout=45,
                retry_attempts=3,
                optimize_bandwidth=False,  # Disabled for CAPTCHA compatibility
                track_bandwidth_savings=False,  # No point if not optimizing
                enable_css=True,  # Always enable CSS for store retry
                manual_wait=manual_wait,
                browser_wait_seconds=browser_wait_seconds,
            )

            if not scraper:
                return {
                    "error": "Could not create TraditionalPlaywrightStoreScraper",
                    "success": False,
                }

            print(f"   ✅ Created TraditionalPlaywrightStoreScraper")

            try:
                # Use the actual scraper method that's used in retry process
                store_info = await scraper.scrape_single_store(url)

                # Convert StoreInfo object to dict for return
                result: Dict[str, Any] = {
                    "success": store_info.is_valid,
                    "store_name": store_info.store_name,
                    "store_id": store_info.store_id,
                    "store_url": store_info.store_url,
                    "method": store_info.extraction_method,
                    "error": store_info.error if not store_info.is_valid else None,
                }

                # Print bandwidth stats if available
                if hasattr(scraper, "get_bandwidth_stats") and callable(
                    getattr(scraper, "get_bandwidth_stats")
                ):
                    try:
                        stats = scraper.get_bandwidth_stats()  # type: ignore
                        if isinstance(stats, dict):
                            # Type cast to avoid type checker warnings
                            stats_dict: Dict[str, int] = stats  # type: ignore
                            print(
                                f"   📊 Bandwidth: {stats_dict.get('blocked_requests', 0)}/{stats_dict.get('total_requests', 0)} blocked"
                            )
                    except Exception:
                        pass  # Ignore if bandwidth stats not available

                return result

            finally:
                # Cleanup
                if hasattr(scraper, "cleanup") and callable(
                    getattr(scraper, "cleanup")
                ):
                    try:
                        await scraper.cleanup()  # type: ignore
                    except Exception:
                        pass  # Ignore cleanup errors

        # Run the async function properly
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Nested event loop - run in thread
                with ThreadPoolExecutor() as executor:

                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(test_with_real_scraper())
                        finally:
                            new_loop.close()

                    future = executor.submit(run_in_thread)
                    return future.result()
            else:
                return loop.run_until_complete(test_with_real_scraper())
        except RuntimeError:
            # No event loop
            return asyncio.run(test_with_real_scraper())

    except Exception as e:
        error_msg = f"Test failed with error: {str(e)}"
        print(f"   ❌ {error_msg}")
        if verbose:
            import traceback

            traceback.print_exc()
        return {"error": error_msg, "success": False}


def test_single_url_debug(url: str, proxy_provider: str = "") -> Dict[str, Any]:
    """Test a single URL with detailed debugging"""
    try:
        print(f"\n🔍 Debug Testing URL: {url}")
        print(f"   Proxy provider: {proxy_provider if proxy_provider else 'None'}")

        async def debug_single_url() -> Dict[str, Any]:
            # Get available scraper methods from the registry
            from store_scraper_interface import store_scraper_registry
            methods = store_scraper_registry.list_available_methods()
            print(
                f"   📋 Available scraper methods: {[str(method) for method in methods]}"
            )

            # Try each method in order of preference
            for method in methods:  # type: ignore
                print(f"\n   🧪 Testing with {method}...")

                try:
                    # Use the store_scraper_manager directly for individual method testing
                    # Disable bandwidth optimization for CAPTCHA compatibility
                    from store_scraper_interface import store_scraper_manager
                    store_info = await store_scraper_manager.scrape_store_with_fallback(
                        url, 
                        preferred_method=method,
                        optimize_bandwidth=False,  # Disabled for CAPTCHA compatibility
                        track_bandwidth_savings=False,  # No point if not optimizing
                        enable_css=True,  # Always enable CSS for store retry
                    )

                    print(
                        f"   📊 Result: {'✅ Success' if store_info.is_valid else '❌ Failed'}"
                    )
                    if store_info.is_valid:
                        print(f"      Store Name: {store_info.store_name}")
                        print(f"      Store ID: {store_info.store_id}")
                        print(f"      Store URL: {store_info.store_url}")
                        print(f"      Method: {store_info.extraction_method}")

                        return {
                            "success": True,
                            "method_used": str(method),
                            "store_name": store_info.store_name,
                            "store_id": store_info.store_id,
                            "store_url": store_info.store_url,
                            "extraction_method": store_info.extraction_method,
                        }
                    else:
                        print(f"      Error: {store_info.error}")

                except Exception as method_error:
                    print(f"   ❌ {method} failed: {str(method_error)}")
                    continue

            return {"success": False, "error": "All scraper methods failed"}

        # Run async debug
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with ThreadPoolExecutor() as executor:

                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(debug_single_url())
                        finally:
                            new_loop.close()

                    future = executor.submit(run_in_thread)
                    return future.result()
            else:
                return loop.run_until_complete(debug_single_url())
        except RuntimeError:
            return asyncio.run(debug_single_url())

    except Exception as e:
        error_msg = f"Debug test failed: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}


async def retry_store_information(
    products: List[Dict[str, Any]],
    proxy_provider: str = "",
    batch_size: int = 5,
    delay_seconds: float = 2.0,
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """
    Retry store information for products with missing data

    Args:
        products: List of product dictionaries
        proxy_provider: Optional proxy provider ("oxylabs", "massive")
        batch_size: Number of products to process simultaneously
        delay_seconds: Delay between batches
        max_retries: Maximum retry attempts per product

    Returns:
        Updated list of products with store information
    """
    print(f"\n🔄 Starting store retry process...")
    print(f"   Products to process: {len(products)}")
    print(f"   Batch size: {batch_size}")
    print(f"   Delay between batches: {delay_seconds}s")
    print(f"   Max retries: {max_retries}")
    print(f"   Proxy provider: {proxy_provider if proxy_provider else 'None'}")

    # Get available scraper methods from the registry
    from store_scraper_interface import store_scraper_registry
    methods = store_scraper_registry.list_available_methods()

    print(f"   📋 Available scraper methods: {[str(method) for method in methods]}")

    updated_products: List[Dict[str, Any]] = []
    total_success = 0
    total_failed = 0

    # Process products in batches
    for i in range(0, len(products), batch_size):
        batch = products[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(products) + batch_size - 1) // batch_size

        print(
            f"\n📦 Processing batch {batch_num}/{total_batches} ({len(batch)} products)..."
        )

        # Process batch concurrently
        batch_tasks: List[Any] = []
        for product in batch:
            product_url = product.get("Product URL", "")
            if product_url:
                # Extract product store URL or use product URL
                store_url = product_url  # Could be enhanced to extract actual store URL
                task = asyncio.create_task(
                    retry_single_product_store(
                        product,
                        store_url,
                        methods,
                        max_retries,  # type: ignore
                    )
                )
                batch_tasks.append(task)  # type: ignore
            else:
                # No URL to work with
                updated_products.append(product)

        # Wait for batch completion
        if batch_tasks:
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)  # type: ignore

            for result in batch_results:  # type: ignore
                if isinstance(result, Exception):
                    print(f"   ❌ Batch task failed: {result}")
                    total_failed += 1
                elif isinstance(result, dict):
                    updated_products.append(result)  # type: ignore
                    if result.get("_store_retry_success"):  # type: ignore
                        total_success += 1
                    else:
                        total_failed += 1

        # Delay between batches (except for last batch)
        if i + batch_size < len(products):
            print(f"   ⏱️ Waiting {delay_seconds}s before next batch...")
            await asyncio.sleep(delay_seconds)

    print(f"\n✅ Store retry process completed!")
    print(f"   Total products: {len(products)}")
    print(f"   Successful updates: {total_success}")
    print(f"   Failed updates: {total_failed}")
    print(f"   Success rate: {(total_success / len(products) * 100):.1f}%")

    return updated_products


async def retry_single_product_store(
    product: Dict[str, Any],
    store_url: str,
    methods: List[Any],  # List of scraper methods
    max_retries: int,
) -> Dict[str, Any]:
    """Retry store information for a single product"""

    # Check if store info is already complete
    store_name = product.get("Store Name")
    store_id = product.get("Store ID")
    store_url_current = product.get("Store URL")

    has_name = store_name and store_name not in [None, "null", "", "N/A"]
    has_id = store_id and store_id not in [None, "null", "", "N/A"]
    has_url = store_url_current and store_url_current not in [None, "null", "", "N/A"]

    if has_name and has_id and has_url:
        # Store info already complete
        return product

    product_name = product.get("Product Name", "Unknown Product")[:50]

    # Try to get store information
    from store_scraper_interface import store_scraper_manager
    
    for method in methods:
        for attempt in range(max_retries):
            try:
                # Disable bandwidth optimization for CAPTCHA compatibility
                store_info = await store_scraper_manager.scrape_store_with_fallback(
                    store_url, 
                    preferred_method=method,
                    optimize_bandwidth=False,  # Disabled for CAPTCHA compatibility
                    track_bandwidth_savings=False,  # No point if not optimizing
                    enable_css=True,  # Always enable CSS for store retry
                )

                if store_info.is_valid:
                    # Update product with store information
                    updated_product = product.copy()
                    if store_info.store_name and not has_name:
                        updated_product["Store Name"] = store_info.store_name
                    if store_info.store_id and not has_id:
                        updated_product["Store ID"] = store_info.store_id
                    if store_info.store_url and not has_url:
                        updated_product["Store URL"] = store_info.store_url

                    updated_product["_store_retry_success"] = True
                    updated_product["_store_retry_method"] = str(method)

                    print(f"   ✅ {product_name}: Updated with {method}")
                    return updated_product

            except Exception:
                if attempt < max_retries - 1:
                    print(
                        f"   🔄 {product_name}: {method} attempt {attempt + 1} failed, retrying..."
                    )
                    await asyncio.sleep(1)  # Brief delay before retry
                else:
                    print(
                        f"   ❌ {product_name}: {method} failed after {max_retries} attempts"
                    )

    # All methods failed
    product_copy = product.copy()
    product_copy["_store_retry_success"] = False
    print(f"   ❌ {product_name}: All methods failed")
    return product_copy


def retry_with_headed_mode(
    products: List[Dict[str, Any]], proxy_provider: str = "", failed_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Interactive retry with headed browser mode for manual intervention

    Args:
        products: Products to retry
        proxy_provider: Proxy provider to use
        failed_only: Only retry products that failed in previous attempts

    Returns:
        Updated products list
    """
    print(f"\n🖥️ Starting headed mode retry (interactive)...")

    # Filter products if needed
    if failed_only:
        retry_products = [
            p for p in products if not p.get("_store_retry_success", False)
        ]
        print(f"   📋 Products to retry (failed only): {len(retry_products)}")
    else:
        retry_products = products
        print(f"   📋 Products to retry (all): {len(retry_products)}")

    if not retry_products:
        print("   ✅ No products need retry!")
        return products

    updated_products = products.copy()

    for i, product in enumerate(retry_products):
        product_name = product.get("Product Name", "Unknown Product")[:50]
        product_url = product.get("Product URL", "")

        if not product_url:
            print(f"   ⚠️ Skipping {product_name}: No product URL")
            continue

        print(f"\n🔍 [{i + 1}/{len(retry_products)}] {product_name}")
        print(f"   URL: {product_url}")

        # Ask user if they want to try this product
        try:
            choice = input("   Try this product? (y)es, (n)o, (q)uit: ").strip().lower()
            if choice == "q":
                print("   🛑 User requested quit")
                break
            elif choice == "n":
                print("   ⏭️ Skipped")
                continue
        except KeyboardInterrupt:
            print("\n   🛑 Interrupted by user")
            break

        # Run headed test
        try:
            result = test_full_store_scraping_process(
                url=product_url,
                proxy_provider=proxy_provider,
                headless=False,  # Headed mode
                verbose=True,
                browser_wait_seconds=5,
                manual_wait=True,  # Allow manual intervention
                enable_css=True,  # Better visual inspection
            )

            if result.get("success"):
                # Update product in the main list
                for j, main_product in enumerate(updated_products):
                    if main_product.get("Product URL") == product_url:
                        if result.get("store_name"):
                            updated_products[j]["Store Name"] = result["store_name"]
                        if result.get("store_id"):
                            updated_products[j]["Store ID"] = result["store_id"]
                        if result.get("store_url"):
                            updated_products[j]["Store URL"] = result["store_url"]
                        updated_products[j]["_store_retry_success"] = True
                        updated_products[j]["_store_retry_method"] = "headed_manual"
                        break

                print(f"   ✅ Successfully updated store information!")
            else:
                print(
                    f"   ❌ Failed to get store information: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            print(f"   ❌ Headed test failed: {e}")

        # Small delay between products
        try:
            input("   Press Enter to continue to next product (or Ctrl+C to stop)...")
        except KeyboardInterrupt:
            print("\n   🛑 Interrupted by user")
            break

    return updated_products


def compare_before_after(
    original_products: List[Dict[str, Any]], updated_products: List[Dict[str, Any]]
) -> None:
    """Compare statistics before and after retry process"""
    print("\n📊 Before/After Comparison:")

    original_stats = analyze_missing_store_info(original_products)
    updated_stats = analyze_missing_store_info(updated_products)

    print(f"   Total products: {original_stats['total_products']}")
    print(
        f"   Missing store names: {original_stats['missing_store_name']} → {updated_stats['missing_store_name']} (Δ{original_stats['missing_store_name'] - updated_stats['missing_store_name']:+d})"
    )
    print(
        f"   Missing store IDs: {original_stats['missing_store_id']} → {updated_stats['missing_store_id']} (Δ{original_stats['missing_store_id'] - updated_stats['missing_store_id']:+d})"
    )
    print(
        f"   Missing store URLs: {original_stats['missing_store_url']} → {updated_stats['missing_store_url']} (Δ{original_stats['missing_store_url'] - updated_stats['missing_store_url']:+d})"
    )
    print(
        f"   Missing any store info: {original_stats['missing_any_store_info']} → {updated_stats['missing_any_store_info']} (Δ{original_stats['missing_any_store_info'] - updated_stats['missing_any_store_info']:+d})"
    )
    print(
        f"   Missing all store info: {original_stats['missing_all_store_info']} → {updated_stats['missing_all_store_info']} (Δ{original_stats['missing_all_store_info'] - updated_stats['missing_all_store_info']:+d})"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Standalone Store Retry Script for AliExpress product data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic retry with default settings
  python standalone_store_retry.py aliexpress_logitech_keyboard_extracted.json

  # Specify output file
  python standalone_store_retry.py input.json output_with_stores.json

  # Use proxy provider for better results
  python standalone_store_retry.py input.json --proxy-provider oxylabs

  # Adjust batch processing settings
  python standalone_store_retry.py input.json --batch-size 10 --delay 3.0

  # Dry run to analyze without changes
  python standalone_store_retry.py input.json --dry-run

  # Debug mode to test scraping on single URL first
  python standalone_store_retry.py input.json --debug --proxy-provider oxylabs

  # Debug with headed/visual browser mode
  python standalone_store_retry.py input.json --debug --headed

  # Debug with manual wait for CAPTCHA solving
  python standalone_store_retry.py input.json --debug --headed --manual-wait

  # Disable CSS for maximum bandwidth optimization (may break CAPTCHA)
  python standalone_store_retry.py input.json --disable-css
        """,
    )

    parser.add_argument("input_file", help="Input JSON file with product data")

    parser.add_argument(
        "output_file",
        nargs="?",
        help="Output JSON file (default: adds '_with_stores' suffix to input filename)",
    )

    parser.add_argument(
        "--proxy-provider",
        choices=["oxylabs", "massive"],
        default="",
        help="Proxy provider to use for better success rates",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of products to process simultaneously (default: 5)",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds between batches (default: 2.0)",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts per product (default: 3)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze missing data without making changes",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (test single URL first)",
    )

    parser.add_argument(
        "--headed",
        action="store_true",
        help="Use headed browser mode (only works with --debug)",
    )

    parser.add_argument(
        "--manual-wait",
        action="store_true",
        help="Enable manual wait for CAPTCHA solving (works with --debug --headed)",
    )

    parser.add_argument(
        "--disable-css",
        action="store_true",
        help="Disable CSS loading for bandwidth optimization (may break CAPTCHA)",
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Use interactive headed mode for manual retry of failed products",
    )

    args = parser.parse_args()

    # Input validation
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"❌ Input file not found: {args.input_file}")
        sys.exit(1)

    # Determine output file
    if args.output_file:
        output_file = args.output_file
    else:
        stem = input_path.stem
        suffix = input_path.suffix
        output_file = f"{stem}_with_stores{suffix}"

    print(f"🔄 Standalone Store Retry Script")
    print(f"   Input: {args.input_file}")
    print(f"   Output: {output_file}")

    # Load products
    products = load_products_from_json(args.input_file)

    # Analyze current state
    stats = analyze_missing_store_info(products)
    print_analysis(stats)

    # Dry run mode
    if args.dry_run:
        print("\n🔍 Dry run mode - no changes will be made")
        return

    # Debug mode
    if args.debug:
        print(f"\n🐛 Debug mode enabled")

        # Get a sample URL for testing
        sample_url = None
        for product in products:
            url = product.get("Product URL")
            if url:
                sample_url = url
                break

        if not sample_url:
            print("❌ No product URLs found for debugging")
            sys.exit(1)

        print(f"   Sample URL: {sample_url}")

        # Run debug test first
        if args.headed:
            # Try headed/visual mode first
            print("🖥️ Try headed/visual mode? (y/n):", end=" ")
            try:
                choice = input().strip().lower()
                if choice == "y":
                    result = test_full_store_scraping_process(
                        url=sample_url,
                        proxy_provider=args.proxy_provider,
                        headless=False,
                        verbose=True,
                        browser_wait_seconds=5,
                        manual_wait=args.manual_wait,
                        enable_css=not args.disable_css,  # CSS enabled by default
                    )
                else:
                    # Fall back to headless debug
                    result = test_single_url_debug(sample_url, args.proxy_provider)
            except KeyboardInterrupt:
                print("\n🛑 Debug cancelled by user")
                sys.exit(0)
        else:
            # Regular debug test
            result = test_single_url_debug(sample_url, args.proxy_provider)

        print(f"\n🧪 Debug result: {result}")

        if not result.get("success"):
            print(
                "❌ Debug test failed - you may want to check your setup before processing all products"
            )
            choice = input("Continue anyway? (y/n): ").strip().lower()
            if choice != "y":
                print("🛑 Exiting due to debug failure")
                sys.exit(1)
        else:
            print("✅ Debug test passed - proceeding with full retry")

    # Interactive mode
    if args.interactive:
        updated_products = retry_with_headed_mode(
            products, proxy_provider=args.proxy_provider, failed_only=True
        )
    else:
        # Regular retry mode
        print(f"\n🚀 Starting retry process...")

        try:
            updated_products = asyncio.run(
                retry_store_information(
                    products=products,
                    proxy_provider=args.proxy_provider,
                    batch_size=args.batch_size,
                    delay_seconds=args.delay,
                    max_retries=args.max_retries,
                )
            )
        except KeyboardInterrupt:
            print("\n🛑 Process interrupted by user")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Retry process failed: {e}")
            sys.exit(1)

    # Compare results
    compare_before_after(products, updated_products)

    # Save results
    save_products_to_json(updated_products, output_file)

    print(f"\n✅ Process completed successfully!")
    print(f"   Results saved to: {output_file}")


if __name__ == "__main__":
    main()
