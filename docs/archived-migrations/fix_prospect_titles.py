#!/usr/bin/env python3
"""Script to fix prospect titles by copying data from extra.summary to title field"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from app import create_app
from app.database import db
from app.database.models import Prospect
from app.utils.logger import logger


def fix_prospect_titles():
    """Copy summary from extra field to title field for prospects that have null titles
    but have summary in their extra data.
    """
    app = create_app()

    with app.app_context():
        try:
            # Count prospects that need fixing
            all_prospects = Prospect.query.filter(Prospect.title.is_(None)).all()

            logger.info(f"Found {len(all_prospects)} prospects with null titles")

            fixed_count = 0
            agency_fixed_count = 0

            for prospect in all_prospects:
                updated = False

                # Fix title from extra.summary
                if prospect.extra and isinstance(prospect.extra, dict):
                    summary = prospect.extra.get("summary")
                    # Check if summary is a valid string (not nan, not None, not empty)
                    if summary and isinstance(summary, str) and summary.strip():
                        prospect.title = summary
                        updated = True
                        fixed_count += 1

                    # Also fix agency if it's null
                    agency = prospect.extra.get("agency")
                    if (
                        prospect.agency is None
                        and agency
                        and isinstance(agency, str)
                        and agency.strip()
                    ):
                        prospect.agency = agency
                        updated = True
                        agency_fixed_count += 1

                # Commit every 100 records to avoid memory issues
                if fixed_count % 100 == 0 and fixed_count > 0:
                    db.session.commit()
                    logger.info(f"Committed {fixed_count} title fixes so far...")

            # Final commit
            db.session.commit()

            logger.info(f"Successfully fixed {fixed_count} prospect titles")
            logger.info(f"Successfully fixed {agency_fixed_count} prospect agencies")

            # Verify the fix
            remaining_null = Prospect.query.filter(Prospect.title.is_(None)).count()

            logger.info(f"Remaining prospects with null titles: {remaining_null}")

        except Exception as e:
            logger.error(f"Error fixing prospect titles: {e}")
            db.session.rollback()
            raise


if __name__ == "__main__":
    fix_prospect_titles()
