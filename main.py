#!/usr/bin/env python3
"""
AliExpress Scraper - Main Entry Point
====================================

This is the main entry point for the AliExpress scraper package.
It provides a unified CLI interface to all scraping and utility operations.

Usage:
    python main.py scrape basic --keyword "gaming mouse" --brand "Logitech"
    python main.py scrape enhanced --keyword "keyboard" --brand "Razer"
    python main.py transform input.json output.csv
    python main.py store-retry input.json
"""

from aliexpress_scraper.cli import main

if __name__ == "__main__":
    main()
