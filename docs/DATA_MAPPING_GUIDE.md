# Data Mapping & Field Normalization Guide

## Overview

This guide provides detailed technical specifications for data mapping and field normalization across all agency scrapers. It serves as a reference for implementing the improvements outlined in CODEBASE_IMPROVEMENTS.md.

## Core Principles

1. **Deterministic Mapping**: Per-source hard-coded mappings are the ground truth
2. **No Magic**: Avoid global normalization that can cause false positives
3. **Fill-Only Policy**: Fallback mappings only fill empty fields, never overwrite
4. **Source Authority**: Each source defines its own mapping rules and requirements
5. **Validation First**: Drop incomplete records early rather than load bad data

## Current Architecture

### Configuration Location

- Primary: `app/core/scraper_configs.py` - Contains all source-specific mappings
- Transforms: `app/core/scrapers/*_scraper.py` - Custom per-source transformations
- Base Logic: `app/core/consolidated_scraper_base.py` - Shared normalization logic

### Key Configuration Fields

```python
# Example scraper configuration structure
{
    "raw_column_rename_map": {
        # Direct column mappings (authoritative)
        "Original Header": "database_field",
    },
    "required_fields_for_load": [
        # Fields that must be present to load record
        "id",
        "title",
        "agency",
    ],
    "place_column_configs": {
        # Location parsing configuration
        "combined_location": "Place of Performance",
        "city": "Place City",
        "state": "Place State",
    },
    "date_column_configs": [
        # Date field mapping and parsing
        {"column": "Award Date", "format": "%m/%d/%Y"}
    ],
    "fiscal_year_configs": {
        # Fiscal year and quarter parsing
        "year_column": "Fiscal Year",
        "quarter_column": "Fiscal Quarter",
    },
}
```

## Field Mapping Specifications

### Required Fields by Source

Each source should define minimum required fields based on data quality:

| Source | Required Fields | Rationale |
|--------|----------------|-----------|
| Acquisition Gateway | `id`, `title`, `agency` | Core fields always present |
| Treasury | `id`, `title`, `agency`, `place_raw` | Location critical for Treasury |
| DHS | `id`, `title`, `agency`, `fiscal_quarter` | Temporal data essential |
| DOC | `id`, `title`, `agency`, `naics_code` | NAICS always provided |
| DOJ | `id`, `title`, `agency`, `award_date` | Date tracking required |
| DOS | `id`, `title`, `agency`, `estimated_value_text` | Value data core feature |
| DOT | `id`, `title`, `agency`, `place_of_performance` | Location mandatory |
| HHS | `id`, `title`, `description` | Description substitutes for agency |
| SSA | `id`, `title`, `agency`, `primary_contact_name` | Contact info priority |

### Location Parsing Patterns

Sources provide location data in various formats that need standardization:

#### Combined Location Format

```python
# Input: "Washington, DC"
# Configuration:
place_column_configs = {
    "combined_location": "Place of Performance",
    "default_country": "USA",
}
# Output:
# place_city: "Washington"
# place_state: "DC"
# place_country: "USA"
```

#### Separate Fields Format

```python
# Input: Separate columns for city/state
# Configuration:
place_column_configs = {
    "city": "Performance City",
    "state": "Performance State",
    "default_country": "USA",
}
```

#### Priority Sources for Location Parsing

- **DOT**: Combined format "City, ST"
- **DOJ**: Combined with occasional country
- **Treasury**: "Place of Performance" field
- **SSA**: Separate city/state fields

### Contact Field Normalization

Contact information appears in multiple formats across sources:

#### First/Last Name Concatenation

```python
# DHS, DOJ pattern
if "Contact First Name" in df and "Contact Last Name" in df:
    df["primary_contact_name"] = (
        df["Contact First Name"] + " " + df["Contact Last Name"]
    )
```

#### Organization-Level Contacts

```python
# Treasury pattern
if "Contracting Office" in df and not df["primary_contact_name"]:
    df["primary_contact_name"] = df["Contracting Office"]
```

#### Email Extraction

```python
# Universal pattern
if "Contact Email" in df:
    df["primary_contact_email"] = df["Contact Email"].str.lower().str.strip()
```

### Date and Fiscal Quarter Parsing

Standardize temporal data across various formats:

#### Direct Date Parsing

```python
date_column_configs = [
    {"column": "Award Date", "format": "%m/%d/%Y"},
    {"column": "Release Date", "format": "%Y-%m-%d"},
    {"column": "Target Date", "format": "%B %Y"},  # "January 2025"
]
```

#### Fiscal Quarter Formats

```python
# Pattern 1: "Q3 2024"
# Pattern 2: "FY25 Q2"
# Pattern 3: "2024 Q3"

fiscal_year_configs = {
    "year_column": "Fiscal Year",
    "quarter_column": "Fiscal Quarter",
    "combined_column": "FY/Quarter",  # If combined
    "pattern": r"(?:FY)?(\d{2,4})\s*Q(\d)",  # Regex for combined
}
```

### Value Field Handling

Contract values require special attention due to range vs. single value formats:

```python
# Range format: "$100K - $500K"
# Single format: "$250,000"
# Text format: "Approximately $1M"

value_configs = {
    "value_column": "Estimated Value",
    "parse_ranges": True,
    "currency_symbols": ["$", "€", "£"],
    "multipliers": {"K": 1000, "M": 1000000, "B": 1000000000},
}
```

## Fallback Normalization Strategy

### Per-Source Fallback Candidates

Define conservative fallback mappings that only apply to specific sources:

```python
# Acquisition Gateway
AG_FALLBACKS = {
    "Body": "description",  # Common variant
    "NAICS": "naics_code",  # Missing underscore
    "Set Aside": "set_aside",  # Space variant
}

# Treasury
TREASURY_FALLBACKS = {
    "Place of Performance": "place_raw",
    "Contracting Agency": "agency",
    "Description of Requirement": "description",
}

# Apply only if target field is empty
for source_col, target_col in FALLBACKS.items():
    if source_col in df.columns and target_col in df.columns:
        mask = df[target_col].isna() | (df[target_col] == "")
        df.loc[mask, target_col] = df.loc[mask, source_col]
```

### Safety Rules

1. **Never overwrite non-empty values**
2. **Log all fallback applications** for audit trail
3. **Validate against known good patterns** before applying
4. **Test with fixtures** before production deployment

## Validation & Monitoring

### Field Coverage Analysis

Use the CLI tool to monitor field coverage:

```bash
# Check all fixtures
python scripts/analyze_field_coverage.py \
    --fixtures tests/fixtures/golden_files \
    --min-threshold 0.8

# Check specific source
python scripts/analyze_field_coverage.py \
    --source treasury \
    --input-dir data/raw/treas

# Generate coverage report
python scripts/analyze_field_coverage.py \
    --fixtures tests/fixtures/golden_files \
    --output-format json \
    --output-file coverage_report.json
```

### Expected Coverage Thresholds

| Field | Target Coverage | Current Coverage | Notes |
|-------|-----------------|------------------|-------|
| title | 100% | 100% | Always required |
| agency | 95% | 92% | Some sources use organization |
| description | 80% | 75% | Not all sources provide |
| naics_code | 60% | 55% | Often needs LLM inference |
| set_aside | 70% | 68% | Important for small business |
| estimated_value_text | 85% | 82% | Critical for opportunity sizing |
| place_city | 75% | 70% | Location parsing improvements needed |
| primary_contact_name | 60% | 45% | Varies significantly by source |

## Database Considerations

### SQLite (Current)

- No schema changes needed
- TEXT fields handle all value formats
- JSON strings in `extras` field for unmapped data

### PostgreSQL (Future)

```sql
-- Recommended schema optimizations
ALTER TABLE prospects 
    ALTER COLUMN estimated_value_min TYPE NUMERIC(15,2),
    ALTER COLUMN estimated_value_max TYPE NUMERIC(15,2),
    ALTER COLUMN estimated_value_single TYPE NUMERIC(15,2);

-- JSONB for better querying
ALTER TABLE prospects 
    ALTER COLUMN extras TYPE JSONB;

-- Index for JSON key searches
CREATE INDEX idx_extras_gin ON prospects USING GIN (extras);
```

## Testing Requirements

### Unit Tests for Mappings

```python
def test_treasury_mapping():
    """Verify Treasury header mappings"""
    config = TREASURY_CONFIG
    sample_data = pd.DataFrame(
        {
            "Title": ["Test Opportunity"],
            "Contracting Agency": ["Treasury"],
            "Place of Performance": ["Washington, DC"],
        }
    )

    mapped = apply_mappings(sample_data, config)

    assert "title" in mapped.columns
    assert "agency" in mapped.columns
    assert "place_raw" in mapped.columns
    assert mapped["title"].iloc[0] == "Test Opportunity"
```

### Regression Tests for Transforms

```python
def test_location_parsing():
    """Verify location parsing doesn't break existing data"""
    input_data = "Washington, DC"
    city, state = parse_location(input_data)
    
    assert city == "Washington"
    assert state == "DC"
```

## Implementation Checklist

- [ ] Add `required_fields_for_load` to all scraper configs
- [ ] Implement per-source fallback mappings
- [ ] Standardize location parsing across sources
- [ ] Unify contact field handling
- [ ] Set up regular field coverage monitoring
- [ ] Add unit tests for each source's mappings
- [ ] Document any new header variants discovered
- [ ] Create alerts for coverage drops below thresholds

## Maintenance

### Monthly Tasks

1. Run field coverage analysis
2. Review logs for fallback normalization usage
3. Update mappings for any header changes
4. Test with latest fixture files

### Quarterly Tasks

1. Review coverage thresholds
2. Evaluate fields for promotion to first-class columns
3. Audit `extras` field usage patterns
4. Update this guide with new patterns discovered
