"""DOC scraper using the consolidated architecture.
Preserves all original DOC-specific functionality including link text finding and fiscal quarter processing.
"""

import pandas as pd

from app.config import active_config
from app.core.consolidated_scraper_base import ConsolidatedScraperBase
from app.core.scraper_configs import get_scraper_config
from app.utils.value_and_date_parsing import fiscal_quarter_to_date


class DocScraper(ConsolidatedScraperBase):
    """Consolidated DOC scraper.
    Preserves all original functionality including link text finding and custom transforms.
    """

    def __init__(self):
        config = get_scraper_config("doc")
        config.base_url = active_config.COMMERCE_FORECAST_URL
        super().__init__(config)

    def _custom_doc_transforms(self, df: pd.DataFrame) -> pd.DataFrame:
        """Custom DOC transformations preserving the original logic.
        Derives release date from fiscal year/quarter and handles place country standardization.
        """
        try:
            self.logger.info("Applying custom DOC transformations...")

            # Derive Solicitation Date (release_date_final) from FY/Quarter
            # Use original Excel column names (before renaming)
            if (
                "Estimated Solicitation Fiscal Year" in df.columns
                and "Estimated Solicitation Fiscal Quarter" in df.columns
            ):
                # Format quarter column correctly for fiscal_quarter_to_date
                df["solicitation_qtr_fmt"] = (
                    df["Estimated Solicitation Fiscal Quarter"]
                    .astype(str)
                    .apply(
                        lambda x: f"Q{x.split('.')[0]}" if pd.notna(x) and x else None
                    )
                )
                df["solicitation_fyq_combined"] = (
                    df["Estimated Solicitation Fiscal Year"].astype(str).fillna("")
                    + " "
                    + df["solicitation_qtr_fmt"].fillna("")
                )

                parsed_sol_date_info = df["solicitation_fyq_combined"].apply(
                    lambda x: (
                        fiscal_quarter_to_date(x.strip())
                        if pd.notna(x) and x.strip()
                        else (None, None)
                    )
                )
                df["release_date_final"] = parsed_sol_date_info.apply(
                    lambda x: x[0].date() if x[0] else None
                )
                self.logger.debug(
                    "Derived 'release_date_final' from fiscal year and quarter."
                )
            else:
                df["release_date_final"] = None
                self.logger.warning(
                    "Could not derive 'release_date_final'; 'Estimated Solicitation Fiscal Year' or 'Estimated Solicitation Fiscal Quarter' missing."
                )

            # Initialize award dates as None (DOC source doesn't provide them)
            df["award_date_final"] = None
            df["award_fiscal_year_final"] = (
                pd.NA
            )  # Use pandas NA for Int64 compatibility
            self.logger.debug(
                "Initialized 'award_date_final' and 'award_fiscal_year_final' to None/NA."
            )

            # Default place_country_final to 'USA' if not present or NaN
            # Use original Excel column name (before renaming)
            if "Place Of Performance Country" in df.columns:
                df["place_country_final"] = df["Place Of Performance Country"].fillna(
                    "USA"
                )
            else:
                df["place_country_final"] = "USA"
            self.logger.debug(
                "Processed 'place_country_final', defaulting to USA if needed."
            )

            # Ensure agency is present (DOC sometimes treats Organization as agency)
            if "agency" not in df.columns and "Organization" in df.columns:
                df["agency"] = df["Organization"]
                self.logger.debug("Mapped 'Organization' to 'agency' (DOC).")

        except Exception as e:
            self.logger.warning(f"Error in _custom_doc_transforms: {e}")

        return df

    def _doc_create_extras(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create extras JSON with DOC-specific fields that aren't in core schema.
        Captures 15 additional data points for comprehensive data retention.
        """
        try:
            # Define DOC-specific extras fields mapping (using original CSV column names)
            extras_fields = {
                "Workspace Number": "workspace_number",
                "Date Created": "date_created",
                "Office": "office",
                "Organization Unit": "organization_unit",
                "Months": "months",
                "Years": "years",
                "Anticipated Set Aside And Type": "anticipated_set_aside_and_type",  # Now storing competition info
                "Competition Strategy": "competition_strategy",  # Original competition strategy
                "New Requirement Or Recompete": "new_requirement_or_recompete",
                "Incumbent Contractor Name": "incumbent_contractor_name",
                "Awarded Contract Order Number": "awarded_contract_order_number",
                "Point Of Contact Name": "point_of_contact_name",
                "Point Of Contact Email": "point_of_contact_email",
                "Does This Acquisition Contain Information Technology": "contains_information_technology",
                "Date Created or Modified": "date_created_or_modified",
                "Awarded?": "awarded",
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
                f"Created DOC extras JSON for {len(extras_data)} rows with {len(extras_fields)} potential fields"
            )

        except Exception as e:
            self.logger.warning(f"Error in _doc_create_extras: {e}")

        return df

    async def doc_setup(self) -> bool:
        """DOC-specific setup: simple navigation to base URL."""
        if not self.base_url:
            self.logger.error("Base URL not configured.")
            return False

        self.logger.info(f"DOC setup: Navigating to {self.base_url}")
        return await self.navigate_to_url(self.base_url)

    async def doc_extract(self) -> str | None:
        """DOC-specific extraction: find link by text and download via browser click.
        Uses interactive download to avoid 403 errors with direct downloads.
        """
        self.logger.info(
            f"Starting DOC data file download process. Looking for link text: '{self.config.download_link_text}'"
        )

        # First, dismiss the newsletter popup if it appears
        popup_selector = "#prefix-dismissButton"
        try:
            popup_exists = await self.wait_for_selector(
                popup_selector, state="visible", timeout=5000
            )
            if popup_exists:
                self.logger.info("Newsletter popup detected, dismissing...")
                await self.click_element(popup_selector)
                await self.wait_for_timeout(2000)  # Wait for popup to close
                self.logger.info("Newsletter popup dismissed")
            else:
                self.logger.info("No newsletter popup detected, proceeding...")
        except Exception as e:
            self.logger.info(
                f"No popup found or error dismissing popup: {e}, proceeding with download..."
            )

        # Create selector for the link containing the specific text
        link_selector = f'a:has-text("{self.config.download_link_text}")'

        # Verify the link exists and is visible
        link_exists = await self.wait_for_selector(
            link_selector, state="visible", timeout=self.config.interaction_timeout_ms
        )
        if not link_exists:
            await self.capture_error_info(
                Exception("Download link not found"), "doc_link_not_found"
            )
            self.logger.error(
                f"Download link with text '{self.config.download_link_text}' not found on page."
            )
            return None

        self.logger.info(
            "Found download link, attempting interactive download via click"
        )

        # Download by clicking the link with fallback (avoids 403 errors)
        return await self.download_with_fallback(
            selector=link_selector, timeout=self.config.download_timeout_ms
        )

    def doc_process(self, file_path: str) -> int:
        """DOC-specific processing with Excel-specific read options."""
        if not file_path:
            # Try to get most recent download
            file_path = self.get_last_downloaded_path()
            if not file_path:
                self.logger.error("No file available for processing")
                return 0

        self.logger.info(f"Starting DOC processing for file: {file_path}")

        # Read Excel file with specific options (header at row 2)
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
        """Execute the complete DOC scraping workflow."""
        return await self.scrape_with_structure(
            setup_method=self.doc_setup,
            extract_method=self.doc_extract,
            process_method=self.doc_process,
        )
