"""
Comprehensive tests for database models.

Tests model validation, relationships, and business logic.
"""

from datetime import UTC

UTC = UTC
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.database import db
from app.database.models import (
    AIEnrichmentLog,
    DataSource,
    GoNoGoDecision,
    LLMOutput,
    Prospect,
)
from app.database.user_models import User


@pytest.fixture(scope="class")
def app():
    """Create test Flask app."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    return app


@pytest.fixture
def db_session(app):
    """Create test database session."""
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        db.drop_all()


class TestProspectModel:
    """Test Prospect model functionality."""

    def test_prospect_creation(self, db_session):
        """Test basic prospect creation with dynamic data."""
        import random
        import string

        # Generate random test data
        prospect_id = "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )
        native_id = f"NATIVE-{random.randint(1000, 9999)}"
        title = f"Contract {random.randint(1000, 9999)} - {''.join(random.choices(string.ascii_letters, k=8))}"
        description = " ".join(["word" + str(i) for i in random.sample(range(100), 10)])
        agency = f"Department of {random.choice(['Defense', 'Energy', 'Health', 'State', 'Commerce'])}"
        naics = str(random.randint(100000, 999999))
        value_min = random.randint(10000, 100000)
        value_max = value_min + random.randint(50000, 500000)
        value_text = f"${value_min:,} - ${value_max:,}"
        cities = ["Washington", "New York", "Chicago", "Los Angeles", "Seattle"]
        states = ["DC", "NY", "IL", "CA", "WA"]
        city_idx = random.randint(0, len(cities) - 1)
        contract_types = ["Fixed Price", "Cost Plus", "T&M", "IDIQ"]
        set_asides = ["Small Business", "8(a)", "WOSB", "HUBZone", None]

        prospect = Prospect(
            id=prospect_id,
            native_id=native_id,
            title=title,
            description=description,
            agency=agency,
            naics=naics,
            estimated_value_text=value_text,
            release_date=date.today(),
            award_date=date.today(),
            place_city=cities[city_idx],
            place_state=states[city_idx],
            contract_type=random.choice(contract_types),
            set_aside=random.choice(set_asides),
            loaded_at=datetime.now(UTC),
        )

        db_session.add(prospect)
        db_session.commit()

        # Verify prospect was created
        saved_prospect = db_session.get(Prospect, prospect_id)
        assert saved_prospect is not None
        assert saved_prospect.title == title
        assert saved_prospect.naics == naics
        assert (
            saved_prospect.enhancement_status is not None
        )  # Should have default value

    def test_prospect_required_fields(self, db_session):
        """Test prospect validation for required fields."""
        import random

        # Missing required id should fail
        title = f"Contract {random.randint(1000, 9999)}"
        prospect = Prospect(title=title, loaded_at=datetime.now(UTC))

        db_session.add(prospect)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_prospect_indexes(self, db_session):
        """Test that indexed fields work correctly with dynamic data."""
        import random
        import string

        num_prospects = random.randint(5, 15)
        agencies = [f"Agency-{random.choice(string.ascii_uppercase)}" for _ in range(3)]
        cities = ["Washington", "New York", "Chicago", "Los Angeles"]

        prospects = []
        agency_counts = dict.fromkeys(agencies, 0)
        city_counts = dict.fromkeys(cities, 0)

        for i in range(num_prospects):
            prospect_id = "".join(
                random.choices(string.ascii_letters + string.digits, k=10)
            )
            agency = random.choice(agencies)
            city = random.choice(cities)

            agency_counts[agency] += 1
            city_counts[city] += 1

            prospect = Prospect(
                id=prospect_id,
                title=f"Contract {random.randint(1000, 9999)}",
                agency=agency,
                naics=str(random.randint(100000, 999999)),
                place_city=city,
                loaded_at=datetime.now(UTC),
            )
            prospects.append(prospect)
            db_session.add(prospect)

        db_session.commit()

        # Test agency filtering - pick an agency that was used
        test_agency = random.choice([a for a in agencies if agency_counts[a] > 0])
        agency_prospects = (
            db_session.execute(select(Prospect).where(Prospect.agency == test_agency))
            .scalars()
            .all()
        )
        assert len(agency_prospects) == agency_counts[test_agency]

        # Test city filtering - pick a city that was used
        test_city = random.choice([c for c in cities if city_counts[c] > 0])
        city_prospects = (
            db_session.execute(select(Prospect).where(Prospect.place_city == test_city))
            .scalars()
            .all()
        )
        assert len(city_prospects) == city_counts[test_city]

    def test_prospect_llm_enhancement_fields(self, db_session):
        """Test LLM enhancement specific fields with dynamic data."""
        import random
        import string

        # Generate random test data
        prospect_id = "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )
        original_title = f"Original {random.randint(1000, 9999)}"
        original_desc = " ".join(
            ["word" + str(i) for i in random.sample(range(100), 5)]
        )
        value_min = random.randint(10000, 100000)
        value_max = value_min + random.randint(50000, 500000)
        value_text = f"${value_min:,}-${value_max:,}"

        prospect = Prospect(
            id=prospect_id,
            title=original_title,
            description=original_desc,
            estimated_value_text=value_text,
            loaded_at=datetime.now(UTC),
        )

        db_session.add(prospect)
        db_session.commit()

        # Generate random enhancement data
        enhanced_title = f"Enhanced {random.randint(1000, 9999)}"
        enhanced_value_min = Decimal(str(value_min))
        enhanced_value_max = Decimal(str(value_max))
        enhanced_value_single = Decimal(str(value_min + (value_max - value_min) // 2))
        naics_code = str(random.randint(100000, 999999))
        naics_desc = f"Service Category {random.randint(1, 100)}"
        contact_name = f"{random.choice(['John', 'Jane', 'Bob', 'Alice'])} {random.choice(['Smith', 'Johnson', 'Williams', 'Brown'])}"
        contact_email = f"contact{random.randint(1, 999)}@{random.choice(['agency', 'gov', 'mil'])}.gov"
        set_aside_types = ["SMALL_BUSINESS", "8A", "WOSB", "HUBZONE", "SDVOSB"]
        set_aside_labels = [
            "Small Business Set-Aside",
            "8(a) Set-Aside",
            "Women-Owned Small Business",
            "HUBZone",
            "Service-Disabled Veteran-Owned",
        ]
        set_aside_idx = random.randint(0, len(set_aside_types) - 1)
        model_versions = ["qwen3:latest", "llama2:13b", "mistral:7b"]

        # Update with LLM enhancements
        before_enhancement = datetime.now(UTC)
        prospect.ai_enhanced_title = enhanced_title
        prospect.estimated_value_min = enhanced_value_min
        prospect.estimated_value_max = enhanced_value_max
        prospect.estimated_value_single = enhanced_value_single
        prospect.naics = naics_code
        prospect.naics_source = "llm_inferred"
        prospect.naics_description = naics_desc
        prospect.primary_contact_email = contact_email
        prospect.primary_contact_name = contact_name
        prospect.set_aside_standardized = set_aside_types[set_aside_idx]
        prospect.set_aside_standardized_label = set_aside_labels[set_aside_idx]
        prospect.ollama_processed_at = datetime.now(UTC)
        prospect.ollama_model_version = random.choice(model_versions)
        after_enhancement = datetime.now(UTC)

        db_session.commit()

        # Verify enhancements
        enhanced_prospect = db_session.get(Prospect, prospect_id)
        assert enhanced_prospect.ai_enhanced_title == enhanced_title
        assert enhanced_prospect.estimated_value_single == enhanced_value_single
        assert enhanced_prospect.naics_source == "llm_inferred"
        assert enhanced_prospect.primary_contact_email == contact_email
        assert enhanced_prospect.ollama_processed_at is not None
        assert (
            before_enhancement
            <= enhanced_prospect.ollama_processed_at
            <= after_enhancement
        )

    def test_prospect_enhancement_status_tracking(self, db_session):
        """Test enhancement status and tracking fields with dynamic data."""
        import random
        import string

        prospect_id = "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )
        title = f"Enhancement Test {random.randint(1000, 9999)}"

        prospect = Prospect(id=prospect_id, title=title, loaded_at=datetime.now(UTC))

        db_session.add(prospect)
        db_session.commit()

        # Start enhancement with random status and user
        statuses = ["in_progress", "queued", "processing"]
        status = random.choice(statuses)
        user_id = random.randint(1, 100)

        before_update = datetime.now(UTC)
        prospect.enhancement_status = status
        prospect.enhancement_started_at = datetime.now(UTC)
        prospect.enhancement_user_id = user_id
        after_update = datetime.now(UTC)

        db_session.commit()

        # Verify tracking
        tracked_prospect = db_session.get(Prospect, prospect_id)
        assert tracked_prospect.enhancement_status == status
        assert tracked_prospect.enhancement_started_at is not None
        assert before_update <= tracked_prospect.enhancement_started_at <= after_update
        assert tracked_prospect.enhancement_user_id == user_id


class TestDataSourceModel:
    """Test DataSource model functionality."""

    def test_data_source_creation(self, db_session):
        """Test basic data source creation with dynamic data."""
        import random
        import string

        agencies = [
            "Department of Defense",
            "Department of Energy",
            "Health and Human Services",
            "Social Security Administration",
        ]
        name = random.choice(agencies)
        domains = ["gov", "mil", "us"]
        subdomain = "".join(
            random.choices(string.ascii_lowercase, k=random.randint(3, 8))
        )
        url = f"https://{subdomain}.{random.choice(domains)}"

        data_source = DataSource(name=name, url=url, last_scraped=datetime.now(UTC))

        db_session.add(data_source)
        db_session.commit()

        # Verify creation
        saved_source = db_session.execute(
            select(DataSource).where(DataSource.name == name)
        ).scalar_one()
        assert saved_source.url == url

    def test_data_source_prospect_relationship(self, db_session):
        """Test relationship between DataSource and Prospects with dynamic data."""
        import random
        import string

        # Create data source with random data
        name = f"Agency {random.randint(1000, 9999)}"
        subdomain = "".join(
            random.choices(string.ascii_lowercase, k=random.randint(3, 8))
        )
        url = f"https://{subdomain}.gov"

        data_source = DataSource(name=name, url=url, last_scraped=datetime.now(UTC))
        db_session.add(data_source)
        db_session.flush()

        # Create random number of prospects linked to data source
        num_prospects = random.randint(2, 7)
        prospect_ids = []
        prospects = []

        for i in range(num_prospects):
            prospect_id = "".join(
                random.choices(string.ascii_letters + string.digits, k=10)
            )
            prospect_ids.append(prospect_id)
            prospect = Prospect(
                id=prospect_id,
                title=f"Contract {random.randint(1000, 9999)}",
                source_id=data_source.id,
                loaded_at=datetime.now(UTC),
            )
            prospects.append(prospect)
            db_session.add(prospect)

        db_session.commit()

        # Test relationship
        saved_source = db_session.get(DataSource, data_source.id)
        assert len(saved_source.prospects) == num_prospects

        # Test reverse relationship with random prospect
        test_prospect_id = random.choice(prospect_ids)
        prospect = db_session.get(Prospect, test_prospect_id)
        assert prospect.data_source.name == name


class TestLLMOutputModel:
    """Test LLMOutput model for logging LLM interactions."""

    def test_llm_output_creation(self, db_session):
        """Test LLM output logging with dynamic data."""
        import json
        import random
        import string

        # Create prospect first with random data
        prospect_id = "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )
        title = f"Prospect {random.randint(1000, 9999)}"

        prospect = Prospect(id=prospect_id, title=title, loaded_at=datetime.now(UTC))
        db_session.add(prospect)
        db_session.flush()

        # Generate random LLM output data
        enhancement_types = ["values", "titles", "naics", "contacts", "set_asides"]
        enhancement_type = random.choice(enhancement_types)

        # Generate appropriate prompt and response based on type
        if enhancement_type == "values":
            value_min = random.randint(10000, 100000)
            value_max = value_min + random.randint(50000, 500000)
            prompt = f"Parse the contract value from: ${value_min:,}-${value_max:,}"
            response = json.dumps({"min_value": value_min, "max_value": value_max})
        elif enhancement_type == "titles":
            prompt = f"Enhance this title: {title}"
            response = json.dumps({"enhanced_title": f"Enhanced {title}"})
        elif enhancement_type == "naics":
            naics = str(random.randint(100000, 999999))
            prompt = f"Identify NAICS code for: {title}"
            response = json.dumps(
                {"naics_code": naics, "description": f"Service {naics}"}
            )
        else:
            prompt = f"Extract {enhancement_type} from: {title}"
            response = json.dumps({"result": f"Extracted {enhancement_type}"})

        # Create LLM output
        llm_output = LLMOutput(
            prospect_id=prospect.id,
            enhancement_type=enhancement_type,
            prompt=prompt,
            response=response,
        )

        db_session.add(llm_output)
        db_session.commit()

        # Verify logging
        saved_output = db_session.execute(
            select(LLMOutput).where(LLMOutput.prospect_id == prospect.id)
        ).scalar_one()
        assert saved_output.enhancement_type == enhancement_type
        assert saved_output.prompt == prompt
        assert saved_output.response == response
        # Verify response is valid JSON
        parsed_response = json.loads(saved_output.response)
        assert isinstance(parsed_response, dict)


class TestInferredProspectDataModel:
    """Test InferredProspectData model."""

    def test_inferred_data_creation(self, db_session):
        """Test creation of inferred prospect data with dynamic values."""
        import random
        import string

        # Create prospect first with random data
        prospect_id = "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )
        title = f"Prospect {random.randint(1000, 9999)}"

        prospect = Prospect(id=prospect_id, title=title, loaded_at=datetime.now(UTC))
        db_session.add(prospect)
        db_session.flush()

        # Generate random inferred data
        naics = str(random.randint(100000, 999999))
        naics_descriptions = [
            "Computer Programming Services",
            "Engineering Services",
            "Management Consulting",
            "Scientific Research",
            "Technical Services",
        ]
        naics_desc = f"{random.choice(naics_descriptions)} - Code {naics}"
        value_min = float(random.randint(10000, 100000))
        value_max = value_min + float(random.randint(50000, 500000))

        # Create inferred data
        inferred_data = InferredProspectData(
            prospect_id=prospect.id,
            inferred_naics=naics,
            inferred_naics_description=naics_desc,
            inferred_estimated_value_min=value_min,
            inferred_estimated_value_max=value_max,
        )

        db_session.add(inferred_data)
        db_session.commit()

        # Verify creation
        saved_data = db_session.execute(
            select(InferredProspectData).where(
                InferredProspectData.prospect_id == prospect.id
            )
        ).scalar_one()
        assert saved_data.inferred_naics == naics
        assert saved_data.inferred_estimated_value_min == value_min
        assert saved_data.inferred_estimated_value_max == value_max


class TestUserModel:
    """Test User model functionality."""

    def test_user_creation(self, db_session):
        """Test user creation with required fields and dynamic data."""
        import random
        import string

        # Generate random user data
        username = "".join(
            random.choices(string.ascii_lowercase, k=random.randint(5, 10))
        )
        domain = random.choice(["example", "test", "demo", "sample"])
        email = f"{username}@{domain}.com"
        first_names = ["John", "Jane", "Bob", "Alice", "Charlie", "Diana"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Davis"]
        first_name = f"{random.choice(first_names)} {random.choice(last_names)}"
        roles = ["user", "admin", "viewer", "editor"]
        role = random.choice(roles)

        user = User(email=email, first_name=first_name, role=role)

        db_session.add(user)
        db_session.commit()

        saved_user = db_session.execute(
            select(User).where(User.email == email)
        ).scalar_one()
        assert saved_user.first_name == first_name
        assert saved_user.role == role

    def test_user_unique_constraints(self, db_session):
        """Test user unique constraints with dynamic data."""
        import random
        import string

        # Generate random email that will be duplicated
        username = "".join(
            random.choices(string.ascii_lowercase, k=random.randint(5, 10))
        )
        duplicate_email = f"{username}@test.com"

        # Create first user
        first_name_1 = f"User {random.randint(1000, 9999)}"
        role_1 = random.choice(["user", "admin", "viewer"])

        user1 = User(email=duplicate_email, first_name=first_name_1, role=role_1)

        # Create second user with same email
        first_name_2 = f"User {random.randint(1000, 9999)}"
        role_2 = random.choice(["user", "admin", "viewer"])

        user2 = User(
            email=duplicate_email,  # Duplicate email
            first_name=first_name_2,
            role=role_2,
        )

        db_session.add(user1)
        db_session.commit()

        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestDecisionModel:
    """Test GoNoGoDecision model for go/no-go decisions."""

    def test_decision_creation(self, db_session):
        """Test decision creation with dynamic data."""
        import random
        import string

        # Create user and prospect first with random data
        username = "".join(
            random.choices(string.ascii_lowercase, k=random.randint(5, 10))
        )
        email = f"{username}@example.com"
        first_name = f"{random.choice(['John', 'Jane', 'Bob', 'Alice'])} {random.choice(['Smith', 'Johnson'])}"
        role = random.choice(["user", "admin", "analyst"])

        user = User(email=email, first_name=first_name, role=role)
        db_session.add(user)
        db_session.flush()

        prospect_id = "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )
        title = f"Opportunity {random.randint(1000, 9999)}"

        prospect = Prospect(id=prospect_id, title=title, loaded_at=datetime.now(UTC))
        db_session.add(prospect)
        db_session.flush()

        # Create decision with random data
        decision_type = random.choice(["go", "no-go"])
        reasons = [
            "Strong alignment with our capabilities",
            "Good opportunity for growth",
            "Matches our strategic goals",
            "Limited competition expected",
            "Outside our core competencies",
            "Resource constraints",
            "Timeline conflicts",
        ]
        reason = random.choice(reasons)

        decision = GoNoGoDecision(
            prospect_id=prospect.id,
            user_id=user.id,
            decision=decision_type,
            reason=reason,
        )

        db_session.add(decision)
        db_session.commit()

        # Verify decision
        saved_decision = db_session.execute(
            select(GoNoGoDecision).where(GoNoGoDecision.prospect_id == prospect.id)
        ).scalar_one()
        assert saved_decision.decision == decision_type
        assert saved_decision.reason == reason
        assert saved_decision.user_id == user.id


class TestAIEnrichmentLogModel:
    """Test AIEnrichmentLog model."""

    def test_enrichment_log_creation(self, db_session):
        """Test enrichment log creation with dynamic data."""
        import random

        # Generate random enrichment log data
        enhancement_types = [
            "all",
            "values",
            "titles",
            "naics",
            "contacts",
            "set_asides",
        ]
        enhancement_type = random.choice(enhancement_types)

        statuses = ["completed", "failed", "partial", "in_progress"]
        status = random.choice(statuses)

        processed_count = random.randint(1, 500)
        duration = round(random.uniform(0.5, 120.0), 2)

        # Generate appropriate message based on status
        if status == "completed":
            message = f"Successfully processed {processed_count} prospects"
            error = None
        elif status == "failed":
            message = f"Failed after processing {processed_count} prospects"
            error = random.choice(
                ["Connection timeout", "API rate limit", "Invalid response"]
            )
        else:
            message = f"Processed {processed_count} prospects with status: {status}"
            error = None

        # Create enrichment log
        enrichment_log = AIEnrichmentLog(
            enhancement_type=enhancement_type,
            status=status,
            processed_count=processed_count,
            duration=duration,
            message=message,
            error=error,
        )

        db_session.add(enrichment_log)
        db_session.commit()

        # Verify log
        saved_log = db_session.execute(
            select(AIEnrichmentLog).order_by(AIEnrichmentLog.id.desc())
        ).scalar_one()
        assert saved_log.enhancement_type == enhancement_type
        assert saved_log.status == status
        assert saved_log.processed_count == processed_count
        assert saved_log.duration == duration
        assert saved_log.message == message
        assert saved_log.error == error


class TestModelRelationships:
    """Test complex model relationships and queries."""

    def test_prospect_full_relationships(self, db_session):
        """Test prospect with all related models using dynamic data."""
        import json
        import random
        import string

        # Create data source with random data
        agency_name = f"Agency {random.randint(1000, 9999)}"
        subdomain = "".join(
            random.choices(string.ascii_lowercase, k=random.randint(3, 8))
        )
        url = f"https://{subdomain}.gov"

        data_source = DataSource(
            name=agency_name, url=url, last_scraped=datetime.now(UTC)
        )
        db_session.add(data_source)
        db_session.flush()

        # Create user with random data
        username = "".join(
            random.choices(string.ascii_lowercase, k=random.randint(5, 10))
        )
        email = f"{username}@example.com"
        first_name = (
            f"{random.choice(['John', 'Jane'])} {random.choice(['Doe', 'Smith'])}"
        )
        role = random.choice(["admin", "user", "analyst"])

        user = User(email=email, first_name=first_name, role=role)
        db_session.add(user)
        db_session.flush()

        # Create prospect with random data
        prospect_id = "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )
        title = f"Contract {random.randint(1000, 9999)}"

        prospect = Prospect(
            id=prospect_id,
            title=title,
            source_id=data_source.id,
            loaded_at=datetime.now(UTC),
        )
        db_session.add(prospect)
        db_session.flush()

        # Create related records with random data
        enhancement_type = random.choice(["titles", "values", "naics"])
        prompt = f"Process {enhancement_type} for: {title}"
        response_data = {
            "result": f"Processed {enhancement_type}",
            "value": random.randint(1, 100),
        }

        llm_output = LLMOutput(
            prospect_id=prospect.id,
            enhancement_type=enhancement_type,
            prompt=prompt,
            response=json.dumps(response_data),
        )

        decision_type = random.choice(["go", "no-go"])
        reason = f"Reason: {random.choice(['Good fit', 'Strategic alignment', 'Resource available'])}"

        decision = GoNoGoDecision(
            prospect_id=prospect.id,
            user_id=user.id,
            decision=decision_type,
            reason=reason,
        )

        status = random.choice(["completed", "in_progress"])
        processed = random.randint(1, 10)
        duration = round(random.uniform(0.5, 10.0), 2)

        enrichment_log = AIEnrichmentLog(
            enhancement_type="all",
            status=status,
            processed_count=processed,
            duration=duration,
            message=f"Test run: processed {processed} items",
        )

        db_session.add_all([llm_output, decision, enrichment_log])
        db_session.commit()

        # Test complex query joining related tables
        result = db_session.execute(
            select(Prospect, DataSource, GoNoGoDecision)
            .join(DataSource, Prospect.source_id == DataSource.id)
            .join(GoNoGoDecision, Prospect.id == GoNoGoDecision.prospect_id)
            .where(Prospect.id == prospect_id)
        ).first()

        assert result is not None
        saved_prospect, saved_source, saved_decision = result
        assert saved_prospect.title == title
        assert saved_source.name == agency_name
        assert saved_decision.decision == decision_type
        assert saved_decision.user_id == user.id

    def test_cascade_deletes(self, db_session):
        """Test that cascade deletes work properly with dynamic data."""
        import random
        import string

        # Create data source with random data
        agency_name = f"Cascade Agency {random.randint(1000, 9999)}"
        subdomain = "".join(
            random.choices(string.ascii_lowercase, k=random.randint(3, 8))
        )

        data_source = DataSource(
            name=agency_name,
            url=f"https://{subdomain}.gov",
            last_scraped=datetime.now(UTC),
        )
        db_session.add(data_source)
        db_session.flush()

        # Create prospect with random ID
        prospect_id = "".join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )
        title = f"Cascade Test {random.randint(1000, 9999)}"

        prospect = Prospect(
            id=prospect_id,
            title=title,
            source_id=data_source.id,
            loaded_at=datetime.now(UTC),
        )
        db_session.add(prospect)
        db_session.flush()

        # Add related records with random data
        enhancement_type = random.choice(["values", "titles", "naics"])
        prompt = f"Test prompt {random.randint(1, 100)}"
        response = f"Test response {random.randint(1, 100)}"

        llm_output = LLMOutput(
            prospect_id=prospect.id,
            enhancement_type=enhancement_type,
            prompt=prompt,
            response=response,
        )
        db_session.add(llm_output)
        db_session.commit()

        # Verify records exist
        assert db_session.get(Prospect, prospect_id) is not None
        assert (
            db_session.execute(
                select(LLMOutput).where(LLMOutput.prospect_id == prospect_id)
            ).scalar_one()
            is not None
        )

        # Delete prospect should cascade to related records if configured
        db_session.delete(prospect)
        db_session.commit()

        # Verify prospect is deleted
        assert db_session.get(Prospect, prospect_id) is None
