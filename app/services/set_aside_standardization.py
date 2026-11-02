"""Set-aside standardization service for normalizing set-aside field values.
This service provides mapping and LLM-based classification of set-aside types.
"""

from enum import Enum


class StandardSetAside(Enum):
    """Simplified standardized set-aside types for business development focus"""

    SMALL_BUSINESS = "Small Business"
    EIGHT_A = "8(a)"
    HUBZONE = "HUBZone"
    WOMEN_OWNED = "Women-Owned"
    VETERAN_OWNED = "Veteran-Owned"
    FULL_AND_OPEN = "Full and Open"
    SOLE_SOURCE = "Sole Source"
    NOT_AVAILABLE = "N/A"

    @property
    def code(self) -> str:
        """Return the enum name as code (e.g., 'SMALL_BUSINESS')"""
        return self.name

    @property
    def label(self) -> str:
        """Return the enum value as human-readable label (e.g., 'Small Business')"""
        return self.value


class SetAsideStandardizer:
    """Simplified service for LLM-based set-aside classification"""

    def __init__(self):
        """Initialize the standardizer - no complex rules needed for LLM approach"""

    def get_llm_prompt(self) -> str:
        """Get the enhanced LLM prompt for set-aside classification"""
        standard_types = [e.value for e in StandardSetAside]

        return f"""You are a federal procurement specialist. Classify the given set-aside information into one of these EXACT categories:

{chr(10).join(f"- {t}" for t in standard_types)}

CLASSIFICATION RULES:
1. "Small Business" - All small business set-asides including SDB, small business total, small disadvantaged business
2. "8(a)" - Any 8(a) program references (competitive, sole source, non-competitive)
3. "HUBZone" - HUBZone program references (any variation of spelling)
4. "Women-Owned" - WOSB, EDWOSB, women-owned small business, economically disadvantaged women-owned
5. "Veteran-Owned" - SDVOSB, VOSB, service-disabled veteran-owned, veteran-owned small business
6. "Full and Open" - Unrestricted competition, open competition, full and open competition
7. "Sole Source" - Explicit sole source procurements (not combined with set-aside types)
8. "N/A" - Unclear, missing, TBD, determined, other, unknown, or non-informative values

INPUT FORMATS:
- Single field: "Small Business Set-Aside"
- Multiple fields: "Set-aside: [value]; Small Business Program: [program]"
- Program only: "Small Business Program: [program_name]"

When multiple data sources are provided, prioritize the most specific information.

EXAMPLES:
- "Small Business Set-Aside" → Small Business
- "8(a) Competitive" → 8(a)
- "WOSB Sole Source" → Women-Owned
- "Service-Disabled Veteran Owned" → Veteran-Owned
- "HubZone" → HUBZone
- "Unrestricted" → Full and Open
- "Set-aside: Full; Small Business Program: WOSB" → Women-Owned
- "Small Business Program: 8(a)" → 8(a)
- "TBD" → N/A
- "Currently not available" → N/A

Input: "{{}}"

Respond with ONLY the exact category name (e.g., "Small Business", "8(a)", "N/A")."""
