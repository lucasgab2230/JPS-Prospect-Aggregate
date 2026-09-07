"""DOS scraper using the consolidated architecture.
Preserves all original DOS-specific functionality including direct download and complex value processing.
"""

import pandas as pd

from app.config import active_config
from app.core.consolidated_scraper_base import ConsolidatedScraperBase
from app.core.scraper_configs import get_scraper_config
from app.utils.value_and_date_parsing import fiscal_quarter_to_date, parse_value_range


class DOSForecastScraper(ConsolidatedScraperBase):
    """Consolidated DOS scraper.
    Preserves all original functionality including direct download and complex data processing.
    """

    def __init__(self):
        config = get_scraper_config("dos")
        config.base_url = active_config.DOS_FORECAST_URL  # For reference
        super().__init__(config)

    def _custom_dos_transforms(self, df: pd.DataFrame) -> pd.DataFrame:
        """Custom DOS transformations preserving the original complex logic.
        Handles priority-based date parsing, value range processing, and place standardization.
        """
        try:
            self.logger.info("Applying custom DOS transformations...")

            # Add row_index first for unique ID generation
            df.reset_index(drop=True, inplace=True)
            df["row_index"] = df.index
            self.logger.debug("Added 'row_index'.")

            # Date Parsing (Award Date/Year with priority)
            df["award_date_final"] = None
            df["award_fiscal_year_final"] = pd.NA

            if "award_fiscal_year_raw" in df.columns:
                df["award_fiscal_year_final"] = pd.to_numeric(
                    df["award_fiscal_year_raw"], errors="coerce"
                )

            if "award_date_raw" in df.columns:
                parsed_direct_award_date = pd.to_datetime(
                    df["award_date_raw"], errors="coerce"
                )
                # Fill award_date if it's still None (it is)
                df["award_date_final"] = df["award_date_final"].fillna(
                    parsed_direct_award_date.dt.date
                )

                # Fill fiscal year from this date if fiscal year is still NA
                needs_fy_from_date_mask = (
                    df["award_fiscal_year_final"].isna()
                    & parsed_direct_award_date.notna()
                )
                if needs_fy_from_date_mask.any():
                    df.loc[needs_fy_from_date_mask, "award_fiscal_year_final"] = (
                        parsed_direct_award_date[needs_fy_from_date_mask].dt.year
                    )

            if "award_qtr_raw" in df.columns:
                # Only parse quarter if both date and fiscal year are still missing
                needs_qtr_parse_mask = (
                    df["award_date_final"].isna()
                    & df["award_fiscal_year_final"].isna()
                    & df["award_qtr_raw"].notna()
                )
                if needs_qtr_parse_mask.any():
                    parsed_qtr_info = df.loc[
                        needs_qtr_parse_mask, "award_qtr_raw"
                    ].apply(
                        lambda x: (
                            fiscal_quarter_to_date(x) if pd.notna(x) else (None, None)
                        )
                    )
                    df.loc[needs_qtr_parse_mask, "award_date_final"] = (
                        parsed_qtr_info.apply(lambda x: x[0].date() if x[0] else None)
                    )
                    df.loc[needs_qtr_parse_mask, "award_fiscal_year_final"] = (
                        parsed_qtr_info.apply(lambda x: x[1])
                    )

            if "award_fiscal_year_final" in df.columns:  # Ensure Int64 type
                df["award_fiscal_year_final"] = df["award_fiscal_year_final"].astype(
                    "Int64"
                )
            self.logger.debug(
                "Processed award date and fiscal year columns with priority logic."
            )

            # Estimated Value Parsing (Priority: raw1 then raw2)
            df["estimated_value_final"] = pd.NA
            df["est_value_unit_final"] = pd.NA
            if (
                "estimated_value_raw1" in df.columns
                and df["estimated_value_raw1"].notna().any()
            ):
                parsed_vals = df["estimated_value_raw1"].apply(
                    lambda x: parse_value_range(x) if pd.notna(x) else (None, None)
                )
                df["estimated_value_final"] = parsed_vals.apply(lambda x: x[0])
                df["est_value_unit_final"] = parsed_vals.apply(lambda x: x[1])
            elif (
                "estimated_value_raw2" in df.columns
            ):  # Fallback to raw2 if raw1 was empty/not present
                # Assuming raw2 is numeric or simple string convertible to numeric, not a range
                df["estimated_value_final"] = pd.to_numeric(
                    df["estimated_value_raw2"], errors="coerce"
                )
                # est_value_unit_final remains NA if only raw2 is used and it's just a number
            self.logger.debug("Processed estimated value columns with priority logic.")

            # Solicitation Date (Release Date)
            if "release_date_raw" in df.columns:
                df["release_date_final"] = pd.to_datetime(
                    df["release_date_raw"], errors="coerce"
                ).dt.date
            else:
                df["release_date_final"] = None
            self.logger.debug("Processed release date column.")

            # Initialize NAICS (not in DOS source)
            df["naics_final"] = pd.NA
            self.logger.debug("Initialized 'naics_final' to NA.")

            # Initialize Place columns if missing after raw rename, default country USA
            df["place_city_final"] = (
                df["place_city_raw"] if "place_city_raw" in df.columns else None
            )
            df["place_state_final"] = (
                df["place_state_raw"] if "place_state_raw" in df.columns else None
            )
            df["place_country_final"] = (
                df["place_country_raw"] if "place_country_raw" in df.columns else "USA"
            )
            df.loc[df["place_country_final"].isna(), "place_country_final"] = (
                "USA"  # Default NA to USA
            )
            self.logger.debug(
                "Processed place columns, defaulting country to USA if needed."
            )

        except Exception as e:
            self.logger.warning(f"Error in _custom_dos_transforms: {e}")

        return df

    def _dos_create_extras(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create extras JSON with DOS-specific fields that aren't in core schema.
        Captures 11 additional data points for comprehensive data retention.
        """
        try:
            # Define DOS-specific extras fields mapping (using original CSV column names)
            extras_fields = {
                "New Requirement?": "new_requirement",
                "Length of Performance": "length_of_performance",
                "Facility Security Clearance": "facility_security_clearance",
                "Past Competition": "past_competition",
                "Past Set-Aside": "past_set_aside",
                "Incumbent Contractor": "incumbent_contractor",
                "Contract Vehicle": "contract_vehicle",
                "Program Funding Agency": "program_funding_agency",
                "Acquisition Phase": "acquisition_phase",
                "Extent Competed": "extent_competed",
                "Modified": "modified",
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
                f"Created DOS extras JSON for {len(extras_data)} rows with {len(extras_fields)} potential fields"
            )

        except Exception as e:
            self.logger.warning(f"Error in _dos_create_extras: {e}")

        return df

    async def dos_setup(self) -> bool:
        """DOS-specific setup: minimal setup for direct download.
        No browser navigation needed since it's a direct download.
        """
        self.logger.info(
            f"DOS Scraper setup initiated for direct download from: {self.config.direct_download_url}"
        )
        # No actual navigation needed, browser is set up by the base class
        return True

    async def dos_extract(self) -> str | None:
        """DOS-specific extraction: direct download from configured URL.
        Preserves original DOS direct download behavior.
        """
        self.logger.info(
            f"Attempting direct download for DOS from URL: {self.config.direct_download_url}"
        )

        # Download directly from the configured URL
        return await self.download_file_directly(self.config.direct_download_url)

    def dos_process(self, file_path: str) -> int:
        """DOS-specific processing with Excel-specific read options."""
        if not file_path:
            # Try to get most recent download
            file_path = self.get_last_downloaded_path()
            if not file_path:
                self.logger.error("No file available for processing")
                return 0

        self.logger.info(f"Starting DOS processing for file: {file_path}")

        # Read Excel file with specific options
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
        """Execute the complete DOS scraping workflow."""
        return await self.scrape_with_structure(
            setup_method=self.dos_setup,
            extract_method=self.dos_extract,
            process_method=self.dos_process,
        )
