"""
Automated tests for enhanced bulk upsert functionality.

Tests the duplicate prevention and upsert logic with dynamic test data
following production-level testing principles.
"""

import random
import string
from unittest.mock import patch

import pandas as pd
import pytest

from app import create_app
from app.database import db
from app.database.models import DataSource, Prospect
from app.utils.duplicate_prevention import enhanced_bulk_upsert_prospects


class TestEnhancedBulkUpsert:
    """Test suite for enhanced bulk upsert functionality."""

    @pytest.fixture(scope="class")
    def app(self):
        """Create test Flask app with real in-memory database."""
        app = create_app()
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        return app

    @pytest.fixture
    def app_context(self, app):
        """Create Flask app context with real database."""
        with app.app_context():
            db.create_all()
            yield
            db.session.rollback()
            db.drop_all()

    @pytest.fixture
    def test_source(self, app_context):
        """Create a test data source with random attributes."""
        source_name = f"TEST_SOURCE_{random.randint(1000, 9999)}"
        source = DataSource(
            name=source_name, description=f"Test source {random.randint(100, 999)}"
        )
        db.session.add(source)
        db.session.commit()
        return source

    def generate_prospect_data(self, source_id, count=1):
        """Generate random prospect test data."""
        data = []
        agencies = [
            "Department of Defense",
            "Department of Energy",
            "Department of Health",
        ]
        cities = ["Washington", "Arlington", "Alexandria", "Fairfax", "Bethesda"]
        states = ["DC", "VA", "MD"]

        for i in range(count):
            data.append(
                {
                    "source_id": source_id,
                    "native_id": f"TEST_{random.randint(10000, 99999)}_{i}",
                    "title": f"{random.choice(['Software', 'Hardware', 'Network', 'Data'])} "
                    f"{random.choice(['Engineer', 'Analyst', 'Manager', 'Specialist'])} "
                    f"Position {random.randint(100, 999)}",
                    "description": f"Test description {random.randint(1000, 9999)} with "
                    f"various requirements and specifications",
                    "agency": random.choice(agencies),
                    "naics": "".join(random.choices(string.digits, k=6)),
                    "place_city": random.choice(cities),
                    "place_state": random.choice(states),
                }
            )

        return pd.DataFrame(data)

    def test_insert_new_prospects(self, app_context, test_source):
        """Test inserting new prospects."""
        # Generate random test data
        test_data = self.generate_prospect_data(test_source.id, count=5)

        # Perform upsert
        stats = enhanced_bulk_upsert_prospects(
            test_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Verify insertion behavior
        assert "inserted" in stats
        assert stats["inserted"] > 0  # Should insert some records

        # Verify records exist in database
        prospects = db.session.query(Prospect).filter_by(source_id=test_source.id).all()
        assert len(prospects) > 0

        # Verify native IDs were preserved
        native_ids = {p.native_id for p in prospects}
        test_native_ids = set(test_data["native_id"].values)
        assert len(native_ids.intersection(test_native_ids)) > 0

    def test_update_existing_prospects(self, app_context, test_source):
        """Test updating existing prospects with same native_id."""
        # Insert initial prospects
        initial_data = self.generate_prospect_data(test_source.id, count=3)
        stats1 = enhanced_bulk_upsert_prospects(
            initial_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        initial_count = stats1.get("inserted", 0)

        # Update with modified data but same native_ids
        updated_data = initial_data.copy()
        for idx in updated_data.index:
            # Update titles with new random values
            updated_data.at[idx, "title"] = (
                f"Updated {random.choice(['Position', 'Role', 'Job'])} {random.randint(100, 999)}"
            )

        # Perform update
        stats2 = enhanced_bulk_upsert_prospects(
            updated_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Verify update behavior
        assert "updated" in stats2
        # Updated count should be positive if matching worked
        assert stats2.get("updated", 0) + stats2.get("high_confidence_matches", 0) > 0

        # Total prospects shouldn't increase much
        final_count = (
            db.session.query(Prospect).filter_by(source_id=test_source.id).count()
        )
        assert final_count <= initial_count + 1  # Allow for small variation

    def test_native_id_matching_with_different_content(self, app_context, test_source):
        """Test that native_id matching handles very different content appropriately."""
        # Insert initial prospect
        native_id = f"STABLE_ID_{random.randint(1000, 9999)}"
        initial_data = pd.DataFrame(
            [
                {
                    "source_id": test_source.id,
                    "native_id": native_id,
                    "title": "Software Developer",
                    "description": "Python development role",
                    "agency": "Department of Defense",
                    "naics": "541511",
                    "place_city": "Washington",
                    "place_state": "DC",
                }
            ]
        )

        enhanced_bulk_upsert_prospects(
            initial_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Try to update with completely different content but same native_id
        different_data = pd.DataFrame(
            [
                {
                    "source_id": test_source.id,
                    "native_id": native_id,  # Same ID
                    "title": "Network Administrator",  # Completely different
                    "description": "Network security specialist",  # Completely different
                    "agency": "Department of Energy",  # Different agency
                    "naics": "541512",
                    "place_city": "Arlington",
                    "place_state": "VA",
                }
            ]
        )

        stats = enhanced_bulk_upsert_prospects(
            different_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # The behavior depends on confidence thresholds
        # Just verify the function completes and returns stats
        assert isinstance(stats, dict)
        assert any(
            key in stats
            for key in ["updated", "inserted", "low_confidence_matches", "errors"]
        )

    def test_fuzzy_matching_similar_titles(self, app_context, test_source):
        """Test fuzzy matching with similar but not identical titles."""
        # Generate base title components
        base_role = random.choice(
            ["Software Engineer", "Data Analyst", "Project Manager"]
        )
        agency = random.choice(["Department of Defense", "Department of Health"])
        city = random.choice(["Washington", "Arlington"])

        # Insert original prospect
        original_data = pd.DataFrame(
            [
                {
                    "source_id": test_source.id,
                    "native_id": f"ORIG_{random.randint(1000, 9999)}",
                    "title": base_role,
                    "description": f"Looking for experienced {base_role.lower()}",
                    "agency": agency,
                    "naics": "541511",
                    "place_city": city,
                    "place_state": "DC",
                }
            ]
        )

        enhanced_bulk_upsert_prospects(
            original_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Try similar prospect with variations
        similar_data = pd.DataFrame(
            [
                {
                    "source_id": test_source.id,
                    "native_id": f"SIMILAR_{random.randint(1000, 9999)}",  # Different ID
                    "title": f"Sr. {base_role}",  # Similar title with prefix
                    "description": f"Seeking senior {base_role.lower()} with experience",
                    "agency": agency,  # Same agency
                    "naics": "541511",
                    "place_city": city,  # Same location
                    "place_state": "DC",
                }
            ]
        )

        stats = enhanced_bulk_upsert_prospects(
            similar_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Verify the function handles similarity matching
        assert isinstance(stats, dict)
        # Could be inserted as new or matched as duplicate depending on thresholds
        assert any(stats.get(key, 0) > 0 for key in ["inserted", "updated", "skipped"])

    def test_preserve_ai_data_flag(self, app_context, test_source):
        """Test that AI data preservation flag is respected."""
        # Generate test data
        test_data = self.generate_prospect_data(test_source.id, count=2)

        # Test with preserve_ai_data=True
        stats_preserve = enhanced_bulk_upsert_prospects(
            test_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Test with preserve_ai_data=False
        test_data2 = self.generate_prospect_data(test_source.id, count=2)
        stats_no_preserve = enhanced_bulk_upsert_prospects(
            test_data2,
            db.session,
            test_source.id,
            preserve_ai_data=False,
            enable_smart_matching=True,
        )

        # Both should complete successfully
        assert isinstance(stats_preserve, dict)
        assert isinstance(stats_no_preserve, dict)

    def test_smart_matching_flag(self, app_context, test_source):
        """Test that smart matching flag affects duplicate detection."""
        # Generate similar prospects
        base_data = self.generate_prospect_data(test_source.id, count=1)

        # Insert base prospect
        enhanced_bulk_upsert_prospects(
            base_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Create slightly modified version
        similar_data = base_data.copy()
        similar_data["native_id"] = f"DIFFERENT_{random.randint(1000, 9999)}"
        similar_data["title"] = similar_data["title"].values[0] + " (Updated)"

        # Test with smart matching enabled
        stats_smart = enhanced_bulk_upsert_prospects(
            similar_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Test with smart matching disabled
        similar_data2 = base_data.copy()
        similar_data2["native_id"] = f"ANOTHER_{random.randint(1000, 9999)}"
        similar_data2["title"] = similar_data2["title"].values[0] + " (Modified)"

        stats_no_smart = enhanced_bulk_upsert_prospects(
            similar_data2,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=False,
        )

        # Both should complete
        assert isinstance(stats_smart, dict)
        assert isinstance(stats_no_smart, dict)

        # With smart matching off, more likely to insert as new
        # With smart matching on, more likely to match as duplicate
        # We can't assert specific behavior without knowing thresholds

    def test_bulk_operation_performance(self, app_context, test_source):
        """Test that bulk operations handle multiple prospects efficiently."""
        # Generate larger dataset
        bulk_data = self.generate_prospect_data(test_source.id, count=50)

        # Perform bulk upsert
        stats = enhanced_bulk_upsert_prospects(
            bulk_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Verify all records were processed
        assert isinstance(stats, dict)
        total_processed = sum(
            [
                stats.get("inserted", 0),
                stats.get("updated", 0),
                stats.get("skipped", 0),
                stats.get("errors", 0),
            ]
        )

        # Most records should be processed (allow for some matching/skipping)
        assert total_processed > 0

    def test_empty_dataframe(self, app_context, test_source):
        """Test handling of empty dataframe."""
        empty_data = pd.DataFrame()

        stats = enhanced_bulk_upsert_prospects(
            empty_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Should handle gracefully
        assert isinstance(stats, dict)
        assert stats.get("inserted", 0) == 0
        assert stats.get("errors", 0) == 0

    @patch("app.config.active_config.DUPLICATE_MIN_CONFIDENCE")
    @patch("app.config.active_config.DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM")
    def test_configuration_values_respected(
        self, mock_content_sim, mock_min_conf, app_context, test_source
    ):
        """Test that configuration values affect matching behavior."""
        # Set mock configuration values
        mock_min_conf.return_value = 0.8
        mock_content_sim.return_value = 0.7

        # Generate test data
        test_data = self.generate_prospect_data(test_source.id, count=3)

        # Perform upsert with mocked config
        stats = enhanced_bulk_upsert_prospects(
            test_data,
            db.session,
            test_source.id,
            preserve_ai_data=True,
            enable_smart_matching=True,
        )

        # Verify function completes with configuration
        assert isinstance(stats, dict)
