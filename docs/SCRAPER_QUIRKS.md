# Agency Scraper Quirks and Implementation Notes

This document details the specific quirks, workarounds, and implementation decisions for each agency scraper. Understanding these details is critical for maintaining the scrapers and avoiding breaking changes.

## Department of Health and Human Services (HHS)

### 404 Status Code Issue
**Problem**: The HHS forecast page returns a 404 HTTP status code even when the page loads successfully with all required data.

**Root Cause**: Server misconfiguration on the HHS side - the page is actually available but returns wrong status.

**Solution**: Special handling in `navigate_to_url()` method:
- Check if status is 404 AND source is HHS
- Wait 1 second for client-side rendering
- Check if page content exceeds 1000 characters
- If yes, continue processing despite 404 status

**Critical Numbers**:
- Error pages: < 500 characters
- Valid pages: > 5000 characters  
- Threshold used: 1000 characters (safe margin)

**DO NOT REMOVE THIS HANDLING** - The scraper will fail without it.

## Department of Treasury

### Browser State Persistence
**Problem**: Treasury website uses complex authentication and session management that causes issues with repeated scraping attempts.

**Root Cause**: The site maintains authentication state in cookies, localStorage, and sessionStorage that expire or become invalid between runs.

**Solution**: Persist browser state between scraper runs:
- Save browser state to temporary directory after each run
- Load saved state when initializing new browser context
- State includes cookies, localStorage, sessionStorage

**Implementation Details**:
- State file: `/tmp/treasury_browser_profile/treasury_state.json`
- Non-fatal if state save/load fails
- Improves reliability but not required

### Extended Timeouts
Treasury requires significantly longer timeouts:
- Navigation: 180 seconds (3 minutes)
- Interaction: 60 seconds (1 minute)  
- Download: 300 seconds (5 minutes)

### XPath Selectors
Treasury uses Lightning Web Components, requiring XPath selectors:
```xpath
//lightning-button/button[contains(text(), 'Download Opportunity Data')]
```

## Acquisition Gateway

### Browser Arguments
Requires special browser arguments to prevent crashes:
```python
--disable-features=VizDisplayCompositor
--disable-backgrounding-occluded-windows
--disable-renderer-backgrounding
```

### Debug Mode
Runs in non-headless mode (`debug_mode=True`) for monitoring due to occasional interaction issues.

### CSV Parsing
Special CSV reading options due to malformed data:
- `on_bad_lines='skip'` - Skip malformed lines
- `quoting=1` (QUOTE_ALL) - Handle embedded quotes
- `engine='python'` - More robust parsing

## Department of Homeland Security (DHS)

### Wait Requirements
DHS requires a 10-second wait before download (`explicit_wait_ms_before_download=10000`) to ensure data is fully loaded.

### Fiscal Quarter Parsing
Complex fiscal quarter format requiring special parsing:
- Input: "Q3 2024"
- Parsed to: award_date and award_fiscal_year

## Department of Commerce (DOC)

### Link Text Navigation
DOC doesn't use standard selectors. Instead, finds links by text:
```python
download_link_text = "DOC Weekly Forecast Report"
```

### Date Derivation
Release dates are derived from fiscal year/quarter combinations since they're not provided directly.

### Excel Header Location
Excel files have headers at row 4 (0-indexed):
```python
excel_read_options = {"header": 3}
```

## Department of Justice (DOJ)

### Complex Award Date Logic
DOJ has two-stage award date parsing:
1. Try direct datetime parsing
2. Fall back to fiscal quarter parsing if that fails

### Excel Structure
Headers located at row 12:
```python
excel_read_options = {"header": 11}
```

### Country Defaulting
Place country defaults to "USA" when not provided.

## Department of State (DOS)

### Direct Download
DOS provides a direct download URL, no navigation needed:
```python
direct_download_url=[configured URL]
```

### Priority-Based Date Parsing
Complex date resolution with multiple fallbacks:
1. Check award_fiscal_year_raw
2. Parse award_date_raw
3. Fall back to award_qtr_raw
4. Use fiscal quarter parsing as last resort

### Value Range Processing
Handles complex value ranges:
- "$100K-$500K" → min: 100000, max: 500000

## Department of Transportation (DOT)

### New Page Downloads
DOT opens downloads in new pages/tabs requiring special handling:
- Wait for new page to open
- Switch context to new page
- Wait for download to start
- Return to original context

### Retry Configuration
Complex retry logic for handling transient failures:
```python
retry_attempts = [
    {"selector": "button[specific-id]", "wait_ms": 5000},
    {"selector": "a.download-link", "wait_ms": 10000},
]
```

## Social Security Administration (SSA)

### XLSM Files
SSA uses macro-enabled Excel files (.xlsm) requiring:
```python
excel_read_options = {"engine": "openpyxl"}
```

### Invalid Value Handling
Special handling for "Various" in value fields - treated as invalid/null.

## General Patterns

### Stealth Mode
Several agencies require stealth mode to avoid bot detection:
- Modifies navigator properties
- Hides webdriver presence
- Adds realistic browser fingerprint

### Error Capture
All scrapers capture on error:
- Full-page screenshots to `logs/error_screenshots/`
- HTML dumps to `logs/error_html/` (if configured)

### File Naming
Consistent naming pattern:
```
{agency_code}_{YYYYMMDD}_{HHMMSS}.{extension}
```

### Duplicate Detection
Each scraper defines fields for ID generation:
```python
fields_for_id_hash = ["native_id", "naics_code", "title", "description"]
```

## Adding New Scrapers

When adding a new agency scraper:

1. **Test the Website Manually First**:
   - Check for authentication requirements
   - Note any unusual behavior (like HHS's 404)
   - Identify download mechanisms

2. **Start with Standard Configuration**:
   - Use default timeouts initially
   - Add special handling only if needed

3. **Document Any Quirks**:
   - Add section to this file
   - Comment unusual code inline
   - Explain WHY, not just what

4. **Test Error Scenarios**:
   - Network timeouts
   - Missing elements
   - Malformed data

5. **Verify Data Quality**:
   - Check all field mappings
   - Validate date parsing
   - Ensure value extraction works