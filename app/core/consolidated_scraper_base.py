"""Consolidated ScraperBase class that combines all functionality from BaseScraper and mixins.
This preserves all existing scraper behavior while eliminating artificial separation.

ARCHITECTURE OVERVIEW:
This is the core of the unified scraper architecture. All agency scrapers inherit from
this single base class, which provides:

1. Browser Automation:
   - Playwright-based browser control with stealth capabilities
   - Automatic retry logic with exponential backoff
   - Screenshot/HTML capture on errors for debugging

2. Data Processing Pipeline:
   - Configurable file reading (CSV, Excel, HTML)
   - Column mapping and transformation rules
   - Date parsing with multiple format support
   - Value extraction and normalization

3. Database Integration:
   - Bulk upsert operations
   - Duplicate detection
   - File processing tracking

KEY DESIGN DECISIONS:
- Configuration-driven: All behavior controlled by ScraperConfig dataclass
- No inheritance hierarchy: Single base class with composition
- Agency-specific code minimized: Only custom transforms in subclasses
- Error resilience: Multiple retry strategies and fallbacks

USAGE PATTERN:
class AgencyScraper(ConsolidatedScraperBase):
    def __init__(self):
        config = create_agency_config()  # From config_converter
        config.base_url = active_config.AGENCY_URL
        super().__init__(config)

    # Optional: Override only for agency-specific transforms
    def custom_transform(self, df):
        return df

This architecture reduces ~20,000 lines of code to ~2,000 while maintaining
all functionality and improving maintainability.
"""

import asyncio
import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC

UTC = UTC
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import pandas as pd

# Playwright imports
from playwright.async_api import (
    Browser,
    BrowserContext,
    Download,
    Page,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from app.config import active_config
from app.database import db
from app.database.crud import bulk_upsert_prospects
from app.database.models import DataSource
from app.services.llm_service import LLMService
from app.utils.file_processing import create_processing_log, update_processing_log

# Application imports
from app.utils.logger import logger


@dataclass
class ScraperConfig:
    """Unified configuration class for scrapers.
    Combines BaseScraperConfig and DataProcessingRules functionality.
    """

    # Core identification
    source_name: str
    base_url: str | None = None
    folder_name: str | None = (
        None  # Custom folder name for file storage (defaults to sanitized source_name)
    )

    # Browser configuration
    use_stealth: bool = False
    debug_mode: bool = False  # Controls headless mode
    special_browser_args: list[str] | None = None  # For sites needing specific args

    # Timeouts (in milliseconds)
    # These defaults are based on empirical testing across all agency sites:
    # - navigation_timeout: 90s handles slow government sites during peak hours
    # - interaction_timeout: 30s for button clicks and form interactions
    # - download_timeout: 120s for large Excel/CSV files (some are 10MB+)
    # - wait_after_download: 2s ensures file is fully written to disk
    navigation_timeout_ms: int = 90000
    interaction_timeout_ms: int = 30000
    download_timeout_ms: int = 120000
    default_wait_after_download_ms: int = 2000

    # Error handling
    screenshot_on_error: bool = True
    save_html_on_error: bool = False

    # Selectors and interaction
    export_button_selector: str | None = None
    csv_button_selector: str | None = None
    pre_export_click_selector: str | None = None
    excel_link_selectors: list[str] | None = None
    download_link_text: str | None = None  # For DOC-style text-based link finding
    direct_download_url: str | None = None  # For DOS-style direct downloads

    # Wait times for specific actions
    explicit_wait_ms_before_download: int = 0
    pre_export_click_wait_ms: int = 0
    wait_after_apply_ms: int = 0

    # File reading configuration
    file_read_strategy: str = (
        "auto"  # "csv_then_excel", "html_then_excel", "excel", etc.
    )
    csv_read_options: dict[str, Any] = field(default_factory=dict)
    excel_read_options: dict[str, Any] = field(default_factory=dict)
    html_read_options: dict[str, Any] = field(default_factory=dict)
    read_options: dict[str, Any] = field(default_factory=dict)  # For general options

    # Data processing configuration
    custom_transform_functions: list[str] = field(default_factory=list)
    raw_column_rename_map: dict[str, str] = field(default_factory=dict)
    date_column_configs: list[dict[str, Any]] = field(default_factory=list)
    value_column_configs: list[dict[str, Any]] = field(default_factory=list)
    place_column_configs: list[dict[str, Any]] = field(default_factory=list)
    fiscal_year_configs: list[dict[str, Any]] = field(default_factory=list)
    db_column_rename_map: dict[str, str] = field(default_factory=dict)
    fields_for_id_hash: list[str] = field(default_factory=list)
    required_fields_for_load: list[str] | None = None
    dropna_how_all: bool = True

    # Special retry configuration (for DOT-style scrapers)
    # Some agencies (like DOT) have multiple download endpoints that may fail intermittently.
    # This allows defining a list of retry strategies with different selectors/approaches.
    # Example: [{"selector": "button.export", "wait_ms": 1000}, {"selector": "a.download", "wait_ms": 2000}]
    retry_attempts: list[dict[str, Any]] | None = None

    # New page download configuration (for DOT-style scrapers)
    new_page_download_expect_timeout_ms: int = 60000
    new_page_download_initiation_wait_ms: int = 120000
    new_page_initial_load_wait_ms: int = 5000

    def __post_init__(self):
        if not self.source_name:
            raise ValueError("source_name must be provided.")


class ConsolidatedScraperBase:
    """Consolidated scraper base class that combines functionality from:
    - BaseScraper
    - NavigationMixin
    - DownloadMixin
    - DataProcessingMixin
    - PageInteractionScraper

    Preserves all existing behavior while eliminating artificial separation.
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self.source_name = config.source_name
        self.base_url = config.base_url

        # Runtime state
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.context: BrowserContext | None = None
        self.download_dir = None
        self.last_downloaded_file = None
        self.data_source = None

        # Set up logger
        self.logger = logger.bind(
            name=f"scraper.{self.source_name.lower().replace(' ', '_')}"
        )

    # ============================================================================
    # CORE BROWSER MANAGEMENT (from BaseScraper)
    # ============================================================================

    async def setup_browser(self):
        """Initialize browser with scraper-specific configuration."""
        self.logger.info(f"Setting up browser for {self.source_name}")

        playwright = await async_playwright().start()

        # Browser arguments - start with defaults
        browser_args = [
            "--no-first-run",
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
        ]

        # Add special browser args if configured
        if self.config.special_browser_args:
            browser_args.extend(self.config.special_browser_args)
            self.logger.debug(
                f"Added special browser args: {self.config.special_browser_args}"
            )

        # Launch browser - use Firefox for HHS and Treasury if stealth is enabled
        headless = not self.config.debug_mode
        if self.config.use_stealth and "Treasury" in self.source_name:
            self.logger.info(
                f"Using Firefox for {self.source_name} to avoid bot detection"
            )
            # Firefox args for Treasury SSL issues
            firefox_args = [
                "--ignore-certificate-errors",
                "--ignore-ssl-errors",
                "--disable-web-security",
            ]
            self.browser = await playwright.firefox.launch(
                headless=headless, args=firefox_args
            )
        elif self.config.use_stealth and "Transportation" in self.source_name:
            self.logger.info(
                f"Using Chromium with enhanced SSL handling for {self.source_name}"
            )
            # Enhanced args for DOT SSL/timeout issues
            enhanced_args = [
                "--disable-web-security",
                "--ignore-certificate-errors-spki-list",
                "--ignore-ssl-errors",
                "--ignore-certificate-errors",
                "--allow-running-insecure-content",
                "--disable-features=VizDisplayCompositor",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-http2",  # DOT-specific
                "--disable-background-timer-throttling",
            ]
            self.browser = await playwright.chromium.launch(
                headless=headless, args=enhanced_args
            )
        elif (
            self.config.use_stealth and "Health and Human Services" in self.source_name
        ):
            self.logger.info(f"Using Firefox for {self.source_name} stealth mode")
            self.browser = await playwright.firefox.launch(headless=headless)
        else:
            self.browser = await playwright.chromium.launch(
                headless=headless, args=browser_args
            )

        # Create context with enhanced settings for JavaScript-heavy sites
        if self.config.use_stealth and (
            "Health and Human Services" in self.source_name
            or "Treasury" in self.source_name
        ):
            # Use Firefox user agent and headers for HHS and Treasury
            context_kwargs = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
                "java_script_enabled": True,
                "extra_http_headers": {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Cache-Control": "max-age=0",
                },
            }
            # Set appropriate referer
            if "Treasury" in self.source_name:
                context_kwargs["extra_http_headers"]["Referer"] = (
                    "https://www.treasury.gov/"
                )
            else:
                context_kwargs["extra_http_headers"]["Referer"] = "https://www.hhs.gov/"
        else:
            context_kwargs = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "java_script_enabled": True,
                "extra_http_headers": {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0",
                },
            }

        # CRITICAL: Treasury Browser State Persistence System
        #
        # Treasury's website has unique authentication challenges:
        # 1. Uses complex session management that expires quickly
        # 2. Requires specific browser fingerprinting to avoid bot detection
        # 3. May use certificate-based authentication in some environments
        #
        # Solution: We persist the browser state (cookies, localStorage, sessionStorage)
        # between scraper runs. This maintains session continuity and avoids the need
        # to re-authenticate on every run, which could trigger security measures.
        #
        # The state is saved in cleanup_browser() and loaded here. This approach is
        # ONLY used for Treasury due to its unique requirements. Other agencies don't
        # need this level of session persistence.
        if "Treasury" in self.source_name:
            import tempfile

            # Create a persistent directory for Treasury browser profile
            treasury_profile_dir = os.path.join(
                tempfile.gettempdir(), "treasury_browser_profile"
            )
            os.makedirs(treasury_profile_dir, exist_ok=True)

            context_kwargs["storage_state"] = None  # Will be set if file exists
            profile_file = os.path.join(treasury_profile_dir, "treasury_state.json")

            # Load existing state if available (cookies, localStorage, sessionStorage)
            if os.path.exists(profile_file):
                try:
                    context_kwargs["storage_state"] = profile_file
                    self.logger.info(
                        f"Loading existing browser state from {profile_file}"
                    )
                except Exception as e:
                    self.logger.warning(f"Could not load browser state: {e}")

            # Treasury's certificate configuration sometimes causes issues
            context_kwargs["ignore_https_errors"] = True

        self.context = await self.browser.new_context(**context_kwargs)

        # Apply stealth if configured
        if self.config.use_stealth:
            try:
                from playwright_stealth import stealth_async

                await stealth_async(self.context)
                self.logger.debug("Applied stealth mode")
            except ImportError:
                self.logger.warning(
                    "playwright_stealth not available, skipping stealth mode"
                )

        # Create page
        self.page = await self.context.new_page()

        # Set additional page-level headers and user agent for enhanced stealth
        if self.config.use_stealth:
            await self.page.set_extra_http_headers(
                {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="120", "Chromium";v="120"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                }
            )

            # ANTI-BOT DETECTION: Enhanced navigator properties
            # Many government websites check for automated browsers using navigator.webdriver
            # and other fingerprinting techniques. This script modifies the browser's
            # JavaScript environment to appear more like a regular user's browser.
            # DO NOT REMOVE - Several agencies will block access without these modifications.
            await self.page.add_init_script(
                """
                // Comprehensive webdriver hiding
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                delete navigator.__proto__.webdriver;

                // Enhanced plugin system
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });

                // Realistic language settings
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });

                // Enhanced hardware properties
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 4,
                });

                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8,
                });

                // Realistic screen properties
                Object.defineProperty(screen, 'availWidth', {
                    get: () => 1920,
                });

                Object.defineProperty(screen, 'availHeight', {
                    get: () => 1040,
                });

                // Enhanced Chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                };

                // Mock permissions API to appear more realistic
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                // Canvas fingerprint spoofing with slight noise injection
                const getImageData = HTMLCanvasElement.prototype.getImageData;
                HTMLCanvasElement.prototype.getImageData = function(sx, sy, sw, sh) {
                    const imageData = getImageData.apply(this, arguments);
                    // Add minimal noise to prevent fingerprinting
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] += Math.floor(Math.random() * 3) - 1;
                        imageData.data[i + 1] += Math.floor(Math.random() * 3) - 1;
                        imageData.data[i + 2] += Math.floor(Math.random() * 3) - 1;
                    }
                    return imageData;
                };

                // WebGL fingerprint protection
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.';
                    }
                    if (parameter === 37446) {
                        return 'Intel(R) Iris(TM) Graphics 6100';
                    }
                    return getParameter.apply(this, [parameter]);
                };
            """
            )

        # Set timeouts
        self.page.set_default_navigation_timeout(self.config.navigation_timeout_ms)
        self.page.set_default_timeout(self.config.interaction_timeout_ms)

        # Set up download handling
        self._setup_download_handling()

        self.logger.info("Browser setup completed")

    def _setup_download_handling(self):
        """Configure download event handling."""
        # Create download directory
        # Use custom folder name if provided, otherwise sanitize source name
        self.folder_name = self.config.folder_name or self.source_name.lower().replace(
            " ", "_"
        )
        self.download_dir = os.path.join(active_config.RAW_DATA_DIR, self.folder_name)
        os.makedirs(self.download_dir, exist_ok=True)

        # Register download handler
        self.page.on("download", self._handle_download_event)

    async def _handle_download_event(self, download: Download):
        """Handle Playwright download events."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Get suggested filename or generate one
            suggested_filename = download.suggested_filename
            if suggested_filename:
                name, ext = os.path.splitext(suggested_filename)
                filename = f"{self.folder_name}_{timestamp}{ext}"
            else:
                filename = f"{self.folder_name}_{timestamp}.csv"

            filepath = os.path.join(self.download_dir, filename)
            await download.save_as(filepath)

            self.last_downloaded_file = filepath
            self.logger.info(f"Downloaded file saved: {filepath}")

        except Exception as e:
            self.logger.error(f"Error handling download: {e}")
            raise

    async def cleanup_browser(self):
        """Clean up browser resources."""
        # CRITICAL: Treasury Browser State Persistence - DO NOT REMOVE
        # The Treasury website uses complex authentication and session management that
        # can cause issues with repeated scraping attempts. By persisting the browser
        # state (cookies, localStorage, sessionStorage), we maintain session continuity
        # between scraper runs, reducing authentication failures and improving reliability.
        #
        # This state includes:
        # - Authentication cookies that may have long expiration times
        # - Session tokens stored in localStorage
        # - User preferences that affect data presentation
        #
        # The temporary directory is used to avoid permission issues and ensure
        # the state file is accessible across different execution contexts.
        if "Treasury" in self.source_name and self.context:
            try:
                import tempfile

                treasury_profile_dir = os.path.join(
                    tempfile.gettempdir(), "treasury_browser_profile"
                )
                os.makedirs(treasury_profile_dir, exist_ok=True)
                profile_file = os.path.join(treasury_profile_dir, "treasury_state.json")

                # Save current browser state (cookies, localStorage, etc.)
                await self.context.storage_state(path=profile_file)
                self.logger.info(f"Saved browser state to {profile_file}")
            except Exception as e:
                # Non-fatal: Treasury scraper will work without state, just less efficiently
                self.logger.warning(f"Could not save browser state: {e}")

        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        self.logger.debug("Browser cleanup completed")

    async def capture_error_info(self, error: Exception, prefix: str = "error"):
        """Capture screenshots and HTML for debugging."""
        try:
            if self.page and self.config.screenshot_on_error:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(
                    active_config.ERROR_SCREENSHOTS_DIR,
                    f"{prefix}_{self.folder_name}_{timestamp}.png",
                )
                await self.page.screenshot(path=screenshot_path, full_page=True)
                self.logger.info(f"Error screenshot saved: {screenshot_path}")

            if self.page and self.config.save_html_on_error:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                html_path = os.path.join(
                    active_config.ERROR_HTML_DIR,
                    f"{prefix}_{self.folder_name}_{timestamp}.html",
                )
                html_content = await self.page.content()
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                self.logger.info(f"Error HTML saved: {html_path}")

        except Exception as capture_error:
            self.logger.warning(f"Failed to capture error info: {capture_error}")

    # ============================================================================
    # NAVIGATION FUNCTIONALITY (from NavigationMixin)
    # ============================================================================

    async def navigate_to_url(self, url: str, wait_until: str = "networkidle") -> bool:
        """Navigate to URL with enhanced error handling and wait state control.

        Args:
            url: URL to navigate to
            wait_until: Wait state ('load', 'domcontentloaded', 'networkidle')

        Returns:
            bool: Success status
        """
        try:
            self.logger.info(f"Navigating to: {url}")

            response = await self.page.goto(
                url, wait_until=wait_until, timeout=self.config.navigation_timeout_ms
            )

            # CRITICAL: HHS 404 Handling - DO NOT REMOVE
            # The HHS website has a known issue where their forecast page returns a 404 HTTP status
            # code even when the page loads successfully with all the required data. This appears
            # to be a misconfiguration on their server. Without this special handling, the scraper
            # would fail even though the data is actually available.
            #
            # The 1000-character threshold was determined through testing - HHS error pages are
            # typically under 500 characters, while valid forecast pages with data tables are
            # always over 5000 characters. The 1000-character check provides a safe margin.
            if response and response.status >= 400:
                self.logger.warning(f"Navigation returned status {response.status}")
                # For HHS, check if content is actually loaded despite the status code
                if (
                    "Health and Human Services" in self.source_name
                    and response.status == 404
                ):
                    self.logger.info(
                        "HHS returned 404 but checking if content is loaded..."
                    )
                    # Give it a moment to load - HHS uses client-side rendering
                    await self.wait_for_timeout(1000)
                    # Check if we have the expected content by looking for substantial HTML
                    try:
                        page_content = await self.page.content()
                        if (
                            len(page_content) > 1000
                        ):  # Valid pages are >5000 chars, errors <500
                            self.logger.info(
                                "HHS page has content despite 404 status, continuing..."
                            )
                            return True
                    except:
                        pass
                return False

            self.logger.debug(f"Navigation successful to {url}")
            return True

        except PlaywrightTimeoutError as e:
            self.logger.error(f"Navigation timeout to {url}: {e}")
            await self.capture_error_info(e, "navigation_timeout")
            return False
        except Exception as e:
            self.logger.error(f"Navigation error to {url}: {e}")
            await self.capture_error_info(e, "navigation_error")
            return False

    # ============================================================================
    # ENHANCED ANTI-BOT FUNCTIONALITY
    # ============================================================================

    async def scroll_into_view(
        self, selector: str, behavior: str = "smooth", block: str = "center"
    ) -> bool:
        """Scroll element into viewport before interaction to mimic human behavior.

        Args:
            selector: CSS selector or XPath of element to scroll to
            behavior: Scroll behavior ('auto', 'smooth')
            block: Vertical alignment ('start', 'center', 'end', 'nearest')

        Returns:
            bool: Success status
        """
        try:
            self.logger.debug(f"Scrolling element into view: {selector}")

            # Detect if selector is XPath
            is_xpath = selector.startswith("//") or selector.startswith("xpath=")

            if is_xpath:
                xpath = selector.replace("xpath=", "")
                await self.page.evaluate(
                    """
                    (xpath, behavior, block) => {
                        const element = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                        if (element) {
                            element.scrollIntoView({ behavior: behavior, block: block });
                        }
                    }
                """,
                    xpath,
                    behavior,
                    block,
                )
            else:
                await self.page.evaluate(
                    f"""
                    const element = document.querySelector('{selector}');
                    if (element) {{
                        element.scrollIntoView({{ behavior: '{behavior}', block: '{block}' }});
                    }}
                """
                )

            # Wait for scroll animation to complete
            await self.wait_for_timeout(1000)
            self.logger.debug(f"Successfully scrolled to element: {selector}")
            return True

        except Exception as e:
            self.logger.error(f"Error scrolling to element {selector}: {e}")
            return False

    async def human_like_hover(self, selector: str) -> bool:
        """Hover over element with human-like mouse movement to avoid bot detection.

        Args:
            selector: CSS selector or XPath of element to hover

        Returns:
            bool: Success status
        """
        try:
            self.logger.debug(f"Hovering over element: {selector}")

            # Detect if selector is XPath and convert for locator
            if selector.startswith("//") or selector.startswith("xpath="):
                if not selector.startswith("xpath="):
                    selector = f"xpath={selector}"
                locator = self.page.locator(selector)
            else:
                locator = self.page.locator(selector)

            # Get element bounding box
            box = await locator.bounding_box()
            if not box:
                self.logger.warning(f"Could not get bounding box for {selector}")
                return False

            # Add slight randomization to hover position
            import random

            x = box["x"] + box["width"] / 2 + random.randint(-5, 5)
            y = box["y"] + box["height"] / 2 + random.randint(-5, 5)

            # Move mouse to element with human-like timing
            await self.page.mouse.move(x, y)
            await self.wait_for_timeout(random.randint(100, 300))

            self.logger.debug(f"Successfully hovered over element: {selector}")
            return True

        except Exception as e:
            self.logger.error(f"Error hovering over {selector}: {e}")
            return False

    async def random_wait(self, min_ms: int = 1000, max_ms: int = 3000) -> None:
        """Wait for a random amount of time to mimic human behavior.

        Args:
            min_ms: Minimum wait time in milliseconds
            max_ms: Maximum wait time in milliseconds
        """
        import random

        wait_time = random.randint(min_ms, max_ms)
        self.logger.debug(f"Random wait: {wait_time}ms")
        await self.wait_for_timeout(wait_time)

    async def enhanced_click_element(
        self,
        selector: str,
        ensure_visible: bool = True,
        use_js: bool = False,
        timeout: int | None = None,
        js_click_fallback: bool = True,
    ) -> bool:
        """Enhanced click with visibility checks, scrolling, and human-like behavior.

        Args:
            selector: CSS selector or XPath
            ensure_visible: Whether to scroll element into view and hover before clicking
            use_js: Use JavaScript click instead of Playwright click
            timeout: Custom timeout for this operation
            js_click_fallback: Use JS fallback if regular click fails

        Returns:
            bool: Success status
        """
        timeout = timeout or self.config.interaction_timeout_ms

        try:
            self.logger.debug(f"Enhanced clicking element: {selector}")

            # Detect if selector is XPath
            is_xpath = selector.startswith("//") or selector.startswith("xpath=")
            if is_xpath and not selector.startswith("xpath="):
                selector = f"xpath={selector}"

            if ensure_visible:
                # Scroll element into view
                await self.scroll_into_view(selector)

                # Hover over element to mimic human behavior
                await self.human_like_hover(selector)

                # Wait for element to be truly visible and stable
                await self.page.wait_for_selector(
                    selector, state="visible", timeout=timeout
                )

                # Ensure element is not moving (check stability)
                if is_xpath:
                    xpath_clean = selector.replace("xpath=", "")
                    await self.page.wait_for_function(
                        """
                        (xpath) => {
                            const el = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                            return el && el.offsetWidth > 0 && el.offsetHeight > 0;
                        }
                    """,
                        xpath_clean,
                        timeout=timeout,
                    )
                else:
                    await self.page.wait_for_function(
                        f"""
                        () => {{
                            const el = document.querySelector('{selector}');
                            return el && el.offsetWidth > 0 && el.offsetHeight > 0;
                        }}
                    """,
                        timeout=timeout,
                    )

            # Add small random delay before click
            await self.random_wait(200, 800)

            # Use the existing click_element method with fallback enabled
            return await self.click_element(
                selector,
                use_js=use_js,
                timeout=timeout,
                js_click_fallback=js_click_fallback,
            )

        except Exception as e:
            self.logger.error(f"Enhanced click failed for {selector}: {e}")
            await self.capture_error_info(e, "enhanced_click_error")
            return False

    async def click_element(
        self,
        selector: str,
        use_js: bool = False,
        timeout: int | None = None,
        js_click_fallback: bool = False,
    ) -> bool:
        """Click an element with robust error handling and JS fallback.

        Args:
            selector: CSS selector or XPath
            use_js: Use JavaScript click instead of Playwright click
            timeout: Custom timeout for this operation

        Returns:
            bool: Success status
        """
        timeout = timeout or self.config.interaction_timeout_ms

        try:
            self.logger.debug(f"Clicking element: {selector}")

            # Detect if selector is XPath
            is_xpath = selector.startswith("//") or selector.startswith("xpath=")
            if is_xpath and not selector.startswith("xpath="):
                selector = f"xpath={selector}"

            # Wait for element to be visible
            await self.page.wait_for_selector(
                selector, state="visible", timeout=timeout
            )

            if use_js:
                # Use JavaScript click
                if is_xpath:
                    # For XPath, need to use evaluate with XPath - escape quotes properly
                    xpath = selector.replace("xpath=", "").replace("'", "\\'")
                    await self.page.evaluate(
                        f"document.evaluate('{xpath}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.click()"
                    )
                else:
                    await self.page.evaluate(
                        f"document.querySelector('{selector}').click()"
                    )
                self.logger.debug(f"JavaScript click successful on {selector}")
            else:
                try:
                    # Use Playwright click
                    await self.page.click(selector, timeout=timeout)
                    self.logger.debug(f"Playwright click successful on {selector}")
                except Exception as click_error:
                    if js_click_fallback:
                        self.logger.info(
                            f"Playwright click failed, trying JS fallback for {selector}"
                        )
                        if is_xpath:
                            xpath = selector.replace("xpath=", "").replace("'", "\\'")
                            await self.page.evaluate(
                                f"document.evaluate('{xpath}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.click()"
                            )
                        else:
                            await self.page.evaluate(
                                f"document.querySelector('{selector}').click()"
                            )
                        self.logger.debug(f"JS fallback click successful on {selector}")
                    else:
                        raise click_error

            return True

        except PlaywrightTimeoutError as e:
            self.logger.error(f"Click timeout on {selector}: {e}")
            await self.capture_error_info(e, "click_timeout")
            return False
        except Exception as e:
            self.logger.error(f"Click error on {selector}: {e}")
            await self.capture_error_info(e, "click_error")
            return False

    async def wait_for_selector(
        self, selector: str, state: str = "visible", timeout: int | None = None
    ) -> bool:
        """Wait for element to reach specified state.

        Args:
            selector: CSS selector or XPath
            state: Element state ('visible', 'hidden', 'attached', 'detached')
            timeout: Custom timeout for this operation

        Returns:
            bool: Success status
        """
        timeout = timeout or self.config.interaction_timeout_ms

        try:
            self.logger.debug(f"Waiting for selector {selector} to be {state}")
            await self.page.wait_for_selector(selector, state=state, timeout=timeout)
            self.logger.debug(f"Selector {selector} reached state {state}")
            return True

        except PlaywrightTimeoutError as e:
            self.logger.warning(f"Timeout waiting for {selector} to be {state}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error waiting for {selector}: {e}")
            return False

    async def fill_input(
        self, selector: str, text: str, timeout: int | None = None
    ) -> bool:
        """Fill an input field with text."""
        timeout = timeout or self.config.interaction_timeout_ms

        try:
            await self.page.wait_for_selector(
                selector, state="visible", timeout=timeout
            )
            await self.page.fill(selector, text)
            self.logger.debug(f"Filled input {selector} with text")
            return True

        except Exception as e:
            self.logger.error(f"Error filling input {selector}: {e}")
            return False

    async def get_element_attribute(
        self, selector: str, attribute: str, timeout: int | None = None
    ) -> str | None:
        """Get attribute value from an element."""
        timeout = timeout or self.config.interaction_timeout_ms

        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return await self.page.get_attribute(selector, attribute)
        except Exception as e:
            self.logger.error(
                f"Error getting attribute {attribute} from {selector}: {e}"
            )
            return None

    async def get_element_text(
        self, selector: str, timeout: int | None = None
    ) -> str | None:
        """Get text content from an element."""
        timeout = timeout or self.config.interaction_timeout_ms

        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return await self.page.text_content(selector)
        except Exception as e:
            self.logger.error(f"Error getting text from {selector}: {e}")
            return None

    async def wait_for_load_state(
        self, state: str = "networkidle", timeout: int | None = None
    ):
        """Wait for page to reach specified load state."""
        timeout = timeout or self.config.navigation_timeout_ms

        try:
            await self.page.wait_for_load_state(state, timeout=timeout)
            self.logger.debug(f"Page reached load state: {state}")
        except Exception as e:
            self.logger.warning(f"Timeout waiting for load state {state}: {e}")

    async def wait_for_timeout(self, timeout_ms: int):
        """Explicit wait for specified time."""
        self.logger.debug(f"Waiting for {timeout_ms}ms")
        await self.page.wait_for_timeout(timeout_ms)

    # ============================================================================
    # DOWNLOAD FUNCTIONALITY (from DownloadMixin)
    # ============================================================================

    async def download_file_via_click(
        self,
        selector: str,
        pre_click_selector: str | None = None,
        wait_after_click: int = 0,
        timeout: int | None = None,
        js_click_fallback: bool = False,
    ) -> str | None:
        """Download file by clicking a button/link.

        Args:
            selector: Selector for download button/link
            pre_click_selector: Optional selector to click before main download
            wait_after_click: Time to wait after clicking (ms)
            timeout: Download timeout

        Returns:
            str: Path to downloaded file, or None if failed
        """
        timeout = timeout or self.config.download_timeout_ms

        try:
            self.logger.info(f"Starting download via click on {selector}")

            # Pre-click action if specified
            if pre_click_selector:
                await self.click_element(pre_click_selector)
                await self.wait_for_timeout(1000)  # Brief pause

            # Set up download expectation
            async with self.page.expect_download(timeout=timeout) as download_info:
                # Click the download element
                success = await self.click_element(
                    selector, js_click_fallback=js_click_fallback
                )
                if not success:
                    self.logger.error("Failed to click download element")
                    return None

                # Wait after click if specified
                if wait_after_click > 0:
                    await self.wait_for_timeout(wait_after_click)

            # Get the download and handle it
            download = await download_info.value
            await self._handle_download_event(download)

            return self.last_downloaded_file

        except PlaywrightTimeoutError as e:
            self.logger.error(f"Download timeout: {e}")
            await self.capture_error_info(e, "download_timeout")
            return None
        except Exception as e:
            self.logger.error(f"Download error: {e}")
            await self.capture_error_info(e, "download_error")
            return None

    async def download_file_directly(
        self, url: str, filename: str | None = None
    ) -> str | None:
        """Download file directly via HTTP request.

        Args:
            url: Direct download URL
            filename: Optional custom filename

        Returns:
            str: Path to downloaded file, or None if failed
        """
        try:
            self.logger.info(f"Starting direct download from {url}")

            # Create API request context
            request_context = self.context.request

            # Make the request
            response = await request_context.get(url)

            if response.status != 200:
                self.logger.error(f"Download failed with status {response.status}")
                return None

            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                parsed_url = urlparse(url)
                original_name = os.path.basename(parsed_url.path) or "download"
                name, ext = os.path.splitext(original_name)
                filename = f"{self.folder_name}_{timestamp}{ext}"

            # Save file
            filepath = os.path.join(self.download_dir, filename)
            content = await response.body()

            with open(filepath, "wb") as f:
                f.write(content)

            self.last_downloaded_file = filepath
            self.logger.info(f"Direct download completed: {filepath}")
            return filepath

        except Exception as e:
            self.logger.error(f"Direct download error: {e}")
            return None

    async def download_file_via_new_page(self, selector: str) -> str | None:
        """Download file by clicking a link that opens a new page/tab.
        Specialized for DOT-style downloads.
        """
        try:
            self.logger.info(f"Starting new page download via selector: {selector}")

            # Wait for the download link to be visible
            if not await self.wait_for_selector(selector, state="visible"):
                self.logger.error(
                    f"Download link '{selector}' not found or not visible"
                )
                return None

            self.logger.info("Download link is visible.")

            new_page = None
            downloaded_file_path = None

            try:
                # Expect a new page to open when clicking the link
                async with self.context.expect_page(
                    timeout=self.config.new_page_download_expect_timeout_ms
                ) as new_page_info:
                    await self.click_element(selector)

                new_page = await new_page_info.value
                self.logger.info(f"New page opened for download, URL: {new_page.url}")

                # Register download handler for the new page
                new_page.on("download", self._handle_download_event)

                # Wait for download to initiate on the new page
                async with new_page.expect_download(
                    timeout=self.config.new_page_download_initiation_wait_ms
                ) as download_info:
                    self.logger.info("Waiting for download to initiate on new page...")
                    await new_page.wait_for_timeout(
                        self.config.new_page_initial_load_wait_ms
                    )

                download = await download_info.value
                await self._handle_download_event(download)

                # Wait for event processing
                await self.wait_for_timeout(self.config.default_wait_after_download_ms)

                if self.last_downloaded_file and os.path.exists(
                    self.last_downloaded_file
                ):
                    downloaded_file_path = self.last_downloaded_file
                    self.logger.info(f"Download successful: {downloaded_file_path}")
                else:
                    # Fallback: manually save from Playwright temp path
                    self.logger.warning(
                        "Download event didn't set path, attempting manual save"
                    )
                    temp_path = await download.path()
                    if temp_path and os.path.exists(temp_path):
                        import shutil

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{self.folder_name}_{timestamp}.csv"
                        final_path = os.path.join(self.download_dir, filename)

                        shutil.copy2(temp_path, final_path)
                        self.last_downloaded_file = final_path
                        downloaded_file_path = final_path
                        self.logger.info(f"Manually saved download: {final_path}")

                return downloaded_file_path

            except Exception as e:
                self.logger.error(f"Error during new page download: {e}")
                await self.capture_error_info(e, "new_page_download_error")

                # Try to capture screenshot from new page if it exists
                if new_page and not new_page.is_closed():
                    try:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        screenshot_path = os.path.join(
                            active_config.ERROR_SCREENSHOTS_DIR,
                            f"new_page_download_error_{self.folder_name}_{timestamp}.png",
                        )
                        await new_page.screenshot(path=screenshot_path)
                        self.logger.info(
                            f"Saved new page screenshot: {screenshot_path}"
                        )
                    except Exception as screenshot_error:
                        self.logger.warning(
                            f"Failed to capture new page screenshot: {screenshot_error}"
                        )

                return None

            finally:
                if new_page and not new_page.is_closed():
                    await new_page.close()
                    self.logger.info("Closed the new page used for download")

        except Exception as e:
            self.logger.error(f"New page download error: {e}")
            await self.capture_error_info(e, "new_page_download_setup_error")
            return None

    async def find_excel_link(self) -> str | None:
        """Find Excel file link on the page using configured selectors.
        Used for SSA-style scrapers that need to find Excel download links.
        """
        if not self.config.excel_link_selectors:
            self.logger.warning("No Excel link selectors configured")
            return None

        self.logger.info("Searching for Excel download link...")

        for selector in self.config.excel_link_selectors:
            self.logger.debug(f"Trying selector for Excel link: {selector}")
            try:
                # Use Playwright to find elements
                elements = await self.page.query_selector_all(selector)
                if elements:
                    self.logger.debug(
                        f"Found {len(elements)} links with selector '{selector}'. Checking hrefs."
                    )
                    for element in elements:
                        href = await element.get_attribute("href")
                        if href and any(
                            ext in href.lower()
                            for ext in [".xls", ".xlsx", ".xlsm", "forecast"]
                        ):
                            # Convert to absolute URL
                            absolute_href = self.page.url
                            if href.startswith("http"):
                                absolute_href = href
                            else:
                                from urllib.parse import urljoin

                                absolute_href = urljoin(self.page.url, href)

                            self.logger.info(
                                f"Found Excel link: {absolute_href} (from original href: {href})"
                            )
                            return absolute_href
            except Exception as e:
                self.logger.warning(f"Error while querying selector '{selector}': {e}")
                continue

        self.logger.warning(
            "Could not find any Excel download link using configured selectors."
        )
        return None

    async def find_link_by_text(
        self, link_text: str, timeout_ms: int = 30000
    ) -> str | None:
        """Find download link by text content and return its href.
        Used for DOC-style scrapers that need to find links by text.
        """
        self.logger.info(f"Looking for link with text: '{link_text}'")

        try:
            # Create selector for link containing the text
            link_selector = f'a:has-text("{link_text}")'

            # Wait for the link to be visible
            await self.wait_for_selector(
                link_selector, state="visible", timeout=timeout_ms
            )

            # Get the first matching element
            link_locator = self.page.locator(link_selector).first

            # Get href attribute
            href = await link_locator.get_attribute("href")
            if not href:
                self.logger.error(
                    f"Link with text '{link_text}' found but has no href attribute"
                )
                return None

            # Convert to absolute URL if needed
            if href.startswith("http"):
                absolute_url = href
            else:
                from urllib.parse import urljoin

                absolute_url = urljoin(self.page.url, href)

            self.logger.info(f"Found link with text '{link_text}': {absolute_url}")
            return absolute_url

        except Exception as e:
            self.logger.error(f"Error finding link with text '{link_text}': {e}")
            await self.capture_error_info(
                e, f"find_link_by_text_{link_text.replace(' ', '_')}"
            )
            return None

    def get_last_downloaded_path(self) -> str | None:
        """Get path to the most recently downloaded file."""
        if self.last_downloaded_file and os.path.exists(self.last_downloaded_file):
            return self.last_downloaded_file

        # Fallback: find most recent file in download directory
        if self.download_dir and os.path.exists(self.download_dir):
            files = [
                f
                for f in os.listdir(self.download_dir)
                if os.path.isfile(os.path.join(self.download_dir, f))
            ]
            if files:
                files.sort(
                    key=lambda x: os.path.getmtime(os.path.join(self.download_dir, x)),
                    reverse=True,
                )
                most_recent = os.path.join(self.download_dir, files[0])
                self.logger.info(f"Using most recent file: {most_recent}")
                return most_recent

        return None

    async def download_with_fallback(self, selector: str, **kwargs) -> str | None:
        """Download file with automatic fallback to last successful file.

        This method tries to download a file normally, and if that fails,
        falls back to using the most recent successfully processed file
        from the same data source.

        Args:
            selector: CSS selector for download button/link
            **kwargs: Additional arguments passed to download_file_via_click

        Returns:
            str: Path to downloaded file (new or fallback), or None if both fail
        """
        self.logger.info(f"Starting download with fallback for selector: {selector}")

        # Try normal download first
        result = await self.download_file_via_click(selector, **kwargs)

        if result:
            self.logger.info(f"Download successful: {result}")
            return result

        self.logger.warning("Download failed, attempting to use fallback file")

        # Get data source for fallback lookup
        data_source = self._get_data_source()
        if not data_source:
            self.logger.error("Could not determine data source for fallback")
            return None

        # Get last successful file using existing validation service
        from app.utils.file_processing import (
            get_recent_files_for_source,
        )

        try:
            recent_logs = get_recent_files_for_source(data_source.id, 1)
            fallback_files = [log.file_path for log in recent_logs if log.success]

            if fallback_files and os.path.exists(fallback_files[0]):
                fallback_path = fallback_files[0]
                self.logger.warning(
                    f"Using database-tracked fallback file: {fallback_path}"
                )

                # Update last_downloaded_file to point to fallback
                self.last_downloaded_file = fallback_path

                # Log fallback usage for monitoring
                self.logger.warning(
                    f"FALLBACK USED (DB): {self.source_name} scraper used database-tracked fallback file due to download failure"
                )

                return fallback_path
            self.logger.warning(
                "No database-tracked fallback file found, trying filesystem scan"
            )

        except Exception as e:
            self.logger.error(f"Error accessing database fallback file: {e}")

        # Database fallback failed, try filesystem-based fallback
        filesystem_fallback = self._find_filesystem_fallback()
        if filesystem_fallback:
            self.logger.warning(
                f"Using filesystem-scanned fallback file: {filesystem_fallback}"
            )

            # Update last_downloaded_file to point to fallback
            self.last_downloaded_file = filesystem_fallback

            # Log fallback usage for monitoring
            self.logger.warning(
                f"FALLBACK USED (FS): {self.source_name} scraper used filesystem-scanned fallback file due to download failure"
            )

            return filesystem_fallback

        self.logger.error(
            "Download failed and no fallback available (checked both database and filesystem)"
        )
        return None

    def _get_data_source(self):
        """Get the data source record for this scraper."""
        try:
            from app.database import db
            from app.database.models import DataSource

            return (
                db.session.query(DataSource)
                .filter(DataSource.name == self.source_name)
                .first()
            )
        except Exception as e:
            self.logger.error(f"Error getting data source: {e}")
            return None

    def _find_filesystem_fallback(self) -> str | None:
        """Find most recent file in download directory as filesystem-based fallback.

        This method scans the download directory directly for files when the
        database-tracked approach fails, providing a secondary fallback mechanism.
        """
        try:
            if not self.download_dir or not os.path.exists(self.download_dir):
                self.logger.warning(
                    f"Download directory not found: {self.download_dir}"
                )
                return None

            # Get all files in download directory
            files = []
            for filename in os.listdir(self.download_dir):
                file_path = os.path.join(self.download_dir, filename)
                if os.path.isfile(file_path):
                    try:
                        # Get file modification time
                        mtime = os.path.getmtime(file_path)
                        files.append((file_path, mtime, filename))
                    except OSError as e:
                        self.logger.warning(f"Could not get mtime for {file_path}: {e}")
                        continue

            if not files:
                self.logger.warning(
                    f"No files found in download directory: {self.download_dir}"
                )
                return None

            # Sort by modification time (newest first)
            files.sort(key=lambda x: x[1], reverse=True)

            # Try files starting with most recent
            for file_path, mtime, filename in files:
                if self._validate_fallback_file(file_path):
                    self.logger.info(
                        f"Found valid filesystem fallback: {filename} (modified: {mtime})"
                    )
                    return file_path
                self.logger.debug(f"Skipping invalid fallback file: {filename}")

            self.logger.warning("No valid fallback files found in filesystem scan")
            return None

        except Exception as e:
            self.logger.error(f"Error during filesystem fallback scan: {e}")
            return None

    def _validate_fallback_file(self, file_path: str) -> bool:
        """Validate that a potential fallback file is usable.

        Args:
            file_path: Path to file to validate

        Returns:
            bool: True if file appears to be valid for processing
        """
        try:
            # Check file exists and has reasonable size
            if not os.path.exists(file_path):
                return False

            file_size = os.path.getsize(file_path)

            # File should be at least 100 bytes (very small files are likely error pages)
            if file_size < 100:
                self.logger.debug(f"File too small ({file_size} bytes): {file_path}")
                return False

            # Check file extension is supported
            _, ext = os.path.splitext(file_path.lower())
            supported_extensions = [".csv", ".xlsx", ".xls", ".xlsm", ".html", ".htm"]
            if ext not in supported_extensions:
                self.logger.debug(f"Unsupported file extension {ext}: {file_path}")
                return False

            # For CSV files, do a quick content check
            if ext == ".csv":
                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        first_line = f.readline().lower()
                        # Check if it looks like HTML error page
                        if "<html" in first_line or "<title>error" in first_line:
                            self.logger.debug(
                                f"File appears to be HTML error page: {file_path}"
                            )
                            return False
                except Exception:
                    # If we can't read it, assume it's binary/Excel and valid
                    pass

            self.logger.debug(f"File passed validation: {file_path}")
            return True

        except Exception as e:
            self.logger.warning(f"Error validating fallback file {file_path}: {e}")
            return False

    # ============================================================================
    # DATA PROCESSING FUNCTIONALITY (from DataProcessingMixin)
    # ============================================================================

    def read_file_to_dataframe(self, file_path: str) -> pd.DataFrame | None:
        """Read file to DataFrame with intelligent format detection and strategy handling.

        Args:
            file_path: Path to file to read

        Returns:
            pd.DataFrame: Loaded DataFrame, or None if failed
        """
        if not file_path or not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            return None

        self.logger.info(f"Reading file: {file_path}")

        try:
            strategy = self.config.file_read_strategy.lower()

            if strategy == "csv_then_excel":
                return self._read_csv_then_excel(file_path)
            if strategy == "html_then_excel":
                return self._read_html_then_excel(file_path)
            if strategy == "excel":
                return self._read_excel_file(file_path)
            if strategy == "csv":
                return self._read_csv_file(file_path)
            if strategy == "html":
                return self._read_html_file(file_path)
            # auto
            return self._read_auto_detect(file_path)

        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            return None

    def _read_csv_then_excel(self, file_path: str) -> pd.DataFrame | None:
        """Try CSV first, fallback to Excel."""
        # Try CSV first
        df = self._read_csv_file(file_path)
        if df is not None:
            return df

        # Fallback to Excel
        self.logger.info("CSV reading failed, trying Excel")
        return self._read_excel_file(file_path)

    def _read_html_then_excel(self, file_path: str) -> pd.DataFrame | None:
        """Try HTML first, fallback to Excel."""
        # Try HTML first
        df = self._read_html_file(file_path)
        if df is not None:
            return df

        # Fallback to Excel
        self.logger.info("HTML reading failed, trying Excel")
        return self._read_excel_file(file_path)

    def _read_csv_file(self, file_path: str) -> pd.DataFrame | None:
        """Read CSV file with configuration options."""
        try:
            # Merge general read options with CSV-specific options
            read_options = {**self.config.read_options, **self.config.csv_read_options}

            # Set default encoding if not specified
            if "encoding" not in read_options:
                read_options["encoding"] = "utf-8"

            # Set default na_values to treat empty strings as NaN
            if "na_values" not in read_options:
                read_options["na_values"] = [
                    "",
                    '""',
                    "''",
                    "N/A",
                    "n/a",
                    "NA",
                    "na",
                    "None",
                    "none",
                    "NULL",
                    "null",
                ]

            df = pd.read_csv(file_path, **read_options)
            self.logger.debug(f"Successfully read CSV file with {len(df)} rows")
            return df

        except Exception as e:
            self.logger.warning(f"Failed to read as CSV: {e}")
            return None

    def _read_excel_file(self, file_path: str) -> pd.DataFrame | None:
        """Read Excel file with configuration options."""
        try:
            # Merge general read options with Excel-specific options
            read_options = {
                **self.config.read_options,
                **self.config.excel_read_options,
            }

            # Set default engine if not specified
            if "engine" not in read_options:
                read_options["engine"] = "openpyxl"

            df = pd.read_excel(file_path, **read_options)
            self.logger.debug(f"Successfully read Excel file with {len(df)} rows")
            return df

        except Exception as e:
            self.logger.warning(f"Failed to read as Excel: {e}")
            return None

    def _read_html_file(self, file_path: str) -> pd.DataFrame | None:
        """Read HTML file with configuration options."""
        try:
            # Merge general read options with HTML-specific options
            read_options = {**self.config.read_options, **self.config.html_read_options}

            # Read HTML tables
            tables = pd.read_html(file_path, **read_options)

            if not tables:
                self.logger.warning("No tables found in HTML file")
                return None

            # Use first table by default
            df = tables[0]
            self.logger.debug(f"Successfully read HTML file with {len(df)} rows")
            return df

        except Exception as e:
            self.logger.warning(f"Failed to read as HTML: {e}")
            return None

    def _read_auto_detect(self, file_path: str) -> pd.DataFrame | None:
        """Auto-detect file format and read appropriately."""
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext in [".csv"]:
            return self._read_csv_file(file_path)
        if file_ext in [".xlsx", ".xls", ".xlsm"]:
            return self._read_excel_file(file_path)
        if file_ext in [".html", ".htm"]:
            return self._read_html_file(file_path)
        # Try CSV first as fallback
        df = self._read_csv_file(file_path)
        if df is not None:
            return df

        # Then try Excel
        return self._read_excel_file(file_path)

    def transform_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply comprehensive data transformations based on configuration.

        Args:
            df: Input DataFrame

        Returns:
            pd.DataFrame: Transformed DataFrame
        """
        if df is None or df.empty:
            self.logger.warning("Cannot transform empty DataFrame")
            return df

        self.logger.info(f"Starting DataFrame transformation with {len(df)} rows")

        # 1. Drop rows that are completely empty
        if self.config.dropna_how_all:
            initial_rows = len(df)
            df = df.dropna(how="all")
            if len(df) < initial_rows:
                self.logger.debug(
                    f"Dropped {initial_rows - len(df)} completely empty rows"
                )

        # 2. Apply custom transformation functions first
        for func_name in self.config.custom_transform_functions:
            if hasattr(self, func_name):
                self.logger.debug(f"Applying custom transformation: {func_name}")
                try:
                    df = getattr(self, func_name)(df)
                except Exception as e:
                    self.logger.error(
                        f"Error in custom transformation {func_name}: {e}"
                    )
                    continue
            else:
                self.logger.warning(
                    f"Custom transformation function {func_name} not found"
                )

        # 3. Apply raw column renaming
        if self.config.raw_column_rename_map:
            df = self._apply_column_renaming(df, self.config.raw_column_rename_map)

        # 4. Process date columns
        if self.config.date_column_configs:
            df = self._process_date_columns(df, self.config.date_column_configs)

        # 5. Process value columns
        if self.config.value_column_configs:
            df = self._process_value_columns(df, self.config.value_column_configs)

        # 6. Process place columns
        if self.config.place_column_configs:
            df = self._process_place_columns(df, self.config.place_column_configs)

        # 7. Process fiscal year columns
        if self.config.fiscal_year_configs:
            df = self._process_fiscal_year_columns(df, self.config.fiscal_year_configs)

        # 8. Process NAICS columns to standardize formatting
        df = self._process_naics_columns(df)

        # 9. Collect unmapped columns into extras_json before db column renaming
        df = self._collect_unmapped_columns_to_extras(df)

        # 10. Apply database column renaming (this will rename extras_json to extra)
        if self.config.db_column_rename_map:
            df = self._apply_column_renaming(df, self.config.db_column_rename_map)

        # 11. Generate ID hash
        if self.config.fields_for_id_hash:
            df = self._generate_id_hash(df, self.config.fields_for_id_hash)

        # 12. Clean up - keep only columns that are in the db_column_rename_map values (final columns)
        # Only filter columns if db_column_rename_map is provided, otherwise keep all columns
        if self.config.db_column_rename_map:
            final_columns = list(self.config.db_column_rename_map.values())
            # Also keep id and any other essential columns (extras_json gets renamed to extra via mapping)
            essential_columns = ["id", "source_id", "loaded_at"]
            columns_to_keep = [
                col
                for col in df.columns
                if col in final_columns or col in essential_columns
            ]
            df = df[columns_to_keep]
            self.logger.debug(f"Kept only final columns: {columns_to_keep}")

        self.logger.info(f"DataFrame transformation completed with {len(df)} rows")
        return df

    def _apply_column_renaming(
        self, df: pd.DataFrame, rename_map: dict[str, str]
    ) -> pd.DataFrame:
        """Apply column renaming with logging."""
        if not rename_map:
            return df

        # Only rename columns that exist
        existing_renames = {
            old: new for old, new in rename_map.items() if old in df.columns
        }

        if existing_renames:
            df = df.rename(columns=existing_renames)
            self.logger.debug(f"Renamed columns: {existing_renames}")

        missing_columns = set(rename_map.keys()) - set(df.columns)
        if missing_columns:
            # Use trace level for expected missing columns (consumed by custom transforms)
            self.logger.trace(
                f"Columns not found for renaming (may be consumed by custom transforms): {missing_columns}"
            )

        return df

    def _process_date_columns(
        self, df: pd.DataFrame, date_configs: list[dict[str, Any]]
    ) -> pd.DataFrame:
        """Process date columns according to configuration."""
        for config in date_configs:
            try:
                if config.get("parse_type") == "fiscal_quarter":
                    df = self._parse_fiscal_quarter_date(df, config)
                else:
                    df = self._parse_standard_date(df, config)
            except Exception as e:
                self.logger.error(f"Error processing date config {config}: {e}")
                continue

        return df

    def _parse_standard_date(
        self, df: pd.DataFrame, config: dict[str, Any]
    ) -> pd.DataFrame:
        """Parse standard date column."""
        source_col = config.get("column")
        target_col = config.get("target_column")

        if not source_col or not target_col or source_col not in df.columns:
            return df

        try:
            df[target_col] = pd.to_datetime(df[source_col], errors="coerce")

            # Convert to date if specified
            if config.get("store_as_date", False):
                df[target_col] = df[target_col].dt.date

            self.logger.debug(f"Parsed date column {source_col} -> {target_col}")

        except Exception as e:
            self.logger.warning(f"Failed to parse date column {source_col}: {e}")

        return df

    def _parse_fiscal_quarter_date(
        self, df: pd.DataFrame, config: dict[str, Any]
    ) -> pd.DataFrame:
        """Parse fiscal quarter (e.g., 'FY24 Q2') into date and fiscal year."""
        source_col = config.get("column")
        target_date_col = config.get("target_date_col")
        target_fy_col = config.get("target_fy_col")

        if not source_col or source_col not in df.columns:
            return df

        try:
            # Extract fiscal year and quarter from strings like "FY24 Q2", "FY 2025 Q2", or "3rd (April 1 - June 30)"
            fiscal_pattern = r"FY\s*(\d{2,4})\s*Q(\d)"
            quarter_detailed_pattern = r"(\d+)(?:st|nd|rd|th)\s*\("

            def parse_fiscal_quarter(value):
                if pd.isna(value):
                    return None, None

                value_str = str(value)

                # Try standard FY Q pattern first
                match = re.search(fiscal_pattern, value_str)
                if match:
                    year_str = match.group(1)
                    quarter = int(match.group(2))

                    # Convert 2-digit year to 4-digit (assume 20XX)
                    if len(year_str) == 2:
                        fiscal_year = 2000 + int(year_str)
                    else:
                        fiscal_year = int(year_str)

                    # Fiscal year typically starts in October
                    # Q1: Oct-Dec, Q2: Jan-Mar, Q3: Apr-Jun, Q4: Jul-Sep
                    if quarter == 1:
                        date = datetime(fiscal_year - 1, 10, 1).date()
                    elif quarter == 2:
                        date = datetime(fiscal_year, 1, 1).date()
                    elif quarter == 3:
                        date = datetime(fiscal_year, 4, 1).date()
                    else:  # quarter == 4
                        date = datetime(fiscal_year, 7, 1).date()

                    return date, fiscal_year

                # Try detailed quarter pattern like "3rd (April 1 - June 30)"
                quarter_match = re.search(quarter_detailed_pattern, value_str)
                if quarter_match:
                    quarter = int(quarter_match.group(1))
                    # Assume current fiscal year (can be improved later with context)
                    current_year = datetime.now().year
                    fiscal_year = (
                        current_year if datetime.now().month >= 10 else current_year
                    )

                    if quarter == 1:
                        date = datetime(fiscal_year - 1, 10, 1).date()
                    elif quarter == 2:
                        date = datetime(fiscal_year, 1, 1).date()
                    elif quarter == 3:
                        date = datetime(fiscal_year, 4, 1).date()
                    elif quarter == 4:
                        date = datetime(fiscal_year, 7, 1).date()
                    else:
                        return None, None

                    return date, fiscal_year

                return None, None

            # Apply parsing
            parsed_data = df[source_col].apply(parse_fiscal_quarter)

            if target_date_col:
                df[target_date_col] = [item[0] for item in parsed_data]

            if target_fy_col:
                df[target_fy_col] = [item[1] for item in parsed_data]

            self.logger.debug(f"Parsed fiscal quarter column {source_col}")

        except Exception as e:
            self.logger.warning(
                f"Failed to parse fiscal quarter column {source_col}: {e}"
            )

        return df

    def _process_value_columns(
        self, df: pd.DataFrame, value_configs: list[dict[str, Any]]
    ) -> pd.DataFrame:
        """Process value columns (extract numeric values and units)."""
        for config in value_configs:
            try:
                source_col = config.get("column")
                target_value_col = config.get("target_value_col")
                target_unit_col = config.get("target_unit_col")

                if not source_col or source_col not in df.columns:
                    continue

                # Extract numeric values and units from text
                def parse_value(text):
                    if pd.isna(text):
                        return None, None

                    text = str(text).strip()

                    # Look for patterns like "$1.5M", "500K", "$1,000,000"
                    money_pattern = r"\$?([0-9,]+\.?[0-9]*)\s*([KMB]?)"
                    match = re.search(money_pattern, text, re.IGNORECASE)

                    if match:
                        value_str = match.group(1).replace(",", "")
                        unit = match.group(2).upper() if match.group(2) else ""

                        try:
                            value = float(value_str)

                            # Convert K, M, B to actual values
                            if unit == "K":
                                value *= 1000
                            elif unit == "M":
                                value *= 1000000
                            elif unit == "B":
                                value *= 1000000000

                            return value, unit
                        except ValueError:
                            pass

                    return None, None

                parsed_data = df[source_col].apply(parse_value)

                if target_value_col:
                    df[target_value_col] = [item[0] for item in parsed_data]

                if target_unit_col:
                    df[target_unit_col] = [item[1] for item in parsed_data]

                self.logger.debug(f"Parsed value column {source_col}")

            except Exception as e:
                self.logger.error(f"Error processing value config {config}: {e}")
                continue

        return df

    def _process_place_columns(
        self, df: pd.DataFrame, place_configs: list[dict[str, Any]]
    ) -> pd.DataFrame:
        """Process place columns (split location strings)."""
        for config in place_configs:
            try:
                source_col = config.get("column")
                target_city_col = config.get("target_city_col")
                target_state_col = config.get("target_state_col")
                target_country_col = config.get("target_country_col")

                if not source_col or source_col not in df.columns:
                    continue

                def parse_location(location):
                    if pd.isna(location):
                        return None, None, None

                    parts = [part.strip() for part in str(location).split(",")]

                    city = parts[0] if len(parts) > 0 else None
                    state = parts[1] if len(parts) > 1 else None
                    country = parts[2] if len(parts) > 2 else None

                    return city, state, country

                parsed_data = df[source_col].apply(parse_location)

                if target_city_col:
                    df[target_city_col] = [item[0] for item in parsed_data]

                if target_state_col:
                    df[target_state_col] = [item[1] for item in parsed_data]

                if target_country_col:
                    df[target_country_col] = [item[2] for item in parsed_data]

                self.logger.debug(f"Parsed place column {source_col}")

            except Exception as e:
                self.logger.error(f"Error processing place config {config}: {e}")
                continue

        return df

    def _process_fiscal_year_columns(
        self, df: pd.DataFrame, fy_configs: list[dict[str, Any]]
    ) -> pd.DataFrame:
        """Process fiscal year columns."""
        for config in fy_configs:
            try:
                parse_type = config.get("parse_type", "direct")

                if parse_type == "direct":
                    source_col = config.get("column")
                    target_col = config.get("target_column")

                    if source_col and target_col and source_col in df.columns:
                        df[target_col] = pd.to_numeric(df[source_col], errors="coerce")

                elif parse_type == "from_date_year":
                    date_col = config.get("date_column")
                    target_col = config.get("target_column")

                    if date_col and target_col and date_col in df.columns:
                        # Extract year from date and use as fiscal year
                        df[target_col] = pd.to_datetime(
                            df[date_col], errors="coerce"
                        ).dt.year
                        # Convert to nullable integer type
                        df[target_col] = df[target_col].astype("Int64")
                        # Convert NaN to None for database compatibility
                        df[target_col] = df[target_col].where(
                            pd.notna(df[target_col]), None
                        )

                self.logger.debug(f"Processed fiscal year config: {config}")

            except Exception as e:
                self.logger.error(f"Error processing fiscal year config {config}: {e}")
                continue

        return df

    def _process_naics_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process NAICS columns to standardize formatting and separate code from description."""
        try:
            # Check for standard NAICS columns that need processing
            naics_columns_to_process = []

            # Common NAICS column names from scrapers
            naics_column_candidates = ["naics_code", "naics", "primary_naics"]
            for col in naics_column_candidates:
                if col in df.columns:
                    naics_columns_to_process.append(col)

            if not naics_columns_to_process:
                return df

            # Initialize LLM service for NAICS parsing (only when needed)
            llm_service = LLMService()

            processed_count = 0
            for col in naics_columns_to_process:
                # Process each NAICS column
                for idx, naics_value in df[col].items():
                    if pd.isna(naics_value) or not str(naics_value).strip():
                        continue

                    # Parse the NAICS value using the standardized parser
                    parsed = llm_service.parse_existing_naics(str(naics_value).strip())

                    if parsed["code"]:
                        # Update the NAICS code column with just the code
                        df.at[idx, col] = parsed["code"]

                        # Set description in appropriate column if it exists and is empty
                        desc_col = "naics_description"
                        if desc_col in df.columns and parsed["description"]:
                            current_desc = df.at[idx, desc_col]
                            if pd.isna(current_desc) or not str(current_desc).strip():
                                df.at[idx, desc_col] = parsed["description"]

                        processed_count += 1

            if processed_count > 0:
                self.logger.info(
                    f"Standardized NAICS formatting for {processed_count} records"
                )

        except Exception as e:
            self.logger.error(f"Error processing NAICS columns: {e}")

        return df

    def _generate_id_hash(
        self, df: pd.DataFrame, hash_fields: list[str]
    ) -> pd.DataFrame:
        """Generate unique ID hash from specified fields."""
        try:
            # Only use fields that exist in the DataFrame
            available_fields = [field for field in hash_fields if field in df.columns]

            if not available_fields:
                self.logger.warning("No fields available for ID hash generation")
                df["id"] = df.index.astype(str)  # Fallback to row numbers
                return df

            # Create MD5 hash from concatenated field values
            def create_hash(row):
                values = []
                for field in available_fields:
                    value = row.get(field, "")
                    if pd.notna(value):
                        values.append(str(value))

                combined = "|".join(values)
                # Create MD5 hash with source prefix
                combined_with_source = f"{self.source_name}|{combined}"
                md5_hash = hashlib.md5(combined_with_source.encode()).hexdigest()
                return md5_hash

            df["id"] = df.apply(create_hash, axis=1)
            self.logger.debug(f"Generated ID hash using fields: {available_fields}")

        except Exception as e:
            self.logger.error(f"Error generating ID hash: {e}")
            df["id"] = df.index.astype(str)  # Fallback

        return df

    def _collect_unmapped_columns_to_extras(self, df: pd.DataFrame) -> pd.DataFrame:
        """Collect unmapped columns into extras_json field before they get filtered out.
        This preserves additional data that isn't explicitly mapped but may be useful for AI processing.
        """
        try:
            if not self.config.db_column_rename_map:
                return df

            # Get all columns that should be kept after cleanup
            final_columns = list(self.config.db_column_rename_map.values())
            essential_columns = ["id", "source_id", "loaded_at"]
            columns_to_keep = set(final_columns + essential_columns)

            # Find columns that will be dropped (unmapped columns)
            current_columns = set(df.columns)
            unmapped_columns = current_columns - columns_to_keep

            # Exclude extras_json from unmapped columns since it's handled specially
            unmapped_columns.discard("extras_json")

            if not unmapped_columns:
                self.logger.debug("No unmapped columns found - no extras to collect")
                return df

            self.logger.debug(
                f"Collecting {len(unmapped_columns)} unmapped columns into extras_json: {sorted(unmapped_columns)}"
            )

            # Create extras_json column with unmapped data
            def create_extras_json(row):
                extras = {}
                for col in unmapped_columns:
                    value = row.get(col)
                    # Only include non-null, non-empty values
                    if pd.notna(value) and value != "" and value is not None:
                        # Convert to string for JSON serialization
                        if isinstance(value, (int, float, str, bool)):
                            extras[col] = value
                        else:
                            extras[col] = str(value)

                return extras if extras else None

            # Apply the function to create the extras_json column, merging with existing if present
            if "extras_json" in df.columns:
                # If extras_json already exists (e.g., from custom transforms), merge the data
                def merge_with_existing_extras(row):
                    new_extras = create_extras_json(row)
                    existing_extras = row.get("extras_json")

                    # Handle existing extras_json that might be a JSON string
                    if isinstance(existing_extras, str):
                        try:
                            existing_extras = (
                                json.loads(existing_extras)
                                if existing_extras and existing_extras != "{}"
                                else {}
                            )
                        except (json.JSONDecodeError, TypeError):
                            existing_extras = {}
                    elif not isinstance(existing_extras, dict):
                        existing_extras = {}

                    # Merge new extras with existing ones
                    if new_extras:
                        merged = {**existing_extras, **new_extras}
                        return merged if merged else None
                    return existing_extras if existing_extras else None

                df["extras_json"] = df.apply(merge_with_existing_extras, axis=1)
                self.logger.debug(
                    "Merged unmapped columns with existing extras_json data"
                )
            else:
                # No existing extras_json, create new one
                df["extras_json"] = df.apply(create_extras_json, axis=1)

            # Log statistics about extras collection
            non_empty_extras = (
                df["extras_json"].apply(lambda x: x is not None and len(x) > 0).sum()
            )
            self.logger.info(
                f"Created extras_json for {non_empty_extras}/{len(df)} rows"
            )

            # Log sample of collected extras for debugging
            if non_empty_extras > 0:
                sample_extras = df[df["extras_json"].notna()]["extras_json"].iloc[0]
                sample_keys = list(sample_extras.keys()) if sample_extras else []
                self.logger.debug(
                    f"Sample extras keys: {sample_keys[:10]}"
                )  # Show first 10 keys

        except Exception as e:
            self.logger.error(f"Error collecting unmapped columns to extras: {e}")
            # Add empty extras_json column as fallback
            df["extras_json"] = None

        return df

    def prepare_and_load_data(self, df: pd.DataFrame) -> int:
        """Prepare DataFrame for database loading and execute bulk load.

        Args:
            df: Transformed DataFrame

        Returns:
            int: Number of records loaded
        """
        if df is None or df.empty:
            self.logger.warning("No data to load")
            return 0

        try:
            # Ensure data source exists
            self._ensure_data_source()

            # Add source_id to all records
            df["source_id"] = self.data_source.id

            # Add loaded_at timestamp
            df["loaded_at"] = datetime.now(UTC)

            # Validate required fields if specified
            if self.config.required_fields_for_load:
                initial_count = len(df)
                for field in self.config.required_fields_for_load:
                    if field in df.columns:
                        df = df.dropna(subset=[field])

                if len(df) < initial_count:
                    self.logger.info(
                        f"Dropped {initial_count - len(df)} rows due to missing required fields"
                    )

            # Get valid Prospect model columns
            from app.database.models import Prospect

            valid_columns = [column.name for column in Prospect.__table__.columns]

            # Add special columns that are handled separately
            special_columns = [
                "extras_json"
            ]  # This gets renamed to 'extra' by the model

            # Filter dataframe to only include valid columns
            columns_to_keep = [
                col
                for col in df.columns
                if col in valid_columns or col in special_columns
            ]

            # Log which columns are being filtered out
            filtered_columns = set(df.columns) - set(columns_to_keep)
            if filtered_columns:
                self.logger.debug(
                    f"Filtering out {len(filtered_columns)} non-model columns: {sorted(filtered_columns)}"
                )

            # Keep only valid columns
            df = df[columns_to_keep]

            # Rename extras_json to extra to match the model
            if "extras_json" in df.columns:
                df = df.rename(columns={"extras_json": "extra"})

            # Convert DataFrame to records for bulk loading
            records = df.to_dict("records")

            # Clean up records to handle NaN and None values properly
            cleaned_records = []
            for record in records:
                cleaned_record = {}
                for key, value in record.items():
                    # Convert NaT and NaN to None
                    if pd.isna(value):
                        cleaned_record[key] = None
                    # Handle Int64 type (nullable integer)
                    elif hasattr(value, "item"):
                        cleaned_record[key] = value.item() if pd.notna(value) else None
                    else:
                        cleaned_record[key] = value
                cleaned_records.append(cleaned_record)

            # Convert to DataFrame for bulk upsert
            df_for_upsert = pd.DataFrame(cleaned_records)

            # Execute bulk upsert
            result = bulk_upsert_prospects(
                df_for_upsert,
                preserve_ai_data=active_config.PRESERVE_AI_DATA_ON_REFRESH,
                enable_smart_matching=active_config.ENABLE_SMART_DUPLICATE_MATCHING,
            )

            # Extract loaded count from result - check for enhanced result format first
            if isinstance(result, dict):
                loaded_count = result.get("inserted", result.get("total_processed", 0))
            else:
                loaded_count = 0

            # Update data source last_scraped timestamp
            self.data_source.last_scraped = datetime.now(UTC)
            db.session.commit()

            self.logger.info(f"Successfully loaded {loaded_count} records to database")
            return loaded_count

        except Exception as e:
            self.logger.error(f"Error loading data to database: {e}")
            db.session.rollback()
            raise Exception(f"Database loading failed: {e}") from e

    def _ensure_data_source(self):
        """Ensure data source record exists in database."""
        if self.data_source:
            return

        self.data_source = DataSource.query.filter_by(name=self.source_name).first()

        if not self.data_source:
            self.data_source = DataSource(
                name=self.source_name,
                url=self.base_url,
                description=f"Data source for {self.source_name}",
            )
            db.session.add(self.data_source)
            db.session.commit()
            self.logger.info(f"Created new data source: {self.source_name}")
        else:
            self.logger.debug(f"Using existing data source: {self.source_name}")

    # ============================================================================
    # STANDARD SCRAPING PATTERNS (from PageInteractionScraper)
    # ============================================================================

    async def standard_setup(self) -> bool:
        """Standard setup: navigate to base URL and wait for load."""
        if not self.base_url:
            self.logger.error("No base URL configured for standard setup")
            return False

        success = await self.navigate_to_url(self.base_url)
        if success:
            await self.wait_for_load_state("networkidle")

        return success

    async def standard_extract(self) -> str | None:
        """Standard extraction: download via configured button selector."""
        selector = self.config.export_button_selector or self.config.csv_button_selector

        if not selector:
            self.logger.error(
                "No export button selector configured for standard extract"
            )
            return None

        # Handle pre-export click if configured
        if self.config.pre_export_click_selector:
            await self.click_element(self.config.pre_export_click_selector)
            if self.config.pre_export_click_wait_ms > 0:
                await self.wait_for_timeout(self.config.pre_export_click_wait_ms)

        # Handle explicit wait before download
        if self.config.explicit_wait_ms_before_download > 0:
            await self.wait_for_timeout(self.config.explicit_wait_ms_before_download)

        # Perform download with fallback
        return await self.download_with_fallback(
            selector=selector,
            wait_after_click=self.config.default_wait_after_download_ms,
        )

    def standard_process(self, file_path: str) -> int:
        """Standard processing with file validation and tracking."""
        start_time = datetime.now()
        processing_log = None

        if not file_path:
            # Try to get most recent download
            file_path = self.get_last_downloaded_path()
            if not file_path:
                self.logger.error("No file available for processing")
                raise Exception("No file available for processing")

        try:
            # Get source ID for tracking
            from app.utils.database_helpers import get_data_source_id_by_name

            source_id = get_data_source_id_by_name(self.source_name)
            if not source_id:
                self.logger.warning(f"Could not find source ID for {self.source_name}")

            # Create processing log
            if source_id:
                processing_log = create_processing_log(source_id, file_path)

            # Perform soft file validation (warnings only)
            from app.utils.file_processing import validate_file_content

            # Get expected columns for schema validation (if available)
            expected_columns = None
            if hasattr(self.config, "raw_column_rename_map"):
                expected_columns = list(self.config.raw_column_rename_map.keys())

            # Validate file content
            validation_result = validate_file_content(file_path, expected_columns)
            is_likely_valid = validation_result.get("valid", False)

            # Log validation summary (warnings only - don't block processing)
            if not is_likely_valid:
                self.logger.warning(
                    f"File validation issues for {file_path}: {validation_result.get('error', 'Unknown error')}"
                )
            if validation_result.get("has_schema_changes", False):
                self.logger.warning(
                    f"Schema changes detected in {file_path}: missing columns {validation_result.get('missing_expected_columns', [])}"
                )

            # Read file to DataFrame
            df = self.read_file_to_dataframe(file_path)
            if df is None:
                error_msg = "Failed to read file to DataFrame"
                self.logger.error(error_msg)

                # Update processing log with failure
                if processing_log:
                    (datetime.now() - start_time).total_seconds()
                    update_processing_log(
                        processing_log, False, error_message=error_msg
                    )
                raise Exception(f"Failed to read file to DataFrame: {file_path}")

            len(df)
            list(df.columns) if not df.empty else []

            # Apply transformations
            df = self.transform_dataframe(df)

            # Load to database
            records_inserted = self.prepare_and_load_data(df)

            # Update processing log with success
            if processing_log:
                update_processing_log(
                    processing_log, True, records_processed=records_inserted
                )

            return records_inserted

        except Exception as e:
            error_msg = f"Error during file processing: {e}"
            self.logger.error(error_msg)

            # Update processing log with failure
            if processing_log:
                update_processing_log(processing_log, False, error_message=error_msg)

            # Re-raise the exception to maintain existing error handling
            raise

    async def scrape_with_structure(
        self,
        setup_method: Callable | None = None,
        extract_method: Callable | None = None,
        process_method: Callable | None = None,
    ) -> int:
        """Execute structured scraping workflow.

        Args:
            setup_method: Custom setup method (defaults to standard_setup)
            extract_method: Custom extract method (defaults to standard_extract)
            process_method: Custom process method (defaults to standard_process)

        Returns:
            int: Number of records loaded
        """
        setup_method = setup_method or self.standard_setup
        extract_method = extract_method or self.standard_extract
        process_method = process_method or self.standard_process

        try:
            # Setup phase
            self.logger.info(f"Starting scrape for {self.source_name}")
            await self.setup_browser()

            setup_success = await setup_method()
            if not setup_success:
                self.logger.error("Setup phase failed, attempting fallback")

                # Try filesystem fallback for setup failures
                filesystem_fallback = self._find_filesystem_fallback()
                if filesystem_fallback:
                    self.logger.warning(
                        f"Using filesystem fallback after setup failure: {filesystem_fallback}"
                    )
                    # Log fallback usage for monitoring
                    self.logger.warning(
                        f"FALLBACK USED (SETUP): {self.source_name} scraper used filesystem fallback due to setup phase failure"
                    )

                    # Skip extract phase and go directly to process phase with fallback file
                    await self.cleanup_browser()

                    # Process phase with fallback file
                    if asyncio.iscoroutinefunction(process_method):
                        loaded_count = await process_method(filesystem_fallback)
                    else:
                        loaded_count = process_method(filesystem_fallback)

                    self.logger.info(
                        f"Scrape completed for {self.source_name} using fallback: {loaded_count} records loaded"
                    )
                    return loaded_count
                await self.cleanup_browser()
                raise Exception(
                    "Setup phase failed - unable to initialize scraper and no fallback available"
                )

            # Extract phase
            file_path = await extract_method()
            if not file_path:
                self.logger.error("Extract phase failed, attempting fallback")

                # Try filesystem fallback for extract failures
                filesystem_fallback = self._find_filesystem_fallback()
                if filesystem_fallback:
                    self.logger.warning(
                        f"Using filesystem fallback after extract failure: {filesystem_fallback}"
                    )
                    file_path = filesystem_fallback
                    # Log fallback usage for monitoring
                    self.logger.warning(
                        f"FALLBACK USED (EXTRACT): {self.source_name} scraper used filesystem fallback due to extract phase failure"
                    )
                else:
                    await self.cleanup_browser()
                    raise Exception(
                        "Extract phase failed - unable to download file and no fallback available"
                    )

            # Process phase
            if asyncio.iscoroutinefunction(process_method):
                loaded_count = await process_method(file_path)
            else:
                loaded_count = process_method(file_path)

            # Clean up browser BEFORE returning to ensure cleanup completes
            await self.cleanup_browser()

            self.logger.info(
                f"Scrape completed for {self.source_name}: {loaded_count} records loaded"
            )
            return loaded_count

        except Exception as e:
            self.logger.error(f"Error during scrape: {e}")
            await self.capture_error_info(e, "scrape_structure_exception")
            await self.cleanup_browser()
            raise Exception(f"Scraper failed with error: {e}") from e

    async def scrape(self) -> int:
        """Simple scrape using standard workflow."""
        return await self.scrape_with_structure()
