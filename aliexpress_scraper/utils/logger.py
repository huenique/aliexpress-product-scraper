#!/usr/bin/env python3
"""
Consistent Logging Utility for AliExpress Scraper
================================================

Provides standardized logging functions with consistent formatting,
emoji usage, and message structure across all modules.

Usage:
    from aliexpress_scraper.utils.logger import ScraperLogger

    logger = ScraperLogger("ModuleName")
    logger.info("Operation started", "Starting data extraction...")
    logger.success("Operation completed", f"Extracted {count} items")
    logger.error("Operation failed", f"Network error: {error}")
"""

import logging
from typing import Any, Callable, Optional


class ScraperLogger:
    """
    Standardized logger for the AliExpress scraper with consistent formatting
    """

    # Standard emoji mapping for different message types
    EMOJIS = {
        "info": "ℹ️ ",
        "success": "✅",
        "error": "❌",
        "warning": "⚠️ ",
        "debug": "🔍",
        "start": "🚀",
        "process": "🔄",
        "config": "🔧",
        "network": "🌐",
        "file": "📁",
        "save": "💾",
        "load": "📄",
        "cache": "💾",
        "retry": "🔄",
        "batch": "📦",
        "progress": "📊",
        "complete": "🎉",
        "skip": "⏭️ ",
        "wait": "⏳",
    }

    def __init__(
        self,
        module_name: str,
        log_callback: Optional[Callable[[str], None]] = None,
        use_emojis: bool = True,
    ):
        """
        Initialize logger for a specific module

        Args:
            module_name: Name of the module/component for prefixing
            log_callback: Optional callback function for custom logging
            use_emojis: Whether to include emojis in messages
        """
        self.module_name = module_name
        self.log_callback = log_callback or self._default_print
        self.use_emojis = use_emojis

        # Configure Python logger for debug output
        self.py_logger = logging.getLogger(f"aliexpress_scraper.{module_name}")

    def _default_print(self, message: str) -> None:
        """Default print function"""
        print(message)

    def _format_message(self, emoji_key: str, title: str, details: str = "") -> str:
        """
        Format a message with consistent structure

        Args:
            emoji_key: Key for emoji lookup
            title: Short title/summary of the message
            details: Optional detailed information

        Returns:
            Formatted message string
        """
        emoji = self.EMOJIS.get(emoji_key, "") if self.use_emojis else ""

        if details:
            return f"{emoji} {title}: {details}"
        else:
            return f"{emoji} {title}"

    def info(self, title: str, details: str = "") -> None:
        """Log informational message"""
        message = self._format_message("info", title, details)
        self.log_callback(message)
        self.py_logger.info(f"{title}: {details}" if details else title)

    def success(self, title: str, details: str = "") -> None:
        """Log success message"""
        message = self._format_message("success", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"SUCCESS: {title}: {details}" if details else f"SUCCESS: {title}"
        )

    def error(self, title: str, details: str = "") -> None:
        """Log error message"""
        message = self._format_message("error", title, details)
        self.log_callback(message)
        self.py_logger.error(f"{title}: {details}" if details else title)

    def warning(self, title: str, details: str = "") -> None:
        """Log warning message"""
        message = self._format_message("warning", title, details)
        self.log_callback(message)
        self.py_logger.warning(f"{title}: {details}" if details else title)

    def debug(self, title: str, details: str = "") -> None:
        """Log debug message"""
        message = self._format_message("debug", title, details)
        self.log_callback(message)
        self.py_logger.debug(f"{title}: {details}" if details else title)

    def start(self, title: str, details: str = "") -> None:
        """Log process start message"""
        message = self._format_message("start", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"START: {title}: {details}" if details else f"START: {title}"
        )

    def process(self, title: str, details: str = "") -> None:
        """Log process update message"""
        message = self._format_message("process", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"PROCESS: {title}: {details}" if details else f"PROCESS: {title}"
        )

    def config(self, title: str, details: str = "") -> None:
        """Log configuration message"""
        message = self._format_message("config", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"CONFIG: {title}: {details}" if details else f"CONFIG: {title}"
        )

    def network(self, title: str, details: str = "") -> None:
        """Log network-related message"""
        message = self._format_message("network", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"NETWORK: {title}: {details}" if details else f"NETWORK: {title}"
        )

    def file_op(self, title: str, details: str = "") -> None:
        """Log file operation message"""
        message = self._format_message("file", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"FILE: {title}: {details}" if details else f"FILE: {title}"
        )

    def save(self, title: str, details: str = "") -> None:
        """Log save operation message"""
        message = self._format_message("save", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"SAVE: {title}: {details}" if details else f"SAVE: {title}"
        )

    def load(self, title: str, details: str = "") -> None:
        """Log load operation message"""
        message = self._format_message("load", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"LOAD: {title}: {details}" if details else f"LOAD: {title}"
        )

    def cache(self, title: str, details: str = "") -> None:
        """Log cache-related message"""
        message = self._format_message("cache", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"CACHE: {title}: {details}" if details else f"CACHE: {title}"
        )

    def retry(self, title: str, details: str = "") -> None:
        """Log retry operation message"""
        message = self._format_message("retry", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"RETRY: {title}: {details}" if details else f"RETRY: {title}"
        )

    def batch(self, title: str, details: str = "") -> None:
        """Log batch processing message"""
        message = self._format_message("batch", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"BATCH: {title}: {details}" if details else f"BATCH: {title}"
        )

    def progress(self, title: str, details: str = "") -> None:
        """Log progress message"""
        message = self._format_message("progress", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"PROGRESS: {title}: {details}" if details else f"PROGRESS: {title}"
        )

    def complete(self, title: str, details: str = "") -> None:
        """Log completion message"""
        message = self._format_message("complete", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"COMPLETE: {title}: {details}" if details else f"COMPLETE: {title}"
        )

    def skip(self, title: str, details: str = "") -> None:
        """Log skip message"""
        message = self._format_message("skip", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"SKIP: {title}: {details}" if details else f"SKIP: {title}"
        )

    def wait(self, title: str, details: str = "") -> None:
        """Log wait message"""
        message = self._format_message("wait", title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"WAIT: {title}: {details}" if details else f"WAIT: {title}"
        )

    def custom(self, emoji_key: str, title: str, details: str = "") -> None:
        """Log custom message with specific emoji"""
        message = self._format_message(emoji_key, title, details)
        self.log_callback(message)
        self.py_logger.info(
            f"CUSTOM: {title}: {details}" if details else f"CUSTOM: {title}"
        )

    def section_header(self, title: str) -> None:
        """Log a section header with visual separator"""
        separator = "=" * 60
        self.log_callback(separator)
        self.log_callback(f"🚀 {title}")
        self.log_callback(separator)

    def sub_header(self, title: str) -> None:
        """Log a sub-section header"""
        separator = "-" * 40
        self.log_callback(separator)
        self.log_callback(f"📋 {title}")
        self.log_callback(separator)

    def summary(self, items: list[tuple[str, Any]]) -> None:
        """Log a summary with key-value pairs"""
        self.log_callback("📊 Summary:")
        for key, value in items:
            self.log_callback(f"   {key}: {value}")


# Convenience functions for backward compatibility
def create_logger(
    module_name: str, log_callback: Optional[Callable[[str], None]] = None
) -> ScraperLogger:
    """Create a standardized logger instance"""
    return ScraperLogger(module_name, log_callback)


def migrate_log_callback(
    log_callback: Callable[[str], None], module_name: str
) -> ScraperLogger:
    """
    Helper function to migrate existing log_callback usage to standardized logger

    Args:
        log_callback: Existing log callback function
        module_name: Name of the module

    Returns:
        Configured ScraperLogger instance
    """
    return ScraperLogger(module_name, log_callback)
