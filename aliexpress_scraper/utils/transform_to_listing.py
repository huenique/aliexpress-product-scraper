#!/usr/bin/env python3
"""
Transform AliExpress scraper results to align with the Listing table schema.

This script reads AliExpress data and transforms it to match the expected
Listing table format for further processing.
"""

import argparse
import csv
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_price(price_str: str | None) -> float:
    """Extract numeric price from price string like 'US $42.04'."""
    if not price_str or price_str.strip() == "":
        return 0.0

    # Remove currency prefix and extract number
    price_clean = price_str.replace("US $", "").replace("$", "").strip()
    try:
        return float(price_clean)
    except ValueError:
        return 0.0


def create_price_history(sale_price: str | None, original_price: str | None) -> str:
    """Create price history JSON string from current prices."""
    current_time = datetime.now().isoformat() + "Z"
    price_history: list[dict[str, Any]] = []

    sale_price_num = parse_price(sale_price)
    if sale_price_num > 0:
        price_history.append(
            {"date": current_time, "price": sale_price_num, "currency": "USD"}
        )

    return json.dumps(price_history)


def create_image_urls_array(image_url: str | None) -> str:
    """Create image URLs JSON array from single image URL."""
    if not image_url or image_url.strip() == "":
        return "[]"

    return json.dumps([image_url])


def generate_listing_uuid() -> str:
    """Generate a new UUID for the listing."""
    return str(uuid.uuid4())


def transform_aliexpress_to_listing(
    aliexpress_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Transform AliExpress data to Listing table schema.

    Schema mapping:
    - listing_uuid: Generated UUID
    - product_uuid: null (not available in AliExpress data)
    - product_title: Title
    - product_image_urls: [Image URL] (converted to JSON array)
    - sku: null (not available)
    - asin: null (Amazon-specific)
    - item_number: Product ID
    - price: Sale Price (parsed to float)
    - price_history: Generated from current prices
    - variation_attributes: null (not available in current data)
    - units_available: null (not available)
    - units_sold: Orders Count
    - listing_status: "New" (default)
    - seller_status: "New" (default)
    - enforcement_status: "None" (default)
    - map_compliance_status: "NA" (default)
    - amazon_buy_box_won: "No" (not applicable)
    - date_first_detected: Current timestamp
    - last_checked: Current timestamp
    - authenticity: "Unverified" (default)
    - listing_note: null
    - marketplaceMarketplace_uuid: null (would need to be set based on target marketplace)
    - parent_asin: null (Amazon-specific)
    - currency: Currency
    - brand_uuid: null (would need brand mapping)
    - enforce_admin_stage: "NotSubmitted" (default)
    - listing_enforcement: "NA" (default)
    - listing_priority: false (default)
    - listing_stage: "NA" (default)
    - re_listed_status: false (default)
    - listing_url: Product URL
    - listing_state: "Active" (default)
    - brand_name: Brand (from scraper results)
    """

    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    transformed_data: list[dict[str, Any]] = []

    for item in aliexpress_data:
        # Skip items that are incomplete (only have Image URL)
        if len(item.keys()) == 1 and "Image URL" in item:
            continue

        transformed_item: dict[str, Any] = {
            "listing_uuid": generate_listing_uuid(),
            "product_uuid": None,  # Not available in AliExpress data
            "product_title": item.get("Title", ""),
            "product_image_urls": create_image_urls_array(item.get("Image URL", "")),
            "sku": None,  # Not available
            "asin": None,  # Amazon-specific
            "item_number": item.get("Product ID", ""),
            "price": parse_price(item.get("Sale Price", "")),
            "price_history": create_price_history(
                item.get("Sale Price", ""), item.get("Original Price", "")
            ),
            "variation_attributes": None,  # Not available in current data structure
            "units_available": None,  # Not available
            "units_sold": item.get("Orders Count", ""),
            "listing_status": "New",
            "seller_status": "New",
            "enforcement_status": "None",
            "map_compliance_status": "NA",
            "amazon_buy_box_won": "No",
            "date_first_detected": current_timestamp,
            "last_checked": current_timestamp,
            "authenticity": "Unverified",
            "listing_note": None,
            "marketplaceMarketplace_uuid": None,  # Would need marketplace mapping
            "parent_asin": None,  # Amazon-specific
            "currency": item.get("Currency", "USD"),
            "brand_uuid": None,  # Would need brand mapping
            "enforce_admin_stage": "NotSubmitted",
            "listing_enforcement": "NA",
            "listing_priority": False,
            "listing_stage": "NA",
            "re_listed_status": False,
            "listing_url": item.get("Product URL", ""),
            "listing_state": "Active",
            "brand_name": item.get(
                "Brand", ""
            ),  # Now using the Brand field from scraper
        }

        transformed_data.append(transformed_item)

    return transformed_data


def read_csv_data(file_path: str) -> list[dict[str, Any]]:
    """Read AliExpress data from CSV file."""
    data: list[dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            data.append(dict(row))
    return data


def read_json_data(file_path: str) -> list[dict[str, Any]]:
    """Read AliExpress data from JSON file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_to_csv(data: list[dict[str, Any]], output_path: str):
    """Write transformed data to CSV file."""
    if not data:
        print("No data to write.")
        return

    fieldnames = data[0].keys()
    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


def write_to_json(data: list[dict[str, Any]], output_path: str):
    """Write transformed data to JSON file."""
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Transform AliExpress scraper results to Listing table schema"
    )
    parser.add_argument("input_file", help="Input file path (CSV or JSON)")
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path (default: auto-generated). Format is auto-detected from extension.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["csv", "json"],
        help="Output format (default: auto-detect from output file extension, fallback to csv)",
    )

    args = parser.parse_args()

    input_path = Path(args.input_file)

    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist.")
        return

    # Determine output format
    output_format = "csv"  # default fallback

    if args.output:
        # Auto-detect format from output file extension
        output_ext = Path(args.output).suffix.lower()
        if output_ext == ".json":
            output_format = "json"
        elif output_ext == ".csv":
            output_format = "csv"
        elif args.format:
            # Use explicit format if extension is not recognized
            output_format = args.format
        else:
            # Default to csv if no extension and no format specified
            output_format = "csv"
    elif args.format:
        # Use explicit format when no output file specified
        output_format = args.format

    # Determine input format from file extension
    if input_path.suffix.lower() == ".json":
        print("Reading JSON data...")
        aliexpress_data = read_json_data(str(input_path))
    elif input_path.suffix.lower() == ".csv":
        print("Reading CSV data...")
        aliexpress_data = read_csv_data(str(input_path))
    else:
        print("Error: Input file must be .json or .csv")
        return

    print(f"Loaded {len(aliexpress_data)} items from {input_path}")

    # Transform the data
    print("Transforming data to Listing schema...")
    transformed_data = transform_aliexpress_to_listing(aliexpress_data)

    print(f"Transformed {len(transformed_data)} items")

    # Generate output filename if not provided
    if args.output:
        output_path = args.output
    else:
        output_path = input_path.stem + f"_listing_format.{output_format}"

    # Write output
    if output_format == "json":
        write_to_json(transformed_data, output_path)
    else:
        write_to_csv(transformed_data, output_path)

    print(f"Output saved to: {output_path}")

    # Print summary
    print("\n--- Transformation Summary ---")
    print(f"Input format: {input_path.suffix.upper()}")
    print(f"Output format: {output_format.upper()}")
    print(f"Records processed: {len(transformed_data)}")
    print("\nField mappings applied:")
    print("- listing_uuid: Generated UUID")
    print("- product_uuid: null (not available)")
    print("- product_title: Title")
    print("- item_number: Product ID")
    print("- price: Sale Price (parsed)")
    print("- units_sold: Orders Count")
    print("- currency: Currency")
    print("- listing_url: Product URL")
    print("- brand_name: Brand")
    print("- product_image_urls: [Image URL] (JSON array)")
    print("- price_history: Generated from current prices")
    print("- Other fields: Set to appropriate defaults")


if __name__ == "__main__":
    main()
