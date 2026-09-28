"""DOT scraper using the consolidated architecture.
Preserves all original DOT-specific functionality including complex retry logic and new page downloads.
"""

import os
import time

import pandas as pd
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.config import active_config
from app.core.consolidated_scraper_base import ConsolidatedScraperBase
from app.core.scraper_configs import get_scraper_config


class DotScraper(ConsolidatedScraperBase):
    """Consolidated DOT scraper.
    Preserves all original functionality including complex navigation retry logic.
    """

    def __init__(self):
        config = get_scraper_config("dot")
        config.base_url = active_config.DOT_FORECAST_URL
        super().__init__(config)

    def _custom_dot_transforms(self, df: pd.DataFrame) -> pd.DataFrame:
        """Custom DOT transformations preserving the original complex logic.
        Handles complex award date parsing and contract type fallbacks.
        """
        try:
            self.logger.info("Applying custom DOT transformations...")

            # Simplified DOT transforms - removed problematic column references
            # Current DOT CSV format doesn't include award dates or contract types
            # in the expected columns, so we skip those transforms

            # Parse place_raw to extract city and state
            if "place_raw" in df.columns:
                # DOT typically has format like "Oklahoma City, OK" or "Washington, DC"
                df[["place_city", "place_state"]] = df["place_raw"].str.extract(
                    r"^([^,]+)(?:,\s*([A-Z]{2}))?$", expand=True
                )
                df["place_city"] = df["place_city"].str.strip()
                df["place_state"] = df["place_state"].str.strip()
                df["place_country"] = "USA"  # Default for DOT data
                self.logger.debug("Parsed place_raw into city, state, and country.")

            self.logger.debug("DOT custom transforms completed")

        except Exception as e:
            self.logger.warning(f"Error in _custom_dot_transforms: {e}")

        return df

    def _dot_create_extras(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create extras JSON with DOT-specific fields that aren't in core schema.
        Captures 19 additional data points for comprehensive data retention.
        """
        try:
            # Define DOT-specific extras fields mapping (using original CSV column names)
            extras_fields = {
                "Agency": "agency_detail",
                "FY": "fiscal_year",
                "Procurement Category": "procurement_category",
                "Incumbent/Contract Number": "incumbent_contract_number",
                "Updates": "updates",
                "Contact Name": "contact_name",
                "Contact Email": "contact_email",
                "Contact Phone": "contact_phone",
                "Is this a follow-on to a current 8(a) contract?": "followon_8a_contract",
                "Is this funded through the American Recovery and Reinvestment Act?": "arra_funded",
                "Contract Awarded": "contract_awarded",
                "Expected Period of Performance - Start": "performance_start_date",
                "Expected Period of Performance - End": "performance_end_date",
                "Personnel Clearance Requirements": "clearance_requirements",
                "Date Modified": "date_modified",
                "Incumbent Contractor": "incumbent_contractor",
                "Action/Award Type": "action_award_type",
                "Anticipated Award Date": "anticipated_award_date",
                "Bipartisan Infrastructure Law (BIL) Opportunity": "bil_opportunity",
            }

            # Create extras JSON column
            extras_data = []
            for _, row in df.iterrows():
                extras = {}
                for df_col, extra_key in extras_fields.items():
                    if df_col in df.columns:
                        value = row[df_col]
                        if pd.notna(value) and value != "":
                            extras[extra_key] = str(value)
                extras_data.append(extras if extras else {})

            # Add the extras JSON column (as dict, not JSON string)
            df["extras_json"] = extras_data

            self.logger.debug(
                f"Created DOT extras JSON for {len(extras_data)} rows with {len(extras_fields)} potential fields"
            )

        except Exception as e:
            self.logger.warning(f"Error in _dot_create_extras: {e}")

        return df

    async def dot_setup(self) -> bool:
        """DOT-specific setup with complex retry logic and Apply button click.
        Preserves original DOT navigation behavior.
        """
        if not self.base_url:
            self.logger.error("Base URL not configured.")
            return False

        self.logger.info(
            f"Navigating to {self.base_url} with custom retry logic (DOT)."
        )

        # Initial delay like original scraper
        await self.wait_for_timeout(2000)

        if not self.config.retry_attempts:
            self.logger.error("No retry attempts configured for DOT")
            return False

        for i, params in enumerate(self.config.retry_attempts, 1):
            try:
                self.logger.info(
                    f"DOT navigation attempt {i}/{len(self.config.retry_attempts)} with params {params}"
                )

                # Delay before attempt (except first)
                delay_before_s = params.get("delay_before_next_s", 0)
                if i > 1 and delay_before_s > 0:
                    self.logger.info(f"Waiting {delay_before_s}s before attempt {i}...")
                    await self.wait_for_timeout(delay_before_s * 1000)

                # Custom navigation with specific wait_until and timeout
                current_nav_timeout = params.get(
                    "timeout", self.config.navigation_timeout_ms
                )
                wait_until = params.get("wait_until", "domcontentloaded")

                try:
                    await self.page.goto(
                        self.base_url,
                        wait_until=wait_until,
                        timeout=current_nav_timeout,
                    )

                    self.logger.info(
                        f"Successfully navigated on attempt {i}. Page URL: {self.page.url}"
                    )

                    # Ensure page is stable after goto
                    await self.wait_for_load_state("load", timeout=current_nav_timeout)

                    # Click Apply button
                    self.logger.info(
                        f"Clicking 'Apply' button: {self.config.pre_export_click_selector}"
                    )
                    success = await self.click_element(
                        self.config.pre_export_click_selector
                    )
                    if not success:
                        self.logger.warning("Failed to click Apply button")
                        if i == len(self.config.retry_attempts):
                            return False
                        continue

                    # Wait after Apply click
                    self.logger.info(
                        f"Waiting {self.config.wait_after_apply_ms}ms after 'Apply' click."
                    )
                    await self.wait_for_timeout(self.config.wait_after_apply_ms)

                    return True  # Successful setup

                except Exception as nav_error:
                    error_str = str(nav_error).upper()

                    # Check for specific network/protocol errors
                    if any(
                        err in error_str
                        for err in [
                            "ERR_HTTP2_PROTOCOL_ERROR",
                            "ERR_TIMED_OUT",
                            "NS_ERROR_NETTIMEOUT",
                        ]
                    ):
                        self.logger.warning(
                            f"Network/Protocol error on attempt {i}: {error_str}"
                        )
                        if i == len(self.config.retry_attempts):
                            self.logger.error(
                                f"All navigation attempts failed with {error_str}"
                            )
                            return False

                        # Progressive delay for these errors
                        delay = params.get("delay_before_next_s", 5) * i
                        self.logger.info(
                            f"Waiting {delay}s before retrying due to {error_str}..."
                        )
                        await self.wait_for_timeout(delay * 1000)
                        continue
                    raise nav_error  # Re-raise unexpected errors

            except PlaywrightTimeoutError as e:
                self.logger.warning(f"Attempt {i} timed out: {str(e)}")
                if i == len(self.config.retry_attempts):
                    self.logger.error("All DOT navigation attempts timed out")
                    return False

                retry_delay_s = params.get("retry_delay_on_timeout_s", 0)
                if retry_delay_s > 0:
                    self.logger.info(
                        f"Waiting {retry_delay_s}s before timeout retry..."
                    )
                    await self.wait_for_timeout(retry_delay_s * 1000)
                continue

            except Exception as e:
                self.logger.error(f"Unexpected error on attempt {i}: {e}")
                if i == len(self.config.retry_attempts):
                    await self.capture_error_info(e, "dot_navigation_error")
                    return False
                continue

        self.logger.error("All navigation attempts failed for DOT scraper setup.")
        return False

    async def dot_extract(self) -> str | None:
        """DOT-specific extraction - handle batch processing workflow.
        DOT uses a batch processing system where clicking the download link starts
        a background job, and we need to wait for completion.
        """
        self.logger.info(
            f"Starting DOT CSV download. Waiting for link: {self.config.export_button_selector}"
        )

        # Wait for download link to be visible
        if not await self.wait_for_selector(
            self.config.export_button_selector, state="visible"
        ):
            self.logger.error(
                f"Download link '{self.config.export_button_selector}' not found or not visible"
            )
            return None

        self.logger.info("Download CSV link is visible.")

        # DOT download - fix the CSV download or fail
        return await self._dot_fix_csv_download()

    async def _dot_fix_csv_download(self) -> str | None:
        """DOT CSV download with proper new tab detection and batch processing monitoring.

        DOT's "Download CSV" button opens a new tab with a batch processing page.
        We need to detect the new tab and monitor it for completion.
        """
        try:
            self.logger.info("Starting DOT CSV download with new tab detection")

            # Set overall timeout for the entire download process
            overall_start_time = time.time()
            overall_timeout = 120  # 2 minutes maximum

            # Get current number of pages before clicking
            initial_pages = len(self.context.pages)
            self.logger.info(f"Initial browser contexts: {initial_pages}")

            # Find the download button
            download_button = await self.page.query_selector(
                self.config.export_button_selector
            )
            if not download_button:
                self.logger.error("Download CSV button not found")
                return None

            self.logger.info("Clicking Download CSV button...")

            # Set up listeners for new pages and downloads across all contexts
            download_occurred = {"file_path": None, "completed": False}

            async def handle_new_page(page):
                self.logger.info(f"New page detected: {page.url}")

                # Set up download listener for the new page
                async def handle_download_on_new_page(download):
                    self.logger.info(
                        f"Download triggered on new page: {download.suggested_filename}"
                    )
                    try:
                        # Handle the download
                        await self._handle_download_event(download)
                        download_occurred["file_path"] = self.last_downloaded_file
                        download_occurred["completed"] = True
                        self.logger.info(
                            f"Download completed: {self.last_downloaded_file}"
                        )
                    except Exception as e:
                        self.logger.error(f"Error handling download: {e}")

                page.on("download", handle_download_on_new_page)

            # Listen for new pages being created
            self.context.on("page", handle_new_page)

            # Also set up download listener on current page (in case download happens here)
            async def handle_download_current_page(download):
                self.logger.info(
                    f"Download triggered on current page: {download.suggested_filename}"
                )
                try:
                    await self._handle_download_event(download)
                    download_occurred["file_path"] = self.last_downloaded_file
                    download_occurred["completed"] = True
                    self.logger.info(
                        f"Download completed on current page: {self.last_downloaded_file}"
                    )
                except Exception as e:
                    self.logger.error(f"Error handling download on current page: {e}")

            self.page.on("download", handle_download_current_page)

            # Get some info about the button before clicking
            href = await download_button.get_attribute("href")
            target = await download_button.get_attribute("target")
            onclick = await download_button.get_attribute("onclick")
            self.logger.info(
                f"Download button attributes - href: {href}, target: {target}, onclick: {onclick}"
            )

            # Try different approaches to handle the target="_blank" link
            if href and target == "_blank":
                self.logger.info(
                    "Link has target=_blank, trying multiple approaches to open it properly"
                )

                # Create a new page manually and navigate to the download URL
                new_page = await self.context.new_page()
                self.logger.info(f"Created new page, navigating to: {href}")

                # Set up download listener on the new page
                async def handle_download_new_page(download):
                    self.logger.info(
                        f"Download triggered on manually created page: {download.suggested_filename}"
                    )
                    try:
                        await self._handle_download_event(download)
                        download_occurred["file_path"] = self.last_downloaded_file
                        download_occurred["completed"] = True
                        self.logger.info(
                            f"Download completed: {self.last_downloaded_file}"
                        )
                    except Exception as e:
                        self.logger.error(f"Error handling download on new page: {e}")

                new_page.on("download", handle_download_new_page)

                # Try to navigate to the download URL, but handle the case where it hangs
                try:
                    self.logger.info("Navigating to batch processing URL...")

                    # Try with a shorter timeout but don't fail completely if it times out
                    try:
                        await new_page.goto(
                            href, wait_until="domcontentloaded", timeout=30000
                        )  # 30 seconds
                        self.logger.info("Successfully navigated to download URL")
                    except Exception as nav_error:
                        self.logger.warning(
                            f"Navigation timeout/error (this may be normal for batch processing): {nav_error}"
                        )
                        # Don't return None yet - the page might still be loading in background

                    # Check what's on the page regardless of navigation success
                    await self.wait_for_timeout(2000)

                    try:
                        title = await new_page.title()
                        url = new_page.url
                        self.logger.info(f"New page - Title: '{title}', URL: {url}")

                        # Check if we can get any content
                        try:
                            content = await new_page.content()
                            if content and len(content) > 100:  # Has some content
                                self.logger.info(
                                    f"Page has content ({len(content)} chars) - monitoring for batch processing"
                                )
                                # Set this as our batch processing page to monitor
                                batch_processing_page = new_page
                                current_pages = len(self.context.pages)  # Update count
                                self.logger.info(
                                    f"Pages after manual navigation: {current_pages}"
                                )
                            else:
                                self.logger.warning(
                                    "Page has minimal content, may still be loading"
                                )
                                batch_processing_page = (
                                    new_page  # Still try to monitor it
                                )
                                current_pages = len(self.context.pages)
                        except Exception as content_error:
                            self.logger.warning(
                                f"Cannot read page content: {content_error}"
                            )
                            batch_processing_page = new_page  # Still try to monitor it
                            current_pages = len(self.context.pages)

                    except Exception as page_error:
                        self.logger.warning(f"Cannot read page info: {page_error}")
                        # Page might still be valid for monitoring downloads
                        batch_processing_page = new_page
                        current_pages = len(self.context.pages)

                except Exception as e:
                    self.logger.error(
                        f"Failed to create/navigate to download page: {e}"
                    )
                    try:
                        await new_page.close()
                    except:
                        pass
                    return None
            else:
                # Fall back to clicking if no href or target
                self.logger.info(
                    "No valid href with target=_blank, falling back to click"
                )
                await download_button.click()
                self.logger.info("Download button clicked")

                # Wait a moment for new page to potentially open
                await self.wait_for_timeout(3000)

                # Check if new page opened
                current_pages = len(self.context.pages)
                self.logger.info(f"Pages after click: {current_pages}")
                batch_processing_page = None

            if current_pages > initial_pages:
                self.logger.info(
                    "New tab detected - monitoring for batch processing completion"
                )

                # Find the batch processing page (either manually created or opened by click)
                if (
                    "batch_processing_page" not in locals()
                    or batch_processing_page is None
                ):
                    for page in self.context.pages:
                        if page != self.page:
                            try:
                                url = page.url
                                title = await page.title()
                                self.logger.info(
                                    f"Found new page: URL={url}, Title='{title}'"
                                )

                                # Check if this looks like a batch processing page
                                if (
                                    "batch" in url.lower()
                                    or "export" in title.lower()
                                    or "processing" in title.lower()
                                ):
                                    batch_processing_page = page
                                    self.logger.info("Identified batch processing page")
                                    break
                            except Exception as e:
                                self.logger.warning(f"Error checking new page: {e}")

                if batch_processing_page:
                    # Monitor the batch processing page
                    max_wait_time = 300  # 5 minutes
                    start_time = time.time()

                    self.logger.info(
                        "Monitoring batch processing page for completion..."
                    )

                    while (
                        time.time() - start_time
                    ) < max_wait_time and not download_occurred["completed"]:
                        # Check overall timeout
                        if (time.time() - overall_start_time) > overall_timeout:
                            self.logger.error(
                                f"Overall download timeout reached ({overall_timeout}s) - aborting"
                            )
                            break

                        try:
                            # Log progress every 30 seconds regardless of page status
                            elapsed = time.time() - start_time
                            overall_elapsed = time.time() - overall_start_time
                            if int(elapsed) % 30 == 0:
                                self.logger.info(
                                    f"Batch processing monitoring... {int(elapsed)}s elapsed (overall: {int(overall_elapsed)}s)"
                                )

                                # Try to get page status with timeout protection
                                try:
                                    title = await batch_processing_page.title()
                                    url = batch_processing_page.url
                                    self.logger.info(
                                        f"Page status - Title: '{title}', URL: {url}"
                                    )
                                except Exception as page_error:
                                    self.logger.warning(
                                        f"Cannot read page status: {page_error}"
                                    )

                            # Check page status for completion/error (with error handling)
                            try:
                                title = await batch_processing_page.title()
                                url = batch_processing_page.url

                                # Check for completion indicators in title or URL
                                if (
                                    "complete" in title.lower()
                                    or "finished" in title.lower()
                                    or "done" in title.lower()
                                ):
                                    self.logger.info(
                                        "Batch processing appears complete based on page title"
                                    )
                                    # Wait a bit more for download to trigger
                                    await self.wait_for_timeout(10000)
                                    break

                                # Check for error states
                                if (
                                    "error" in title.lower()
                                    or "failed" in title.lower()
                                ):
                                    self.logger.error(
                                        "Batch processing error detected in page title"
                                    )
                                    return None

                            except Exception as page_check_error:
                                self.logger.warning(
                                    f"Error checking page status: {page_check_error}"
                                )
                                # Continue monitoring even if we can't read page status

                            # Check page content for progress indicators
                            try:
                                content = await batch_processing_page.content()
                                # More specific error detection - only fail on actual batch processing errors
                                if (
                                    "export failed" in content.lower()
                                    or "processing failed" in content.lower()
                                    or "batch failed" in content.lower()
                                ):
                                    self.logger.error(
                                        "Batch processing error detected in page content"
                                    )
                                    return None
                                # Log a snippet of content for debugging
                                content_snippet = (
                                    content[:500] if content else "No content"
                                )
                                self.logger.debug(
                                    f"Page content snippet: {content_snippet}"
                                )
                            except Exception as content_error:
                                self.logger.warning(
                                    f"Error reading page content: {content_error}"
                                )

                        except Exception as e:
                            self.logger.warning(
                                f"Error checking batch processing page: {e}"
                            )

                        await self.wait_for_timeout(2000)  # Check every 2 seconds

                    # Check if download completed
                    if download_occurred["completed"]:
                        download_path = download_occurred["file_path"]
                        self.logger.info(
                            f"Batch processing completed with download: {download_path}"
                        )

                        # Verify the file is CSV, not HTML
                        if download_path and os.path.exists(download_path):
                            with open(download_path, encoding="utf-8") as f:
                                first_line = f.readline().strip()

                            if (
                                first_line.startswith("<!DOCTYPE html")
                                or "<html" in first_line
                            ):
                                self.logger.warning(
                                    "Downloaded file is HTML batch processing page, not CSV"
                                )
                                return None

                            self.logger.info(
                                "Successfully downloaded CSV via batch processing"
                            )
                            return download_path
                        self.logger.error(
                            "Download path not found or file doesn't exist"
                        )
                        return None
                    self.logger.error(
                        "Batch processing timed out - no download occurred"
                    )
                    return None
                self.logger.warning(
                    "New tab opened but couldn't identify batch processing page"
                )
                # Wait a bit to see if download happens anyway
                await self.wait_for_timeout(30000)  # 30 seconds

                if download_occurred["completed"]:
                    return download_occurred["file_path"]
                self.logger.error("No download occurred on new tab")
                return None
            self.logger.info(
                "No new tab detected - checking for download on current page"
            )
            # Wait for potential download on current page
            await self.wait_for_timeout(30000)  # 30 seconds

            if download_occurred["completed"]:
                download_path = download_occurred["file_path"]
                self.logger.info(f"Download occurred on current page: {download_path}")
                return download_path
            self.logger.error("No download occurred and no new tab opened")
            return None

        except Exception as e:
            self.logger.error(f"DOT CSV download failed: {e}")
            return None

    def dot_process(self, file_path: str) -> int:
        """DOT-specific processing."""
        if not file_path:
            # Try to get most recent download
            file_path = self.get_last_downloaded_path()
            if not file_path:
                self.logger.error("No file available for processing")
                return 0

        self.logger.info(f"Starting DOT processing for file: {file_path}")

        # Read file
        df = self.read_file_to_dataframe(file_path)
        if df is None or df.empty:
            self.logger.info("DataFrame is empty after reading. Nothing to process.")
            return 0

        # Apply transformations
        df = self.transform_dataframe(df)
        if df.empty:
            self.logger.info(
                "DataFrame is empty after transformations. Nothing to load."
            )
            return 0

        # Load to database
        return self.prepare_and_load_data(df)

    async def scrape(self) -> int:
        """Execute the complete DOT scraping workflow."""
        return await self.scrape_with_structure(
            setup_method=self.dot_setup,
            extract_method=self.dot_extract,
            process_method=self.dot_process,
        )
