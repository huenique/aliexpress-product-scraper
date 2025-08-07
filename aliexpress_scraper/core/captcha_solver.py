#!/usr/bin/env python3
"""
AliExpress Captcha Solver Module
Uses advanced techniques to automatically solve AliExpress captchas
Adapted from French programmer's solution with enhanced integration capabilities
"""

import asyncio
import random
import time
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright


class AliExpressCaptchaSolver:
    """Specialized captcha solver for AliExpress"""

    def __init__(
        self, headless: bool = True, proxy_config: dict[str, str] | None = None
    ):
        """
        Initialize the captcha solver

        Args:
            headless: Whether to run browser in headless mode
            proxy_config: Optional proxy configuration dict with keys: server, username, password
        """
        self.headless = headless
        self.proxy_config = proxy_config
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.playwright = None

    async def start_browser(self) -> None:
        """Start the browser with optimized configuration"""
        if self.browser:
            return  # Already started

        self.playwright = await async_playwright().start()

        # Browser args optimized for captcha solving
        browser_args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--disable-extensions",
            "--disable-plugins",
            "--excludeSwitches=enable-automation",
            "--useAutomationExtension=false",
        ]

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless, args=browser_args
        )

        # Context configuration
        context_options: dict[str, Any] = {
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-US",
            "timezone_id": "America/New_York",
        }

        # Add proxy configuration if provided
        if self.proxy_config:
            context_options["proxy"] = self.proxy_config

        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()

        # Hide automation indicators
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            window.chrome = {
                runtime: {},
            };
        """)

    async def close(self) -> None:
        """Clean browser shutdown"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def human_like_delay(
        self, min_delay: float = 2.0, max_delay: float = 5.0
    ) -> None:
        """Random delay to simulate human behavior"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def solve_captcha_on_url(
        self, url: str, max_attempts: int = 5
    ) -> tuple[bool, dict[str, Any]]:
        """
        Navigate to URL and solve any captcha encountered

        Args:
            url: The URL to navigate to
            max_attempts: Maximum number of captcha solving attempts

        Returns:
            Tuple of (success, session_data) where session_data contains cookies and user_agent
        """
        if not self.page:
            await self.start_browser()

        if not self.page:
            return False, {}

        try:
            print(f"🔍 Navigating to: {url}")
            await self.page.goto(url, wait_until="domcontentloaded")
            await self.human_like_delay(3, 6)

            # Handle cookie consent
            await self._handle_cookie_consent()

            # Captcha solving loop
            captcha_attempts = 0

            while captcha_attempts < max_attempts:
                # Check if we're on a valid page (products visible)
                if await self._is_on_products_page():
                    print("✅ Products page detected - no captcha needed!")
                    break

                # Check for captcha
                if await self._is_captcha_present():
                    print(
                        f"🛡️ Captcha detected (attempt {captcha_attempts + 1}/{max_attempts})"
                    )

                    success = await self._solve_slide_captcha()
                    captcha_attempts += 1

                    if success:
                        print(f"✅ Captcha solved successfully!")
                        await asyncio.sleep(3)

                        if await self._is_on_products_page():
                            print("✅ Products now visible!")
                            break
                        else:
                            print("🔄 Products not yet visible, retrying...")
                            await asyncio.sleep(2)
                    else:
                        print(
                            f"⚠️ Captcha solving failed (attempt {captcha_attempts}/{max_attempts})"
                        )
                        await asyncio.sleep(2)
                else:
                    print("⏳ Waiting for page to load...")
                    await asyncio.sleep(2)

            # Extract session data
            session_data = await self._extract_session_data()

            success = (
                captcha_attempts < max_attempts or await self._is_on_products_page()
            )

            return success, session_data

        except Exception as e:
            print(f"❌ Error during captcha solving: {str(e)}")
            return False, {}

    async def _handle_cookie_consent(self) -> None:
        """Handle cookie consent banner"""
        if not self.page:
            return

        try:
            # Wait for potential cookie banner with short timeout
            cookie_button = await self.page.wait_for_selector(
                '[data-ae-cookie-policy-accept], .btn-accept, [class*="cookie"] button',
                timeout=5000,
            )
            if cookie_button:
                await cookie_button.click()
                print("🍪 Cookie consent accepted")
                await asyncio.sleep(1)
        except:
            # No cookie banner found, continue
            pass

    async def _is_captcha_present(self) -> bool:
        """Detects the presence of a captcha on the page"""
        if not self.page:
            return False

        try:
            return await self.page.evaluate("""
                () => {
                    const captchaSelectors = [
                        '.nc_iconfont.btn_slide',
                        '.btn_slide',
                        '[class*="nc_iconfont"]',
                        '[class*="btn_slide"]',
                        'span[data-nc-lang="SLIDE"]',
                        '.nc-lang-cnt',
                        '[class*="captcha"]',
                        '[class*="slider"]',
                        '[class*="verify"]',
                        '[class*="puzzle"]',
                        'iframe[src*="captcha"]',
                        '.nc_wrapper',
                        '.nc_scale',
                        '.nc_scale_text'
                    ];
                    
                    for (const selector of captchaSelectors) {
                        if (document.querySelector(selector)) {
                            return true;
                        }
                    }
                    
                    // Check in iframes
                    const iframes = document.querySelectorAll('iframe');
                    for (const iframe of iframes) {
                        try {
                            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                            for (const selector of captchaSelectors) {
                                if (iframeDoc.querySelector(selector)) {
                                    return true;
                                }
                            }
                        } catch (e) {
                            // Ignore iframe access errors
                        }
                    }
                    
                    return false;
                }
            """)
        except Exception as e:
            print(f"⚠️ Error checking for captcha: {str(e)}")
            return False

    async def _is_on_products_page(self) -> bool:
        """Checks if we are on a valid products page"""
        if not self.page:
            return False

        try:
            return await self.page.evaluate("""
                () => {
                    // Check for product links
                    const productLinks = document.querySelectorAll('a[href*="item"]');
                    if (productLinks.length > 3) {
                        return true;
                    }
                    
                    // Check for product containers
                    const productContainers = document.querySelectorAll(
                        '[class*="product"], [class*="item"], [class*="card"], [data-spm*="item"]'
                    );
                    if (productContainers.length > 3) {
                        return true;
                    }
                    
                    // Check for product images
                    const productImages = document.querySelectorAll('img[src*="ae-pic"], img[src*="alicdn"]');
                    if (productImages.length > 5) {
                        return true;
                    }
                    
                    return false;
                }
            """)
        except Exception as e:
            print(f"⚠️ Error checking products page: {str(e)}")
            return False

    async def _solve_slide_captcha(self) -> bool:
        """Solves a slider-type captcha"""
        if not self.page:
            return False

        try:
            # Get slider information
            slider_info = await self.page.evaluate("""
                () => {
                    const slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                  document.querySelector('.btn_slide') ||
                                  document.querySelector('[class*="nc_iconfont"]') ||
                                  document.querySelector('[class*="btn_slide"]');
                    
                    if (!slider) {
                        return null;
                    }
                    
                    const container = slider.closest('[class*="nc_scale"]') || 
                                    slider.closest('[class*="slider"]') ||
                                    slider.parentElement;
                    
                    const sliderRect = slider.getBoundingClientRect();
                    const containerRect = container ? container.getBoundingClientRect() : sliderRect;
                    
                    return {
                        sliderLeft: sliderRect.left,
                        sliderTop: sliderRect.top,
                        sliderWidth: sliderRect.width,
                        sliderHeight: sliderRect.height,
                        containerLeft: containerRect.left,
                        containerWidth: containerRect.width
                    };
                }
            """)

            if not slider_info:
                print("❌ Slider not found")
                return False

            print(
                f"🎯 Slider found at position ({slider_info['sliderLeft']:.0f}, {slider_info['sliderTop']:.0f})"
            )

            # Calculate slide distance (go to the end)
            slide_distance = slider_info["containerWidth"] * 0.95  # 95% to be safe

            # Start position (center of slider)
            start_x = slider_info["sliderLeft"] + slider_info["sliderWidth"] / 2
            start_y = slider_info["sliderTop"] + slider_info["sliderHeight"] / 2

            # End position
            end_x = start_x + slide_distance

            print(
                f"🖱️ Sliding from ({start_x:.0f}, {start_y:.0f}) to ({end_x:.0f}, {start_y:.0f}) - Distance: {slide_distance:.0f}px"
            )

            # Perform the slide with human-like movement
            if not self.page:
                return False

            await self.page.mouse.move(start_x, start_y)
            await asyncio.sleep(0.2)

            # Mouse down
            await self.page.mouse.down()
            await asyncio.sleep(0.1)

            # Progressive sliding with natural acceleration/deceleration
            steps = 25
            for i in range(1, steps + 1):
                if not self.page:
                    return False

                progress = i / steps

                # Natural easing curve
                if progress < 0.3:
                    ease = progress * progress * 2.5  # Acceleration
                elif progress > 0.7:
                    ease = 1 - (1 - progress) * (1 - progress) * 2.5  # Deceleration
                else:
                    ease = progress  # Constant speed

                current_x = start_x + slide_distance * ease
                current_y = start_y + random.uniform(-1, 1)  # Slight vertical variation

                await self.page.mouse.move(current_x, current_y)
                await asyncio.sleep(random.uniform(0.015, 0.025))

            # Mouse up
            await self.page.mouse.up()
            await asyncio.sleep(1.5)

            # Check if captcha was solved
            captcha_solved = await self.page.evaluate("""
                () => {
                    // Check if captcha container disappeared
                    const captchaContainer = document.querySelector('[class*="nc_scale"]') ||
                                           document.querySelector('[class*="captcha"]') ||
                                           document.querySelector('[class*="slider"]');
                    
                    if (!captchaContainer || captchaContainer.style.display === 'none') {
                        return true;
                    }
                    
                    // Check if slider moved significantly
                    const slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                  document.querySelector('.btn_slide') ||
                                  document.querySelector('[class*="nc_iconfont"]') ||
                                  document.querySelector('[class*="btn_slide"]');
                    
                    if (slider) {
                        const style = window.getComputedStyle(slider);
                        const left = parseFloat(style.left);
                        if (left > 10) {
                            return true;
                        }
                    }
                    
                    // Check if products are visible
                    const productLinks = document.querySelectorAll('a[href*="item"]');
                    if (productLinks.length > 3) {
                        return true;
                    }
                    
                    return false;
                }
            """)

            if captcha_solved:
                print("✅ Slide successful!")
                return True
            else:
                print("❌ Slide failed, trying alternative method...")
                return await self._solve_captcha_alternative()

        except Exception as e:
            print(f"⚠️ Error solving slide captcha: {str(e)}")
            return False

    async def _solve_captcha_alternative(self) -> bool:
        """Alternative captcha solving method using JavaScript injection"""
        if not self.page:
            return False

        try:
            print("🔄 Trying JavaScript injection method...")

            success = await self.page.evaluate("""
                () => {
                    const slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                  document.querySelector('.btn_slide') ||
                                  document.querySelector('[class*="nc_iconfont"]') ||
                                  document.querySelector('[class*="btn_slide"]');
                    
                    if (!slider) {
                        return false;
                    }
                    
                    const container = slider.closest('[class*="nc_scale"]') || 
                                    slider.closest('[class*="slider"]') ||
                                    slider.parentElement;
                    
                    if (!container) {
                        return false;
                    }
                    
                    const containerWidth = container.offsetWidth || container.clientWidth;
                    const targetLeft = containerWidth * 0.98;  // 98% for safety
                    
                    // Simulate movement by changing style
                    slider.style.left = targetLeft + 'px';
                    
                    // Trigger necessary events
                    const rect = slider.getBoundingClientRect();
                    
                    // Mouse down event
                    const downEvent = new MouseEvent('mousedown', {
                        clientX: rect.x + 5,
                        clientY: rect.y + rect.height / 2,
                        bubbles: true,
                        cancelable: true
                    });
                    slider.dispatchEvent(downEvent);
                    
                    // Mouse up event after delay
                    setTimeout(() => {
                        const upEvent = new MouseEvent('mouseup', {
                            clientX: rect.x + targetLeft,
                            clientY: rect.y + rect.height / 2,
                            bubbles: true,
                            cancelable: true
                        });
                        document.dispatchEvent(upEvent);
                    }, 500);
                    
                    return true;
                }
            """)

            if success:
                await asyncio.sleep(2)

                # Verify solution
                captcha_solved = await self.page.evaluate("""
                    () => {
                        const slider = document.querySelector('.nc_iconfont.btn_slide') ||
                                      document.querySelector('.btn_slide') ||
                                      document.querySelector('[class*="nc_iconfont"]') ||
                                      document.querySelector('[class*="btn_slide"]');
                        
                        if (slider) {
                            const style = window.getComputedStyle(slider);
                            const left = parseFloat(style.left);
                            return left > 10;
                        }
                        
                        return false;
                    }
                """)

                return captcha_solved

            return False

        except Exception as e:
            print(f"⚠️ Error in alternative captcha solving: {str(e)}")
            return False

    async def _extract_session_data(self) -> dict[str, Any]:
        """Extract cookies and user agent from current session"""
        try:
            # Get cookies
            if not self.context:
                return {}
            cookies_list = await self.context.cookies()
            cookies = {
                cookie["name"]: cookie["value"]
                for cookie in cookies_list
                if "name" in cookie and "value" in cookie
            }

            # Get user agent
            if not self.page:
                return {"cookies": cookies}
            user_agent = await self.page.evaluate("() => navigator.userAgent")

            return {
                "cookies": cookies,
                "user_agent": user_agent,
                "timestamp": time.time(),
            }

        except Exception as e:
            print(f"⚠️ Error extracting session data: {str(e)}")
            return {}


class CaptchaSolverIntegration:
    """Integration helper for captcha solver with existing scraper"""

    @staticmethod
    def should_use_captcha_solver(html_content: str) -> bool:
        """
        Determine if captcha solver should be used based on page content

        Args:
            html_content: HTML content to analyze

        Returns:
            True if captcha solving is needed
        """
        captcha_indicators = [
            "captcha",
            "nc_iconfont",
            "btn_slide",
            "slider",
            "verify",
            "security",
            "challenge",
        ]

        html_lower = html_content.lower()
        return any(indicator in html_lower for indicator in captcha_indicators)

    @staticmethod
    async def solve_captcha_and_get_session(
        url: str,
        proxy_config: dict[str, str] | None = None,
        headless: bool = True,
        max_attempts: int = 5,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Convenience method to solve captcha and get session data

        Args:
            url: URL to navigate to and solve captcha
            proxy_config: Optional proxy configuration
            headless: Whether to run browser in headless mode
            max_attempts: Maximum captcha solving attempts

        Returns:
            Tuple of (success, session_data)
        """
        solver = AliExpressCaptchaSolver(headless=headless, proxy_config=proxy_config)

        try:
            success, session_data = await solver.solve_captcha_on_url(url, max_attempts)
            return success, session_data
        finally:
            await solver.close()


# Async context manager for easier usage
class CaptchaSolverContext:
    """Async context manager for captcha solver"""

    def __init__(
        self, headless: bool = True, proxy_config: dict[str, str] | None = None
    ):
        self.solver = AliExpressCaptchaSolver(
            headless=headless, proxy_config=proxy_config
        )

    async def __aenter__(self):
        await self.solver.start_browser()
        return self.solver

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.solver.close()


def main():
    """Example usage"""

    async def test_captcha_solver():
        test_url = "https://www.aliexpress.com/w/wholesale-mechanical-keyboard.html"

        (
            success,
            session_data,
        ) = await CaptchaSolverIntegration.solve_captcha_and_get_session(
            url=test_url,
            headless=False,  # Set to False to see the browser in action
            max_attempts=3,
        )

        if success:
            print("✅ Captcha solving successful!")
            print(f"📊 Extracted {len(session_data.get('cookies', {}))} cookies")
            print(f"🔧 User agent: {session_data.get('user_agent', '')[:50]}...")
        else:
            print("❌ Captcha solving failed")

    # Run test
    asyncio.run(test_captcha_solver())


if __name__ == "__main__":
    main()
