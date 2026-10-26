import math

import numpy as np
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError

from app.database import db
from app.database.models import Prospect  # Changed back to Prospect
from app.exceptions import ValidationError
from app.utils.logger import logger


def paginate_sqlalchemy_query(query, page: int, per_page: int):
    """Paginates a SQLAlchemy query.

    Args:
        query: The SQLAlchemy query object.
        page (int): The current page number (1-indexed).
        per_page (int): The number of items per page.

    Returns:
        dict: A dictionary containing the paginated items and pagination details.

    Raises:
        ValidationError: If page or per_page have invalid values.
    """
    if not isinstance(page, int) or page < 1:
        raise ValidationError(
            "Page number must be a positive integer greater than or equal to 1."
        )
    if not isinstance(per_page, int) or per_page < 1:
        raise ValidationError(
            "Per_page must be a positive integer greater than or equal to 1."
        )
    if per_page > 100:  # Example max limit
        raise ValidationError("Per_page cannot exceed 100.")

    try:
        total_items = query.count()
    except SQLAlchemyError as e:
        logger.exception(f"Database error counting items for pagination: {e}")
        # Depending on desired behavior, could re-raise, or return an error state
        raise  # Re-raise to be handled by the caller or a global error handler

    if total_items == 0:
        total_pages = 0
        items = []
    else:
        total_pages = math.ceil(total_items / per_page)
        if (
            page > total_pages and total_items > 0
        ):  # If page is out of bounds but there are items
            raise ValidationError(
                f"Page number {page} is out of bounds. Total pages: {total_pages}."
            )

        offset = (page - 1) * per_page
        try:
            items_query = query.offset(offset).limit(per_page)
            items = items_query.all()
        except SQLAlchemyError as e:
            logger.exception(f"Database error fetching paginated items: {e}")
            # Depending on desired behavior, could re-raise, or return an error state
            raise  # Re-raise

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
        and total_items > 0,  # Ensure has_prev is false if no items
    }


def _try_enhanced_matching(df_in, preserve_ai_data, enable_smart_matching):
    """Try to use enhanced matching if enabled, return stats or None if fallback needed."""
    if not enable_smart_matching:
        return None

    from app.utils.duplicate_prevention import enhanced_bulk_upsert_prospects

    try:
        # Get the first row to determine source_id
        first_row = df_in.iloc[0]
        source_id = first_row.get("source_id")
        if source_id:
            stats = enhanced_bulk_upsert_prospects(
                df_in, db.session, source_id, preserve_ai_data, enable_smart_matching
            )
            logger.info(f"Enhanced upsert stats: {stats}")
            return stats
        logger.warning("No source_id found, falling back to standard upsert")
    except Exception as e:
        logger.error(f"Enhanced matching failed, falling back to standard upsert: {e}")

    return None


def _preprocess_dataframe(df_in):
    """Preprocess DataFrame: convert dates, handle nulls, remove loaded_at column."""
    # Work on a copy to avoid SettingWithCopyWarning
    df = df_in.copy()

    # Convert Timestamp columns to Python date objects for SQLite compatibility
    date_columns = ["release_date", "award_date"]
    for col in date_columns:
        if col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].apply(lambda x: x.date() if pd.notna(x) else None)
                logger.debug(f"Converted column '{col}' to Python date objects.")
            else:
                logger.debug(
                    f"Column '{col}' is not datetime type ({df[col].dtype}). Attempting conversion."
                )
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
                    logger.debug(
                        f"Successfully converted column '{col}' to date objects."
                    )
                except Exception as e:
                    logger.error(f"Failed to convert column '{col}' to date: {e}")
                    df[col] = None

    # Handle NaN/null values
    try:
        with pd.option_context("future.no_silent_downcasting", True):
            df = df.fillna(value=np.nan).replace([np.nan], [None])
        df = df.infer_objects(copy=False)
        logger.debug(
            "DataFrame NaN/null values replaced with None using fillna/replace."
        )
    except ImportError:
        logger.error(
            "Numpy not found. Cannot perform robust NaN replacement. Falling back to df.where()."
        )
        df = df.where(pd.notna(df), None)

    if "loaded_at" in df.columns:
        df = df.drop(columns=["loaded_at"])

    return df


def _remove_batch_duplicates(data_to_insert):
    """Remove duplicate records within the same batch based on ID."""
    seen_ids = set()
    unique_data_to_insert = []
    duplicates_count = 0

    for record in data_to_insert:
        record_id = record.get("id")
        if record_id and record_id not in seen_ids:
            seen_ids.add(record_id)
            unique_data_to_insert.append(record)
        elif record_id:
            duplicates_count += 1

    if duplicates_count > 0:
        logger.warning(
            f"Removed {duplicates_count} duplicate records within the same batch"
        )

    return unique_data_to_insert


def _process_ai_safe_upserts(session, data_to_insert, ids_to_upsert):
    """Process upserts with AI field preservation."""
    # Get existing AI-processed records
    ai_processed_records = (
        session.query(Prospect)
        .filter(
            Prospect.id.in_(ids_to_upsert), Prospect.ollama_processed_at.isnot(None)
        )
        .all()
    )

    ai_processed_ids = {record.id for record in ai_processed_records}
    logger.info(f"Found {len(ai_processed_ids)} AI-processed records to preserve")

    # AI-enhanced fields to preserve during updates
    ai_fields = [
        "naics",
        "naics_description",
        "naics_source",
        "estimated_value_min",
        "estimated_value_max",
        "estimated_value_single",
        "primary_contact_email",
        "primary_contact_name",
        "ollama_processed_at",
        "ollama_model_version",
    ]

    ai_safe_updates = 0
    regular_inserts = 0

    # Process records with AI preservation
    for record in data_to_insert:
        record_id = record.get("id")
        if record_id in ai_processed_ids:
            # Update existing AI-processed record, preserving AI fields
            existing_record = session.query(Prospect).filter_by(id=record_id).first()
            if existing_record:
                # Update only source fields, preserve AI fields
                for key, value in record.items():
                    if key not in ai_fields and hasattr(existing_record, key):
                        setattr(existing_record, key, value)
                ai_safe_updates += 1
                logger.debug(f"AI-safe update for record {record_id}")
        else:
            # Record either doesn't exist or isn't AI-processed
            # Delete and insert (regular upsert)
            session.query(Prospect).filter_by(id=record_id).delete()
            new_record = Prospect(**record)
            session.add(new_record)
            regular_inserts += 1

    logger.info(
        f"AI-safe processing: {ai_safe_updates} preserved, {regular_inserts} regular upserts"
    )
    return ai_safe_updates, regular_inserts


def _process_standard_upserts(session, data_to_insert, ids_to_upsert):
    """Process standard upserts: delete existing records and insert new ones."""
    regular_inserts = 0

    # Delete existing records in batches
    batch_size = 500  # SQLite has a limit on number of parameters
    for i in range(0, len(ids_to_upsert), batch_size):
        batch_ids = ids_to_upsert[i : i + batch_size]
        delete_count = (
            session.query(Prospect)
            .filter(Prospect.id.in_(batch_ids))
            .delete(synchronize_session=False)
        )
        logger.info(
            f"Deleted {delete_count} existing records from batch {i // batch_size + 1}"
        )

    # Insert all records in batches
    batch_size = 1000
    for i in range(0, len(data_to_insert), batch_size):
        batch_data = data_to_insert[i : i + batch_size]
        session.bulk_insert_mappings(Prospect, batch_data)
        regular_inserts += len(batch_data)
        logger.info(f"Inserted batch {i // batch_size + 1}: {len(batch_data)} records")

    logger.info(f"Standard upsert: {regular_inserts} records processed")
    return 0, regular_inserts  # 0 ai_safe_updates, regular_inserts


def bulk_upsert_prospects(
    df_in: pd.DataFrame,
    preserve_ai_data: bool = True,
    enable_smart_matching: bool = False,
):
    """Performs a bulk UPSERT (INSERT ON CONFLICT DO UPDATE) of prospect data
    from a Pandas DataFrame into the prospects table.

    Args:
        df_in (pd.DataFrame): DataFrame containing prospect data matching the
                           Prospect model schema.
        preserve_ai_data (bool): If True, preserves AI-enhanced fields for
                               existing records that have been LLM-processed.
        enable_smart_matching (bool): If True, uses advanced matching strategies
                                    to prevent duplicates when titles/descriptions change.
    """
    if df_in.empty:
        logger.info("DataFrame is empty, skipping database insertion.")
        return None

    # Try enhanced matching first
    enhanced_result = _try_enhanced_matching(
        df_in, preserve_ai_data, enable_smart_matching
    )
    if enhanced_result is not None:
        return enhanced_result

    # Standard upsert logic
    df = _preprocess_dataframe(df_in)
    data_to_insert = df.to_dict(orient="records")

    if not data_to_insert:
        logger.warning("Converted data to insert is empty.")
        return None

    # Remove duplicates within the batch
    data_to_insert = _remove_batch_duplicates(data_to_insert)

    session = db.session

    try:
        # Extract all IDs from the data to insert
        ids_to_upsert = [record["id"] for record in data_to_insert if "id" in record]

        if ids_to_upsert and preserve_ai_data:
            ai_safe_updates, regular_inserts = _process_ai_safe_upserts(
                session, data_to_insert, ids_to_upsert
            )
        elif ids_to_upsert:
            ai_safe_updates, regular_inserts = _process_standard_upserts(
                session, data_to_insert, ids_to_upsert
            )
        else:
            ai_safe_updates, regular_inserts = 0, 0

        # Commit all changes
        session.commit()
        total_processed = ai_safe_updates + regular_inserts
        if total_processed > 0:
            logger.info(
                f"Successfully processed {total_processed} records into prospects table."
            )
            if preserve_ai_data and ai_safe_updates > 0:
                logger.info(
                    f"AI-enhanced data preserved for {ai_safe_updates} records."
                )
        else:
            logger.warning("No records were processed.")

    except SQLAlchemyError as e:
        logger.exception(f"Database error during bulk upsert: {e}")
        session.rollback()
    except Exception as e:
        logger.exception(f"An unexpected error occurred during bulk upsert: {e}")
        session.rollback()


def get_prospects_for_llm_enhancement(enhancement_type: str = "all", limit: int = None):
    """Get prospects that need LLM enhancement.

    Args:
        enhancement_type: Type of enhancement needed ('values', 'contacts', 'naics', 'all')
        limit: Maximum number of prospects to return

    Returns:
        List of Prospect objects needing enhancement
    """
    query = Prospect.query

    if enhancement_type == "values":
        # Prospects with value text but no parsed values
        query = query.filter(
            Prospect.estimated_value_text.isnot(None),
            Prospect.estimated_value_single.is_(None),
        )
    elif enhancement_type == "contacts":
        # Prospects with potential contact info in extra but no primary contact
        query = query.filter(
            Prospect.primary_contact_email.is_(None), Prospect.extra.isnot(None)
        )
    elif enhancement_type == "naics":
        # Prospects without NAICS codes
        query = query.filter(Prospect.naics.is_(None))
    elif enhancement_type == "all":
        # All prospects not yet processed by LLM
        query = query.filter(Prospect.ollama_processed_at.is_(None))
    else:
        raise ValidationError(f"Invalid enhancement type: {enhancement_type}")

    if limit:
        query = query.limit(limit)

    return query.all()


def update_prospect_llm_fields(prospect_id: str, llm_data: dict):
    """Update prospect with LLM-enhanced fields.

    Args:
        prospect_id: The prospect ID to update
        llm_data: Dictionary containing LLM-enhanced fields

    Returns:
        Updated Prospect object or None if not found
    """
    prospect = Prospect.query.filter_by(id=prospect_id).first()

    if not prospect:
        return None

    # Update LLM-enhanced fields
    updateable_fields = [
        "naics",
        "naics_description",
        "naics_source",
        "estimated_value_min",
        "estimated_value_max",
        "estimated_value_single",
        "primary_contact_email",
        "primary_contact_name",
        "ollama_processed_at",
        "ollama_model_version",
    ]

    for field in updateable_fields:
        if field in llm_data:
            setattr(prospect, field, llm_data[field])

    # Update extra field if provided
    if "extra_updates" in llm_data and prospect.extra:
        prospect.extra.update(llm_data["extra_updates"])
        # Flag the JSON field as modified for SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(prospect, "extra")

    try:
        db.session.commit()
        logger.info(f"Updated prospect {prospect_id} with LLM enhancements")
        return prospect
    except SQLAlchemyError as e:
        logger.error(f"Error updating prospect {prospect_id}: {e}")
        db.session.rollback()
        return None


def get_prospect_statistics():
    """Get statistics about prospects and their enhancement status.

    Returns:
        Dictionary with various statistics
    """
    try:
        stats = {
            "total_prospects": Prospect.query.count(),
            "with_naics": Prospect.query.filter(Prospect.naics.isnot(None)).count(),
            "with_naics_original": Prospect.query.filter(
                Prospect.naics_source == "original"
            ).count(),
            "with_naics_inferred": Prospect.query.filter(
                Prospect.naics_source == "llm_inferred"
            ).count(),
            "with_parsed_values": Prospect.query.filter(
                Prospect.estimated_value_single.isnot(None)
            ).count(),
            "with_contact_info": Prospect.query.filter(
                Prospect.primary_contact_email.isnot(None)
            ).count(),
            "llm_processed": Prospect.query.filter(
                Prospect.ollama_processed_at.isnot(None)
            ).count(),
            "pending_llm": Prospect.query.filter(
                Prospect.ollama_processed_at.is_(None)
            ).count(),
        }

        # Calculate percentages
        if stats["total_prospects"] > 0:
            stats["naics_coverage_pct"] = round(
                100 * stats["with_naics"] / stats["total_prospects"], 2
            )
            stats["value_parsing_pct"] = round(
                100 * stats["with_parsed_values"] / stats["total_prospects"], 2
            )
            stats["contact_extraction_pct"] = round(
                100 * stats["with_contact_info"] / stats["total_prospects"], 2
            )
            stats["llm_processed_pct"] = round(
                100 * stats["llm_processed"] / stats["total_prospects"], 2
            )
        else:
            stats["naics_coverage_pct"] = 0
            stats["value_parsing_pct"] = 0
            stats["contact_extraction_pct"] = 0
            stats["llm_processed_pct"] = 0

        return stats

    except SQLAlchemyError as e:
        logger.error(f"Error getting prospect statistics: {e}")
        return {}
