from datetime import UTC

UTC = UTC
from datetime import date, datetime

from flask import Blueprint, jsonify
from sqlalchemy import desc, func

from app.database import db
from app.database.models import (
    DataSource,
    Prospect,
    ScraperStatus,
)  # Added ScraperStatus
from app.utils.logger import logger

main_bp = Blueprint("main", __name__)

# Set up logging using the centralized utility
logger = logger.bind(name="api.main")


@main_bp.route("/", methods=["GET"])
def api_info():
    """API information endpoint."""
    return jsonify(
        {
            "name": "JPS Prospect Aggregate API",
            "version": "1.0.0",
            "description": "API for managing government procurement prospects",
            "endpoints": {
                "/api/": "This endpoint - API information",
                "/api/health": "Health check endpoint",
                "/api/dashboard": "Dashboard summary data",
                "/api/prospects": "Prospects data with pagination",
            },
            "status": "operational",
        }
    )


@main_bp.route("/health", methods=["GET"])
def health_check():
    """API health check endpoint."""
    try:
        session = db.session
        # Simple database query to check connection
        session.query(DataSource).first()

        return jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.now(UTC).isoformat() + "Z",
                "database": "connected",
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        # No rollback needed for a read operation that failed
        return jsonify(
            {
                "status": "unhealthy",
                "timestamp": datetime.now(UTC).isoformat() + "Z",
                "database": "disconnected",  # More specific status
                "error": str(e),
            }
        ), 500


@main_bp.route("/dashboard", methods=["GET"])
def get_dashboard():
    """Get dashboard summary information."""
    session = db.session
    try:
        # Get total number of prospects
        total_prospects = session.query(func.count(Prospect.id)).scalar()

        # Get newest data source update (last_scraped from DataSource)
        latest_successful_scrape = session.query(
            func.max(DataSource.last_scraped)
        ).scalar()

        # Get top agencies by prospect count
        top_agencies = (
            session.query(
                Prospect.agency, func.count(Prospect.id).label("prospect_count")
            )
            .group_by(Prospect.agency)
            .order_by(desc("prospect_count"))
            .limit(5)
            .all()
        )

        # Get upcoming prospects (using release_date)
        today = date.today()  # Use date.today() for date comparison
        upcoming_prospects_data = (
            session.query(Prospect)
            .filter(Prospect.release_date >= today)
            .order_by(Prospect.release_date)
            .limit(5)
            .all()
        )

        # Get recent scraper activity (last 5 completed or failed)
        recent_scraper_activity = (
            session.query(
                DataSource.name,
                ScraperStatus.status,
                ScraperStatus.last_checked,
                ScraperStatus.details,
            )
            .join(ScraperStatus, DataSource.id == ScraperStatus.source_id)
            .order_by(ScraperStatus.last_checked.desc())
            .limit(5)
            .all()
        )

        return jsonify(
            {
                "status": "success",
                "data": {
                    "total_proposals": total_prospects,
                    "latest_successful_scrape": latest_successful_scrape.isoformat()
                    + "Z"
                    if latest_successful_scrape
                    else None,
                    "top_agencies": [
                        {"agency": agency, "count": count}
                        for agency, count in top_agencies
                    ],
                    "upcoming_proposals": [
                        {
                            "id": p.id,
                            "title": p.title,
                            "agency": p.agency,
                            "proposal_date": p.release_date.isoformat() + "Z"
                            if p.release_date
                            else None,
                        }
                        for p in upcoming_prospects_data
                    ],
                    "recent_scraper_activity": [
                        {
                            "data_source_name": name,
                            "status": status,
                            "last_checked": last_checked.isoformat() + "Z"
                            if last_checked
                            else None,
                            "details": details,
                        }
                        for name, status, last_checked, details in recent_scraper_activity
                    ],
                },
            }
        )
    except Exception as e:
        logger.error(f"Error in get_dashboard: {str(e)}", exc_info=True)
        # db.session.rollback() # Removed
        return jsonify(
            {"status": "error", "message": "An unexpected error occurred"}
        ), 500


def _execute_database_clear_operation(operation_name: str, clear_function):
    """Common utility for database clearing operations."""
    try:
        logger.info(f"{operation_name} operation initiated")

        # Execute the specific clearing logic
        result = clear_function()

        db.session.commit()

        logger.info(result["log_message"])

        return jsonify(
            {
                "status": "success",
                "message": result["response_message"],
                "timestamp": datetime.now(UTC).isoformat() + "Z",
            }
        )

    except Exception as e:
        logger.error(f"Error in {operation_name.lower()}: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify(
            {
                "status": "error",
                "message": f"Failed to {operation_name.lower()}: {str(e)}",
            }
        ), 500


@main_bp.route("/database/clear", methods=["POST"])
@main_bp.route("/database/clear/<clear_type>", methods=["POST"])
def clear_database(clear_type="all"):
    """Clear data from the database based on type.

    Args:
        clear_type: Type of data to clear ('all', 'ai', 'original')
    """
    if clear_type not in ["all", "ai", "original"]:
        return jsonify(
            {
                "status": "error",
                "message": f"Invalid clear type: {clear_type}. Must be 'all', 'ai', or 'original'",
            }
        ), 400

    def _clear_all_data():
        # Delete all prospects first (due to foreign key constraints)
        prospect_count = db.session.query(func.count(Prospect.id)).scalar()
        db.session.query(Prospect).delete()

        # Reset the auto-increment counters if using SQLite
        try:
            db.session.execute('DELETE FROM sqlite_sequence WHERE name="prospects"')
            db.session.execute(
                'DELETE FROM sqlite_sequence WHERE name="scraper_status"'
            )
        except Exception:
            # Not SQLite or sequence doesn't exist, ignore
            pass

        # Clear scraper status records
        from app.database.models import ScraperStatus

        status_count = db.session.query(func.count(ScraperStatus.id)).scalar()
        db.session.query(ScraperStatus).delete()

        # Reset last_scraped on data sources
        data_sources = db.session.query(DataSource).all()
        for ds in data_sources:
            ds.last_scraped = None

        return {
            "log_message": f"Database cleared successfully. Removed {prospect_count} prospects and {status_count} status records",
            "response_message": f"Database cleared successfully. Removed {prospect_count} prospects and {status_count} status records.",
        }

    def _clear_ai_data():
        # Count AI-enriched prospects
        ai_prospect_count = (
            db.session.query(func.count(Prospect.id))
            .filter(Prospect.ollama_processed_at.isnot(None))
            .scalar()
        )

        # Delete AI-enriched prospects
        db.session.query(Prospect).filter(
            Prospect.ollama_processed_at.isnot(None)
        ).delete()

        # Clear AI enrichment logs
        from app.database.models import AIEnrichmentLog, LLMOutput

        log_count = db.session.query(func.count(AIEnrichmentLog.id)).scalar()
        db.session.query(AIEnrichmentLog).delete()

        # Clear LLM outputs
        output_count = db.session.query(func.count(LLMOutput.id)).scalar()
        db.session.query(LLMOutput).delete()

        return {
            "log_message": f"AI entries cleared successfully. Removed {ai_prospect_count} AI-enriched prospects, {log_count} enrichment logs, and {output_count} LLM outputs",
            "response_message": f"AI entries cleared successfully. Removed {ai_prospect_count} AI-enriched prospects, {log_count} enrichment logs, and {output_count} LLM outputs.",
        }

    def _clear_original_data():
        # Count non-AI-enriched prospects
        original_prospect_count = (
            db.session.query(func.count(Prospect.id))
            .filter(Prospect.ollama_processed_at.is_(None))
            .scalar()
        )

        # Delete non-AI-enriched prospects
        db.session.query(Prospect).filter(
            Prospect.ollama_processed_at.is_(None)
        ).delete()

        # Note: We keep data sources and scraper status as they might be needed for future scraping

        return {
            "log_message": f"Original entries cleared successfully. Removed {original_prospect_count} non-AI-enriched prospects",
            "response_message": f"Original entries cleared successfully. Removed {original_prospect_count} non-AI-enriched prospects.",
        }

    # Map clear type to appropriate function
    clear_functions = {
        "all": _clear_all_data,
        "ai": _clear_ai_data,
        "original": _clear_original_data,
    }

    operation_names = {
        "all": "Database clear",
        "ai": "AI entries clear",
        "original": "Original entries clear",
    }

    return _execute_database_clear_operation(
        operation_names[clear_type], clear_functions[clear_type]
    )


@main_bp.route("/database/status", methods=["GET"])
def database_status():
    """Get database status and statistics."""
    try:
        # Get counts for all main tables
        prospect_count = db.session.query(func.count(Prospect.id)).scalar()
        data_source_count = db.session.query(func.count(DataSource.id)).scalar()

        # Count prospects with valid source_id vs total
        prospects_with_source = (
            db.session.query(func.count(Prospect.id))
            .filter(Prospect.source_id.isnot(None))
            .scalar()
        )
        prospects_without_source = prospect_count - prospects_with_source

        # Count AI-enriched vs original prospects
        ai_enriched_count = (
            db.session.query(func.count(Prospect.id))
            .filter(Prospect.ollama_processed_at.isnot(None))
            .scalar()
        )
        original_count = prospect_count - ai_enriched_count

        status_count = db.session.query(func.count(ScraperStatus.id)).scalar()

        # Get database size for SQLite
        db_size = None
        try:
            from flask import current_app

            db_path = current_app.config.get("SQLALCHEMY_DATABASE_URI")

            if db_path and db_path.startswith("sqlite:///"):
                # SQLite: Get file size
                import os

                db_file = db_path.replace("sqlite:///", "")
                if os.path.exists(db_file):
                    db_size = os.path.getsize(db_file)
            # Only SQLite is supported
        except Exception:
            # If any error occurs, silently continue with db_size = None
            pass

        return jsonify(
            {
                "status": "success",
                "data": {
                    "prospect_count": prospect_count,
                    "prospects_with_source": prospects_with_source,
                    "prospects_without_source": prospects_without_source,
                    "ai_enriched_count": ai_enriched_count,
                    "original_count": original_count,
                    "data_source_count": data_source_count,
                    "status_record_count": status_count,
                    "database_size_bytes": db_size,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting database status: {str(e)}", exc_info=True)
        return jsonify(
            {"status": "error", "message": f"Failed to get database status: {str(e)}"}
        ), 500


@main_bp.route("/config/ai-preservation", methods=["GET"])
def get_ai_preservation_config():
    """Get AI data preservation configuration."""
    from app.config import active_config

    return jsonify(
        {
            "status": "success",
            "data": {
                "preserve_ai_data_on_refresh": active_config.PRESERVE_AI_DATA_ON_REFRESH,
                "enable_smart_duplicate_matching": active_config.ENABLE_SMART_DUPLICATE_MATCHING,
                "description": "When enabled, AI-enhanced fields (NAICS, contact info, parsed values) are preserved during data source refreshes",
            },
        }
    )


@main_bp.route("/config/ai-preservation", methods=["POST"])
def set_ai_preservation_config():
    """Set AI data preservation configuration."""
    try:
        import os

        from flask import request

        from app.config import active_config

        data = request.get_json()
        if not data:
            return jsonify(
                {"status": "error", "message": "Request body is required"}
            ), 400

        updated_fields = []

        # Handle AI preservation setting
        if "preserve_ai_data_on_refresh" in data:
            new_value = bool(data["preserve_ai_data_on_refresh"])
            active_config.PRESERVE_AI_DATA_ON_REFRESH = new_value
            os.environ["PRESERVE_AI_DATA_ON_REFRESH"] = "true" if new_value else "false"
            updated_fields.append(
                f"AI preservation {'enabled' if new_value else 'disabled'}"
            )
            logger.info(f"AI data preservation setting updated to: {new_value}")

        # Handle smart matching setting
        if "enable_smart_duplicate_matching" in data:
            new_value = bool(data["enable_smart_duplicate_matching"])
            active_config.ENABLE_SMART_DUPLICATE_MATCHING = new_value
            os.environ["ENABLE_SMART_DUPLICATE_MATCHING"] = (
                "true" if new_value else "false"
            )
            updated_fields.append(
                f"Smart duplicate matching {'enabled' if new_value else 'disabled'}"
            )
            logger.info(f"Smart duplicate matching setting updated to: {new_value}")

        if not updated_fields:
            return jsonify(
                {
                    "status": "error",
                    "message": "At least one configuration field is required",
                }
            ), 400

        return jsonify(
            {
                "status": "success",
                "data": {
                    "preserve_ai_data_on_refresh": active_config.PRESERVE_AI_DATA_ON_REFRESH,
                    "enable_smart_duplicate_matching": active_config.ENABLE_SMART_DUPLICATE_MATCHING,
                    "message": f"Configuration updated: {', '.join(updated_fields)}",
                },
            }
        )

    except Exception as e:
        logger.error(f"Error updating AI preservation config: {str(e)}", exc_info=True)
        return jsonify(
            {"status": "error", "message": f"Failed to update configuration: {str(e)}"}
        ), 500


def _setup_progress_tracking():
    """Initialize progress tracking for duplicate detection scan."""
    import threading
    import time

    scan_id = f"scan_{int(time.time())}_{threading.get_ident()}"

    # Initialize progress in a global store
    global_progress_store = getattr(detect_duplicates, "progress_store", {})

    global_progress_store[scan_id] = {
        "status": "starting",
        "current": 0,
        "total": 0,
        "message": "Initializing scan...",
        "start_time": time.time(),
    }

    # Ensure the store is attached to the function
    detect_duplicates.progress_store = global_progress_store

    logger.info(f"Started duplicate scan with ID: {scan_id}")
    return scan_id


def _get_prospects_to_process(source_id, limit):
    """Get the list of prospects to process for duplicate detection."""
    from app.database.models import Prospect

    query = db.session.query(Prospect)
    if source_id:
        query = query.filter(Prospect.source_id == source_id)

    # If limit is very high (10000+), treat as "scan all"
    if limit >= 10000:
        prospects = query.order_by(Prospect.loaded_at.desc()).all()
    else:
        prospects = query.order_by(Prospect.loaded_at.desc()).limit(limit * 2).all()

    # Process up to the limit (or all if scanning all)
    return prospects if limit >= 10000 else prospects[:limit]


def _format_prospect_for_api(prospect):
    """Format a single prospect for API response."""
    return {
        "id": prospect.id,
        "native_id": prospect.native_id,
        "title": prospect.title[:100] + "..."
        if prospect.title and len(prospect.title) > 100
        else prospect.title,
        "description": prospect.description[:150] + "..."
        if prospect.description and len(prospect.description) > 150
        else prospect.description,
        "agency": prospect.agency,
        "naics": prospect.naics,
        "place_city": prospect.place_city,
        "place_state": prospect.place_state,
        "ai_processed": prospect.ollama_processed_at is not None,
        "loaded_at": prospect.loaded_at.isoformat() + "Z"
        if prospect.loaded_at
        else None,
    }


def _create_duplicate_group(
    prospect, high_confidence_matches, matched_prospects_cache=None
):
    """Create a duplicate group from a prospect and its matches."""
    from app.database.models import Prospect

    # Use cache if provided, otherwise fetch
    if matched_prospects_cache is None:
        # Get prospect details for the matches
        match_ids = [m.prospect_id for m in high_confidence_matches]
        matched_prospects = (
            db.session.query(Prospect).filter(Prospect.id.in_(match_ids)).all()
        )

        matched_prospects_dict = {p.id: p for p in matched_prospects}
    else:
        matched_prospects_dict = matched_prospects_cache

    duplicate_group = {"original": _format_prospect_for_api(prospect), "matches": []}

    for match in high_confidence_matches:
        matched_prospect = matched_prospects_dict.get(match.prospect_id)
        if matched_prospect:
            match_data = _format_prospect_for_api(matched_prospect)
            match_data.update(
                {
                    "confidence_score": match.confidence_score,
                    "match_type": match.match_type,
                    "matched_fields": match.matched_fields,
                }
            )
            duplicate_group["matches"].append(match_data)

    return duplicate_group


def _process_prospects_for_duplicates(prospects_to_process, scan_id, min_confidence):
    """Process prospects to find duplicates with progress tracking."""
    from app.utils.duplicate_prevention import DuplicateDetector

    detector = DuplicateDetector()
    potential_duplicates = []

    # Update progress with total count
    detect_duplicates.progress_store[scan_id].update(
        {
            "status": "processing",
            "total": len(prospects_to_process),
            "message": f"Scanning {len(prospects_to_process)} prospects for duplicates...",
        }
    )

    logger.info(f"Processing {len(prospects_to_process)} prospects for scan {scan_id}")

    # Group prospects by source_id and preload data for each source
    prospects_by_source = {}
    for prospect in prospects_to_process:
        source_id = prospect.source_id or 0
        if source_id not in prospects_by_source:
            prospects_by_source[source_id] = []
        prospects_by_source[source_id].append(prospect)

    # Pre-fetch all prospects that might be needed for matching
    # This prevents N+1 queries in the duplicate detection logic
    all_prospect_ids = set()
    all_matches_by_prospect = {}

    # Process all prospects with progress tracking
    processed_count = 0
    for source_id, source_prospects in prospects_by_source.items():
        # Preload all prospects for this source to optimize matching
        detector.preload_source_prospects(db.session, source_id)

        # Process prospects from this source
        for prospect in source_prospects:
            # Update progress every 25 records or on last record for better performance
            if (
                processed_count % 25 == 0
                or processed_count == len(prospects_to_process) - 1
            ):
                detect_duplicates.progress_store[scan_id].update(
                    {
                        "current": processed_count + 1,
                        "message": f"Processing prospect {processed_count + 1} of {len(prospects_to_process)}...",
                    }
                )
                logger.debug(
                    f"Scan {scan_id} progress: {processed_count + 1}/{len(prospects_to_process)}"
                )

            # Convert prospect to dict for matching
            prospect_data = {
                "native_id": prospect.native_id,
                "title": prospect.title,
                "description": prospect.description,
                "naics": prospect.naics,
                "agency": prospect.agency,
                "place_city": prospect.place_city,
                "place_state": prospect.place_state,
                "source_id": prospect.source_id,  # Add source_id for cache lookup
            }

            # Find potential matches
            matches = detector.find_potential_matches(
                db.session, prospect_data, prospect.source_id or 0
            )

            # Filter by confidence and exclude self-matches
            high_confidence_matches = [
                match
                for match in matches
                if match.confidence_score >= min_confidence
                and match.prospect_id != prospect.id
            ]

            if high_confidence_matches:
                all_matches_by_prospect[prospect.id] = high_confidence_matches
                # Collect all prospect IDs that will be needed
                for match in high_confidence_matches:
                    all_prospect_ids.add(match.prospect_id)

            processed_count += 1

    # Pre-fetch all needed prospects in a single query
    matched_prospects_cache = {}
    if all_prospect_ids:
        all_matched_prospects = (
            db.session.query(Prospect)
            .filter(Prospect.id.in_(list(all_prospect_ids)))
            .all()
        )
        matched_prospects_cache = {p.id: p for p in all_matched_prospects}

    # Second pass: create duplicate groups using cached data
    for prospect in prospects_to_process:
        if prospect.id in all_matches_by_prospect:
            high_confidence_matches = all_matches_by_prospect[prospect.id]
            duplicate_group = _create_duplicate_group(
                prospect, high_confidence_matches, matched_prospects_cache
            )
            potential_duplicates.append(duplicate_group)

    return potential_duplicates


@main_bp.route("/duplicates/detect", methods=["POST"])
def detect_duplicates():
    """Detect potential duplicate prospects in the database."""
    try:
        import time

        from flask import request

        # Parse request parameters
        data = request.get_json() or {}
        source_id = data.get("source_id")
        min_confidence = float(data.get("min_confidence", 0.7))
        limit = int(data.get("limit", 100))

        # Setup progress tracking
        scan_id = _setup_progress_tracking()

        # Get prospects to process
        prospects_to_process = _get_prospects_to_process(source_id, limit)

        # Process prospects for duplicates
        potential_duplicates = _process_prospects_for_duplicates(
            prospects_to_process, scan_id, min_confidence
        )

        # Mark scan as completed and store results
        processing_time = (
            time.time() - detect_duplicates.progress_store[scan_id]["start_time"]
        )
        detect_duplicates.progress_store[scan_id].update(
            {
                "status": "completed",
                "current": len(prospects_to_process),
                "message": f"Scan completed! Found {len(potential_duplicates)} duplicate groups.",
                "end_time": time.time(),
                "results": {
                    "potential_duplicates": potential_duplicates,
                    "total_found": len(potential_duplicates),
                    "scan_parameters": {
                        "source_id": source_id,
                        "min_confidence": min_confidence,
                        "limit": limit,
                    },
                    "processing_time": processing_time,
                },
            }
        )

        logger.info(
            f"Scan {scan_id} completed in {processing_time:.2f}s. Found {len(potential_duplicates)} duplicate groups."
        )

        # Return the scan results
        return jsonify(
            {
                "status": "success",
                "data": {
                    "potential_duplicates": potential_duplicates,
                    "total_found": len(potential_duplicates),
                    "scan_parameters": {
                        "source_id": source_id,
                        "min_confidence": min_confidence,
                        "limit": limit,
                    },
                    "scan_id": scan_id,
                    "processing_time": processing_time,
                },
            }
        )

    except Exception as e:
        # Mark scan as failed in progress store
        if "scan_id" in locals():
            detect_duplicates.progress_store[scan_id].update(
                {
                    "status": "error",
                    "message": f"Scan failed: {str(e)}",
                    "end_time": time.time(),
                }
            )

        logger.error(f"Error detecting duplicates: {str(e)}", exc_info=True)
        return jsonify(
            {"status": "error", "message": f"Failed to detect duplicates: {str(e)}"}
        ), 500


@main_bp.route("/duplicates/progress/<scan_id>", methods=["GET"])
def get_duplicate_scan_progress(scan_id):
    """Get progress of a duplicate detection scan."""
    try:
        import time

        if not hasattr(detect_duplicates, "progress_store"):
            return jsonify({"status": "error", "message": "No active scans found"}), 404

        progress = detect_duplicates.progress_store.get(scan_id)
        if not progress:
            return jsonify({"status": "error", "message": "Scan not found"}), 404

        # Calculate percentage
        percentage = 0
        if progress["total"] > 0:
            percentage = min(100, (progress["current"] / progress["total"]) * 100)

        # Calculate elapsed time
        elapsed_time = time.time() - progress["start_time"]

        # Estimate remaining time
        eta = None
        if progress["current"] > 0 and progress["status"] == "processing":
            rate = progress["current"] / elapsed_time
            remaining_items = progress["total"] - progress["current"]
            eta = remaining_items / rate if rate > 0 else None

        return jsonify(
            {
                "status": "success",
                "data": {
                    "scan_id": scan_id,
                    "status": progress["status"],
                    "current": progress["current"],
                    "total": progress["total"],
                    "percentage": round(percentage, 1),
                    "message": progress["message"],
                    "elapsed_time": round(elapsed_time, 1),
                    "eta": round(eta, 1) if eta else None,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting scan progress: {str(e)}", exc_info=True)
        return jsonify(
            {"status": "error", "message": f"Failed to get scan progress: {str(e)}"}
        ), 500


@main_bp.route("/duplicates/merge", methods=["POST"])
def merge_duplicates():
    """Merge duplicate prospects, preserving AI data from the best record."""
    try:
        from flask import request
        from sqlalchemy.orm.attributes import flag_modified

        data = request.get_json()
        if not data or "keep_id" not in data or "remove_ids" not in data:
            return jsonify(
                {"status": "error", "message": "keep_id and remove_ids are required"}
            ), 400

        keep_id = data["keep_id"]
        remove_ids = data["remove_ids"]

        if not isinstance(remove_ids, list) or not remove_ids:
            return jsonify(
                {"status": "error", "message": "remove_ids must be a non-empty list"}
            ), 400

        # Get the record to keep
        keep_record = db.session.query(Prospect).filter_by(id=keep_id).first()
        if not keep_record:
            return jsonify(
                {"status": "error", "message": f"Record with id {keep_id} not found"}
            ), 404

        # Get records to remove
        remove_records = (
            db.session.query(Prospect).filter(Prospect.id.in_(remove_ids)).all()
        )

        if len(remove_records) != len(remove_ids):
            return jsonify(
                {"status": "error", "message": "Some records to remove were not found"}
            ), 404

        # Merge strategy: preserve AI data if any record has it
        ai_enhanced_records = [r for r in remove_records if r.ollama_processed_at]
        if ai_enhanced_records and not keep_record.ollama_processed_at:
            # Use AI data from the best AI-enhanced record (most recent)
            best_ai_record = max(
                ai_enhanced_records, key=lambda x: x.ollama_processed_at
            )

            # Copy AI fields
            ai_fields = [
                "naics",
                "naics_description",
                "naics_source",
                "estimated_value_min",
                "estimated_value_max",
                "estimated_value_single",
                "primary_contact_email",
                "primary_contact_name",
                "ai_enhanced_title",
                "ollama_processed_at",
                "ollama_model_version",
            ]

            for field in ai_fields:
                if hasattr(best_ai_record, field):
                    setattr(keep_record, field, getattr(best_ai_record, field))

            # Merge extra fields
            if best_ai_record.extra:
                if keep_record.extra or best_ai_record.extra:
                    # Parse JSON strings if needed
                    import json

                    keep_extra = {}
                    ai_extra = {}

                    if keep_record.extra:
                        keep_extra = (
                            keep_record.extra
                            if isinstance(keep_record.extra, dict)
                            else json.loads(keep_record.extra)
                        )

                    if best_ai_record.extra:
                        ai_extra = (
                            best_ai_record.extra
                            if isinstance(best_ai_record.extra, dict)
                            else json.loads(best_ai_record.extra)
                        )

                    # Merge extras, preferring AI-enhanced data
                    merged_extra = {**keep_extra, **ai_extra}
                    keep_record.extra = json.dumps(merged_extra)
                else:
                    keep_record.extra = best_ai_record.extra

                # Flag as modified for SQLAlchemy
                flag_modified(keep_record, "extra")

        # Delete the duplicate records
        for record in remove_records:
            db.session.delete(record)

        db.session.commit()

        logger.info(f"Merged duplicates: kept {keep_id}, removed {remove_ids}")

        return jsonify(
            {
                "status": "success",
                "data": {
                    "kept_id": keep_id,
                    "removed_ids": remove_ids,
                    "ai_data_preserved": bool(ai_enhanced_records),
                    "message": f"Successfully merged {len(remove_ids)} duplicate(s) into record {keep_id}",
                },
            }
        )

    except Exception as e:
        logger.error(f"Error merging duplicates: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify(
            {"status": "error", "message": f"Failed to merge duplicates: {str(e)}"}
        ), 500


@main_bp.route("/duplicates/sources", methods=["GET"])
def get_data_sources_for_duplicates():
    """Get list of data sources for duplicate detection filtering."""
    try:
        from app.database.models import DataSource

        # Use a single query with a subquery to get counts
        sources_with_counts = (
            db.session.query(
                DataSource.id,
                DataSource.name,
                func.count(Prospect.id).label("prospect_count"),
            )
            .outerjoin(Prospect, DataSource.id == Prospect.source_id)
            .group_by(DataSource.id, DataSource.name)
            .order_by(DataSource.name)
            .all()
        )

        return jsonify(
            {
                "status": "success",
                "data": {
                    "sources": [
                        {"id": source_id, "name": name, "prospect_count": count or 0}
                        for source_id, name, count in sources_with_counts
                    ]
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting data sources: {str(e)}", exc_info=True)
        return jsonify(
            {"status": "error", "message": f"Failed to get data sources: {str(e)}"}
        ), 500


# Add main/general routes here
