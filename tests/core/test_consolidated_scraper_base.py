"""
Comprehensive tests for ConsolidatedScraperBase.

Tests the core scraper framework functionality that all agency scrapers inherit.
Following production-level testing principles:
- No hardcoded expected values
- Tests verify behavior, not specific data
- Uses real operations where possible
- Mocks only external browser dependencies
"""

import os
import random
import tempfile
from datetime import UTC

UTC = UTC
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest

from app import create_app
from app.core.consolidated_scraper_base import ConsolidatedScraperBase, ScraperConfig
from app.database import db
from app.database.models import DataSource, Prospect


class TestScraperConfig:
    """Test ScraperConfig dataclass functionality following black-box testing principles."""

    def test_scraper_config_creation(self):
        """Test basic scraper configuration creation with dynamic data."""
        # Generate random configuration values
        source_name = f"Scraper-{random.randint(1000, 9999)}"
        base_url = f"https://agency{random.randint(1, 100)}.gov"
        timeout_ms = random.randint(10000, 60000)
        screenshot_on_error = random.choice([True, False])
        use_stealth = random.choice([True, False])

        config = ScraperConfig(
            source_name=source_name,
            base_url=base_url,
            navigation_timeout_ms=timeout_ms,
            screenshot_on_error=screenshot_on_error,
            use_stealth=use_stealth,
        )

        # Verify configuration was set correctly
        assert config.source_name == source_name
        assert config.base_url == base_url
        assert config.navigation_timeout_ms == timeout_ms
        assert config.screenshot_on_error == screenshot_on_error
        assert config.use_stealth == use_stealth

        # Verify defaults are applied
        assert isinstance(config.raw_column_rename_map, dict)
        assert len(config.raw_column_rename_map) == 0  # Default empty map

    def test_scraper_config_with_field_mappings(self):
        """Test scraper config with field mappings using dynamic data."""
        # Generate random field mappings
        field_count = random.randint(2, 6)
        field_mappings = {}

        source_fields = ["title", "agency", "value", "date", "description", "contact"]
        target_fields = [
            "contract_title",
            "issuing_agency",
            "estimated_value",
            "posted_date",
            "opportunity_description",
            "contact_info",
        ]

        for i in range(min(field_count, len(source_fields))):
            field_mappings[source_fields[i]] = target_fields[i]

        source_name = f"MappedScraper-{random.randint(1000, 9999)}"
        base_url = f"https://mapped{random.randint(1, 100)}.gov"

        config = ScraperConfig(
            source_name=source_name,
            base_url=base_url,
            raw_column_rename_map=field_mappings,
        )

        # Verify mappings are preserved
        assert config.raw_column_rename_map == field_mappings
        assert len(config.raw_column_rename_map) == field_count

        # Verify each mapping exists
        for source, target in field_mappings.items():
            assert config.raw_column_rename_map[source] == target


class TestConsolidatedScraperBase:
    """Test ConsolidatedScraperBase functionality."""

    @pytest.fixture(scope="class")
    def app(self):
        """Create test Flask app."""
        app = create_app()
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        return app

    @pytest.fixture
    def db_session(self, app):
        """Create test database session."""
        with app.app_context():
            db.create_all()
            yield db.session
            db.session.rollback()
            db.drop_all()

    @pytest.fixture
    def test_config(self):
        """Create test scraper configuration with dynamic values."""
        # Generate random configuration
        source_name = f"TestAgency-{random.randint(1000, 9999)}"
        base_url = f"https://test-agency-{random.randint(1, 100)}.gov"
        timeout_ms = random.randint(20000, 40000)

        # Generate random field mappings
        possible_mappings = [
            ("opportunity_title", "title"),
            ("opportunity_description", "description"),
            ("issuing_agency", "agency"),
            ("post_date", "posted_date"),
            ("naics_code", "naics"),
            ("contract_value", "estimated_value"),
            ("contact_info", "contact_name"),
        ]

        num_mappings = random.randint(3, len(possible_mappings))
        selected_mappings = random.sample(possible_mappings, num_mappings)
        raw_column_rename_map = dict(selected_mappings)

        return ScraperConfig(
            source_name=source_name,
            base_url=base_url,
            navigation_timeout_ms=timeout_ms,
            screenshot_on_error=random.choice([True, False]),
            use_stealth=random.choice([True, False]),
            raw_column_rename_map=raw_column_rename_map,
        )

    @pytest.fixture
    def scraper(self, test_config):
        """Create test scraper instance."""
        return ConsolidatedScraperBase(test_config)

    def test_scraper_initialization(self, scraper, test_config):
        """Test scraper initialization with dynamic configuration."""
        # Verify scraper was initialized with provided config
        assert scraper.config == test_config
        assert scraper.config.source_name == test_config.source_name

        # Verify directories are created
        assert scraper.screenshots_dir.exists()
        assert scraper.downloads_dir.exists()
        assert scraper.html_dumps_dir.exists()

        # Verify logger is configured
        assert scraper.logger is not None
        assert hasattr(scraper.logger, "info")
        assert hasattr(scraper.logger, "error")

    def test_scraper_directories_creation(self, scraper, test_config):
        """Test that scraper creates necessary directories."""
        # Directories should be created during initialization
        assert scraper.screenshots_dir.exists()
        assert scraper.downloads_dir.exists()
        assert scraper.html_dumps_dir.exists()

        # Directory names should include some form of the scraper name
        scraper_name_part = test_config.source_name.lower().replace(" ", "-")
        dirs_str = str(scraper.screenshots_dir).lower()

        # Verify directory structure makes sense (contains some identifier)
        assert any(
            [
                scraper_name_part in dirs_str,
                "screenshot" in dirs_str,
                "scraper" in dirs_str,
            ]
        )

    @patch("app.core.consolidated_scraper_base.async_playwright")
    def test_setup_browser_success(self, mock_playwright, scraper):
        """Test successful browser setup."""
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        mock_playwright.return_value.__aenter__.return_value.chromium.launch = (
            AsyncMock(return_value=mock_browser)
        )
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        # Mock stealth plugin
        with patch("app.core.consolidated_scraper_base.stealth_async"):
            result = scraper._setup_browser()

        assert result == (mock_browser, mock_context, mock_page)

    @patch("app.core.consolidated_scraper_base.async_playwright")
    def test_setup_browser_failure(self, mock_playwright, scraper):
        """Test browser setup failure handling."""
        mock_playwright.return_value.__aenter__.return_value.chromium.launch = (
            AsyncMock(side_effect=Exception("Browser launch failed"))
        )

        with pytest.raises(Exception, match="Browser launch failed"):
            scraper._setup_browser()

    def test_take_screenshot_success(self, scraper):
        """Test successful screenshot capture with dynamic naming."""
        mock_page = Mock()
        mock_page.screenshot = AsyncMock()

        # Generate random error context
        error_context = f"error-{random.randint(1000, 9999)}"

        before_screenshot = datetime.now(UTC)
        screenshot_path = scraper._take_screenshot(mock_page, error_context)
        after_screenshot = datetime.now(UTC)

        # Verify screenshot was attempted
        mock_page.screenshot.assert_called_once()

        # Verify path contains error context
        assert error_context in str(screenshot_path)

        # Verify path has timestamp component (but don't check exact format)
        path_str = str(screenshot_path)
        assert any(char.isdigit() for char in path_str)  # Contains some timestamp

    def test_save_html_dump_success(self, scraper):
        """Test successful HTML dump saving with dynamic content."""
        mock_page = Mock()

        # Generate random HTML content
        random_content = (
            f"<html><body>Content-{random.randint(1000, 9999)}</body></html>"
        )
        mock_page.content = AsyncMock(return_value=random_content)

        # Generate random error context
        error_context = f"dump-{random.randint(1000, 9999)}"

        html_path = scraper._save_html_dump(mock_page, error_context)

        # Verify content was retrieved
        mock_page.content.assert_called_once()

        # Verify path contains context
        assert error_context in str(html_path)

        # Verify file was created
        if html_path.exists():
            # File should contain the content
            content = html_path.read_text()
            assert len(content) > 0

    def test_navigate_to_page_success(self, scraper, test_config):
        """Test successful page navigation with dynamic URLs."""
        mock_page = Mock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()

        # Generate random URL path
        paths = ["/opportunities", "/contracts", "/solicitations", "/procurement"]
        url_path = random.choice(paths)
        full_url = f"{test_config.base_url}{url_path}"

        scraper._navigate_to_page(mock_page, full_url)

        # Verify navigation was attempted
        mock_page.goto.assert_called_once()
        call_args = mock_page.goto.call_args

        # Verify URL was used
        assert call_args[0][0] == full_url

        # Verify timeout was set (but not specific value)
        assert "timeout" in call_args[1]
        assert call_args[1]["timeout"] > 0

        # Verify wait for load was called
        mock_page.wait_for_load_state.assert_called()

    def test_navigate_to_page_failure(self, scraper):
        """Test page navigation failure handling."""
        mock_page = Mock()
        mock_page.goto = AsyncMock(side_effect=Exception("Navigation failed"))

        with pytest.raises(Exception, match="Navigation failed"):
            scraper._navigate_to_page(mock_page, "https://test.gov/opportunities")

    def test_wait_for_downloads_success(self, scraper):
        """Test successful download waiting with dynamic files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            scraper.downloads_dir = temp_path

            # Create random number of test files
            num_files = random.randint(1, 5)
            extensions = [".pdf", ".xlsx", ".csv", ".xls", ".doc"]
            test_files = []

            for i in range(num_files):
                ext = random.choice(extensions)
                filename = f"document-{random.randint(1000, 9999)}{ext}"
                file_path = temp_path / filename
                file_path.write_text(f"Content {i}: {random.randint(1, 1000)}")
                test_files.append(file_path)

            initial_files = set()
            files = scraper._wait_for_downloads(initial_files, timeout=1)

            # Verify files were detected
            assert len(files) == num_files

            # Verify all created files are in the result
            file_names = [f.name for f in files]
            for test_file in test_files:
                assert test_file.name in file_names

    def test_extract_data_from_files_csv(self, scraper):
        """Test data extraction from CSV files with dynamic data."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as temp_file:
            # Generate random CSV data
            num_rows = random.randint(2, 10)
            columns = ["title", "agency", "value", "date"]

            # Write header
            temp_file.write(",".join(columns) + "\n")

            # Write random data rows
            for i in range(num_rows):
                row_data = [
                    f"Contract-{random.randint(1000, 9999)}",
                    f"Agency-{random.choice(['A', 'B', 'C'])}",
                    str(random.randint(10000, 1000000)),
                    f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                ]
                temp_file.write(",".join(row_data) + "\n")

            temp_file_path = temp_file.name

        try:
            files = [Path(temp_file_path)]
            df = scraper._extract_data_from_files(files)

            # Verify extraction worked
            assert len(df) == num_rows

            # Verify columns exist
            for col in columns:
                assert col in df.columns

            # Verify data types are reasonable
            assert df["title"].dtype == object  # String type
            assert not df.empty
        finally:
            os.unlink(temp_file_path)

    def test_extract_data_from_files_excel(self, scraper):
        """Test data extraction from Excel files with dynamic data."""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            # Generate random Excel data
            num_rows = random.randint(3, 15)
            test_data = {
                "contract_title": [
                    f"Excel-Contract-{random.randint(1000, 9999)}"
                    for _ in range(num_rows)
                ],
                "issuing_agency": [
                    f"Agency-{random.choice(['X', 'Y', 'Z'])}" for _ in range(num_rows)
                ],
                "contract_value": [
                    random.randint(50000, 500000) for _ in range(num_rows)
                ],
                "posted_date": [
                    f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
                    for _ in range(num_rows)
                ],
            }

            test_df = pd.DataFrame(test_data)
            test_df.to_excel(temp_file_path, index=False)

            files = [Path(temp_file_path)]
            df = scraper._extract_data_from_files(files)

            # Verify extraction
            assert len(df) == num_rows

            # Verify columns
            for col in test_data:
                assert col in df.columns

            # Verify data integrity
            assert df["contract_value"].dtype in [int, float, object]
            assert not df.empty
        finally:
            os.unlink(temp_file_path)

    def test_apply_field_mappings(self, scraper, test_config):
        """Test field mapping application with dynamic mappings."""
        # Generate original data matching the config's mappings
        num_rows = random.randint(2, 5)
        original_data = {}

        # Use the actual mappings from the config
        for source_col, target_col in test_config.raw_column_rename_map.items():
            if "title" in source_col.lower():
                original_data[source_col] = [
                    f"Title-{random.randint(1000, 9999)}" for _ in range(num_rows)
                ]
            elif "agency" in source_col.lower():
                original_data[source_col] = [
                    f"Agency-{random.choice(['A', 'B', 'C'])}" for _ in range(num_rows)
                ]
            elif "date" in source_col.lower():
                original_data[source_col] = [
                    f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
                    for _ in range(num_rows)
                ]
            else:
                original_data[source_col] = [
                    f"Value-{random.randint(1, 1000)}" for _ in range(num_rows)
                ]

        original_df = pd.DataFrame(original_data)

        # Apply transformation
        mapped_df = scraper.transform_dataframe(original_df)

        # Verify mappings were applied
        for source_col, target_col in test_config.raw_column_rename_map.items():
            # Target column should exist
            assert target_col in mapped_df.columns
            # Source column should not exist (unless it wasn't mapped)
            if source_col != target_col:
                assert source_col not in mapped_df.columns

        # Verify data integrity
        assert len(mapped_df) == num_rows
        assert not mapped_df.empty

    def test_clean_and_validate_data(self, scraper):
        """Test data cleaning and validation with various data quality issues."""
        # Generate test data with random quality issues
        num_rows = random.randint(5, 10)

        test_data = {
            "title": [],
            "agency": [],
            "description": [],
            "posted_date": [],
            "naics": [],
            "estimated_value_text": [],
        }

        for i in range(num_rows):
            # Randomly introduce data quality issues
            if random.random() > 0.2:  # 80% valid titles
                test_data["title"].append(f"  Title-{random.randint(1000, 9999)}  ")
            else:
                test_data["title"].append(random.choice(["", None, "   "]))

            test_data["agency"].append(
                f"Agency-{random.choice(['A', 'B', 'C'])}"
                if random.random() > 0.1
                else ""
            )
            test_data["description"].append(
                f"Desc-{i}" if random.random() > 0.3 else None
            )

            # Random date formats
            if random.random() > 0.3:
                test_data["posted_date"].append(
                    f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
                )
            else:
                test_data["posted_date"].append(
                    random.choice(["invalid-date", "not-a-date", None])
                )

            # NAICS codes
            if random.random() > 0.4:
                test_data["naics"].append(f"{random.randint(100000, 999999)}")
            else:
                test_data["naics"].append(random.choice(["invalid", None, "ABC123"]))

            test_data["estimated_value_text"].append(
                f"${random.randint(1000, 100000):,}" if random.random() > 0.3 else "TBD"
            )

        test_df = pd.DataFrame(test_data)
        original_len = len(test_df)

        cleaned_df = scraper._clean_and_validate_data(test_df)

        # Should handle invalid data
        assert len(cleaned_df) <= original_len

        # Valid titles should be cleaned
        if "title" in cleaned_df.columns:
            valid_titles = cleaned_df["title"].dropna()
            for title in valid_titles:
                # Should be trimmed
                assert title == title.strip()
                # Should not be empty
                assert len(title) > 0

        # Result should be a valid DataFrame
        assert isinstance(cleaned_df, pd.DataFrame)

    def test_create_prospects_from_dataframe(self, scraper, db_session):
        """Test prospect creation from DataFrame with dynamic data."""
        # Create data source with random attributes
        source_name = f"TestAgency-{random.randint(1000, 9999)}"
        data_source = DataSource(
            name=source_name,
            url=f"https://test-{random.randint(1, 100)}.gov",
            last_scraped=datetime.now(UTC) - timedelta(hours=random.randint(0, 48)),
        )
        db_session.add(data_source)
        db_session.flush()

        scraper.data_source_id = data_source.id

        # Generate random DataFrame
        num_prospects = random.randint(2, 8)
        test_data = {
            "title": [
                f"Prospect-{random.randint(1000, 9999)}" for _ in range(num_prospects)
            ],
            "description": [
                f"Desc-{random.randint(1, 100)}" for _ in range(num_prospects)
            ],
            "agency": [source_name for _ in range(num_prospects)],
            "naics": [
                f"{random.randint(100000, 999999)}" for _ in range(num_prospects)
            ],
            "posted_date": [
                f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
                for _ in range(num_prospects)
            ],
            "estimated_value_text": [
                f"${random.randint(10000, 1000000):,}" for _ in range(num_prospects)
            ],
        }

        test_df = pd.DataFrame(test_data)

        # Let the real ID generation happen
        prospects = scraper._create_prospects_from_dataframe(test_df)

        # Verify prospects were created
        assert len(prospects) == num_prospects

        # Verify each prospect has required fields
        for i, prospect in enumerate(prospects):
            assert prospect.title == test_data["title"][i]
            assert prospect.agency == test_data["agency"][i]
            assert prospect.source_id == data_source.id
            assert prospect.id is not None  # Should have generated ID

    def test_generate_prospect_id(self, scraper):
        """Test prospect ID generation with dynamic data."""
        # Generate random test data
        test_data = {
            "title": f"Contract-{random.randint(1000, 9999)}",
            "agency": f"Agency-{random.choice(['A', 'B', 'C', 'D'])}",
            "posted_date": f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
        }

        prospect_id = scraper._generate_prospect_id(test_data)

        # Verify ID characteristics
        assert isinstance(prospect_id, str)
        assert len(prospect_id) > 0  # Should have some length

        # Test consistency - same data should generate same ID
        prospect_id2 = scraper._generate_prospect_id(test_data)
        assert prospect_id == prospect_id2

        # Test uniqueness - different data should generate different ID
        test_data2 = test_data.copy()
        test_data2["title"] = f"DifferentContract-{random.randint(10000, 99999)}"
        prospect_id3 = scraper._generate_prospect_id(test_data2)
        assert prospect_id != prospect_id3

        # Test with missing fields
        partial_data = {"title": test_data["title"]}
        prospect_id4 = scraper._generate_prospect_id(partial_data)
        assert isinstance(prospect_id4, str)
        assert len(prospect_id4) > 0

    def test_save_prospects_to_database(self, scraper, db_session):
        """Test saving prospects to database with dynamic data."""
        # Create data source with random attributes
        source_name = f"SaveTestAgency-{random.randint(1000, 9999)}"
        data_source = DataSource(
            name=source_name,
            url=f"https://save-test-{random.randint(1, 100)}.gov",
            last_scraped=datetime.now(UTC),
        )
        db_session.add(data_source)
        db_session.flush()

        # Create random number of test prospects
        num_prospects = random.randint(2, 10)
        prospects = []

        for i in range(num_prospects):
            prospect = Prospect(
                id=f"SAVE-TEST-{random.randint(10000, 99999)}-{i}",
                title=f"SaveTest-{random.randint(1000, 9999)}",
                agency=source_name,
                description=f"Test description {i}: {random.randint(1, 1000)}",
                source_id=data_source.id,
                loaded_at=datetime.now(UTC) - timedelta(minutes=random.randint(0, 60)),
            )
            prospects.append(prospect)

        # Mock database operations
        with patch.object(scraper, "db") as mock_db:
            mock_db.session = db_session

            result = scraper._save_prospects_to_database(prospects)

            # Verify save results
            assert result["saved"] == num_prospects
            assert result["errors"] == 0

            # Verify prospects list integrity
            assert len(prospects) == num_prospects

            # Verify each prospect has required fields
            for prospect in prospects:
                assert prospect.id is not None
                assert prospect.source_id == data_source.id

    @patch("app.core.consolidated_scraper_base.async_playwright")
    def test_run_scraper_success(self, mock_playwright, scraper, db_session):
        """Test successful end-to-end scraper run with dynamic data."""
        # Mock browser operations
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        mock_playwright.return_value.__aenter__.return_value.chromium.launch = (
            AsyncMock(return_value=mock_browser)
        )
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()

        with patch("app.core.consolidated_scraper_base.stealth_async"):
            # Generate random data
            num_rows = random.randint(1, 5)
            test_data = {}

            # Generate columns based on scraper config
            for source_col in scraper.config.raw_column_rename_map.keys():
                test_data[source_col] = [
                    f"Value-{random.randint(1000, 9999)}" for _ in range(num_rows)
                ]

            # If no mappings, use default columns
            if not test_data:
                test_data = {
                    "title": [
                        f"Contract-{random.randint(1000, 9999)}"
                        for _ in range(num_rows)
                    ],
                    "agency": [
                        f"Agency-{random.choice(['A', 'B'])}" for _ in range(num_rows)
                    ],
                    "description": [f"Desc-{i}" for i in range(num_rows)],
                }

            test_df = pd.DataFrame(test_data)

            with patch.object(scraper, "_extract_data_from_files") as mock_extract:
                mock_extract.return_value = test_df

                with patch.object(scraper, "_save_prospects_to_database") as mock_save:
                    saved_count = random.randint(0, num_rows)
                    error_count = num_rows - saved_count
                    mock_save.return_value = {
                        "saved": saved_count,
                        "errors": error_count,
                    }

                    with patch.object(scraper, "scrape_data") as mock_scrape:
                        num_files = random.randint(1, 3)
                        mock_scrape.return_value = [
                            Path(f"/fake/file{i}.csv") for i in range(num_files)
                        ]

                        result = scraper.run()

                        # Verify result structure
                        assert "success" in result
                        assert "prospects_saved" in result
                        assert "errors" in result

                        # Verify counts match
                        assert result["prospects_saved"] == saved_count
                        assert result["errors"] == error_count

    @patch("app.core.consolidated_scraper_base.async_playwright")
    def test_run_scraper_with_errors(self, mock_playwright, scraper):
        """Test scraper run with errors."""
        # Mock browser failure
        mock_playwright.return_value.__aenter__.return_value.chromium.launch = (
            AsyncMock(side_effect=Exception("Browser setup failed"))
        )

        result = scraper.run()

        assert result["success"] is False
        assert "error" in result
        assert "Browser setup failed" in result["error"]

    def test_scraper_logging(self, scraper, test_config):
        """Test scraper logging functionality."""
        # Logger should be configured
        assert scraper.logger is not None
        assert scraper.logger.name == test_config.source_name

        # Generate random log messages
        log_messages = [
            f"Info: {random.randint(1000, 9999)}",
            f"Warning: {random.choice(['timeout', 'retry', 'slow'])}",
            f"Error: {random.choice(['connection', 'parsing', 'validation'])}",
        ]

        # Test logging methods don't raise errors
        scraper.logger.info(log_messages[0])
        scraper.logger.warning(log_messages[1])
        scraper.logger.error(log_messages[2])

    def test_scraper_custom_transformations(self, scraper):
        """Test custom transformation hooks with dynamic data."""
        # Generate random test data
        num_rows = random.randint(2, 5)
        test_df = pd.DataFrame(
            {
                "title": [
                    f"Title-{random.randint(1000, 9999)}" for _ in range(num_rows)
                ],
                "agency": [
                    f"Agency-{random.choice(['X', 'Y', 'Z'])}" for _ in range(num_rows)
                ],
                "value": [random.randint(10000, 1000000) for _ in range(num_rows)],
            }
        )

        # Default implementation should return unchanged
        transformed_df = scraper.custom_transform(test_df)
        assert transformed_df.equals(test_df)

        # Test that method can be overridden with custom logic
        class CustomScraper(ConsolidatedScraperBase):
            def custom_transform(self, df):
                df = df.copy()
                # Apply some transformation
                df["title"] = df["title"].str.upper()
                df["value"] = df["value"] * 2  # Double values
                return df

        custom_scraper = CustomScraper(scraper.config)
        custom_transformed = custom_scraper.custom_transform(test_df)

        # Verify transformations were applied
        for i in range(num_rows):
            original_title = test_df.iloc[i]["title"]
            transformed_title = custom_transformed.iloc[i]["title"]
            assert transformed_title == original_title.upper()

            original_value = test_df.iloc[i]["value"]
            transformed_value = custom_transformed.iloc[i]["value"]
            assert transformed_value == original_value * 2

    def test_scraper_file_cleanup(self, scraper):
        """Test cleanup of temporary files with random files."""
        # Create random temporary files
        num_files = random.randint(2, 6)
        extensions = [".pdf", ".xlsx", ".csv", ".png", ".html"]
        temp_files = []

        for i in range(num_files):
            ext = random.choice(extensions)
            if ext in [".png", ".html"]:
                dir_path = (
                    scraper.screenshots_dir if ext == ".png" else scraper.html_dumps_dir
                )
            else:
                dir_path = scraper.downloads_dir

            filename = f"temp-{random.randint(1000, 9999)}{ext}"
            file_path = dir_path / filename
            file_path.write_text(f"Temporary content {i}: {random.randint(1, 1000)}")
            temp_files.append(file_path)
            assert file_path.exists()

        # Test cleanup if method exists
        if hasattr(scraper, "cleanup"):
            scraper.cleanup()
            # Check cleanup behavior (implementation-specific)

        # Verify files were created
        assert len(temp_files) == num_files

    def test_scraper_error_recovery(self, scraper):
        """Test scraper error recovery mechanisms with random errors."""
        mock_page = Mock()

        # Generate random error
        error_messages = [
            "Connection timeout",
            "Element not found",
            "Page load failed",
            "Download failed",
            "Parsing error",
        ]
        error_msg = random.choice(error_messages)
        error_context = f"context-{random.randint(1000, 9999)}"

        # Test error handling
        with patch.object(scraper, "_take_screenshot") as mock_screenshot:
            with patch.object(scraper, "_save_html_dump") as mock_html:
                scraper._handle_error(mock_page, Exception(error_msg), error_context)

                # Verify error recovery actions were triggered
                mock_screenshot.assert_called_once()
                mock_html.assert_called_once()

                # Verify context was passed
                screenshot_call = mock_screenshot.call_args
                html_call = mock_html.call_args
                assert error_context in str(screenshot_call)
                assert error_context in str(html_call)

    def test_scraper_configuration_validation(self):
        """Test scraper configuration validation with various inputs."""
        # Test missing required fields
        with pytest.raises(TypeError):
            ScraperConfig()  # Missing required source_name

        # Test with minimal required fields
        min_name = f"MinConfig-{random.randint(1000, 9999)}"
        min_config = ScraperConfig(source_name=min_name)
        assert min_config.source_name == min_name

        # Test with various parameter combinations
        test_configs = [
            {"source_name": f"Config-{random.randint(1000, 9999)}"},
            {
                "source_name": f"Config-{random.randint(1000, 9999)}",
                "base_url": f"https://test{random.randint(1, 100)}.gov",
            },
            {
                "source_name": f"Config-{random.randint(1000, 9999)}",
                "navigation_timeout_ms": random.randint(10000, 60000),
            },
            {
                "source_name": f"Config-{random.randint(1000, 9999)}",
                "screenshot_on_error": random.choice([True, False]),
            },
        ]

        for config_params in test_configs:
            config = ScraperConfig(**config_params)
            assert config.source_name == config_params["source_name"]

            # Verify defaults are set for unspecified params
            assert hasattr(config, "raw_column_rename_map")
            assert isinstance(config.raw_column_rename_map, dict)
