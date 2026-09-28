#!/usr/bin/env python3
"""Check the results of set-aside enhancement to verify it's working correctly."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.database import db
from app.database.models import InferredProspectData, Prospect


def check_enhancement_results():
    """Check the results of set-aside enhancement"""
    app = create_app()
    with app.app_context():
        # Get prospects that have both original and inferred set-aside data
        prospects_with_enhancement = (
            db.session.query(Prospect)
            .join(InferredProspectData)
            .filter(
                Prospect.set_aside.isnot(None),
                InferredProspectData.inferred_set_aside.isnot(None),
            )
            .limit(20)
            .all()
        )

        print("SET-ASIDE ENHANCEMENT RESULTS")
        print("=" * 80)
        print(
            f"Found {len(prospects_with_enhancement)} prospects with enhanced set-aside data"
        )
        print()

        for i, prospect in enumerate(prospects_with_enhancement, 1):
            print(f"{i:2d}. Prospect ID: {prospect.id}")
            print(f"    Original: '{prospect.set_aside}'")
            print(f"    Enhanced: '{prospect.inferred_data.inferred_set_aside}'")

            # Show confidence if available
            if (
                prospect.inferred_data.llm_confidence_scores
                and "set_aside" in prospect.inferred_data.llm_confidence_scores
            ):
                confidence = prospect.inferred_data.llm_confidence_scores["set_aside"]
                print(f"    Confidence: {confidence:.2f}")

            print()

        # Get some statistics
        total_with_set_aside = (
            db.session.query(Prospect)
            .filter(Prospect.set_aside.isnot(None), Prospect.set_aside != "")
            .count()
        )

        total_enhanced = (
            db.session.query(Prospect)
            .join(InferredProspectData)
            .filter(InferredProspectData.inferred_set_aside.isnot(None))
            .count()
        )

        print("STATISTICS")
        print("=" * 80)
        print(f"Total prospects with set-aside data: {total_with_set_aside:,}")
        print(f"Total prospects with enhanced set-aside: {total_enhanced:,}")
        print(
            f"Enhancement coverage: {(total_enhanced / total_with_set_aside * 100):.1f}%"
        )


if __name__ == "__main__":
    check_enhancement_results()
