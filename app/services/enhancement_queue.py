"""Simplified Enhancement Queue

Replaces the complex EnhancementQueueService with simple function-based processing.
This maintains the same API but with significantly reduced complexity.
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC

UTC = UTC
from datetime import datetime
from enum import Enum
from typing import Any

from app.database.models import Prospect, db
from app.services.llm_service import EnhancementType, llm_service
from app.utils.logger import logger


class QueueStatus(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class EnhancementProgress:
    """Simple progress tracking for enhancements"""

    status: QueueStatus = QueueStatus.IDLE
    enhancement_type: EnhancementType | None = None
    processed: int = 0
    total: int = 0
    current_prospect_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    errors: list[str] = field(default_factory=list)


class MockQueueItem:
    """Mock queue item for backward compatibility with API expectations"""

    def __init__(
        self,
        prospect_id: str,
        user_id: int,
        enhancement_type: str,
        processing_type: str,
        status: str,
        item_id: str = None,
    ):
        self.prospect_id = prospect_id
        self.user_id = user_id
        self.enhancement_type = enhancement_type
        self.processing_type = processing_type
        self._status = status
        # Generate a unique ID if not provided
        self.id = item_id or f"{processing_type}_{prospect_id[:8]}_{int(time.time())}"

    @property
    def type(self):
        """Mock type enum with value attribute"""

        class MockType:
            def __init__(self, value):
                self.value = value

        return MockType(self.processing_type)

    @property
    def status(self):
        """Mock status enum with value attribute"""

        class MockStatus:
            def __init__(self, value):
                self.value = value

        return MockStatus(self._status)


class SimpleEnhancementQueue:
    """Simplified enhancement queue that handles both individual and bulk processing
    without the complexity of priority queues and multiple thread management.
    """

    def __init__(self):
        self._progress = EnhancementProgress()
        self._processing = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._app = None  # Store Flask app reference

        # Track current enhancement details for API compatibility
        self._current_prospect_id: str | None = None
        self._current_user_id: int | None = None
        self._current_enhancement_type: str | None = None
        self._current_processing_type: str = "individual"  # 'individual' or 'bulk'

        # Cache recent enhancement results for polling
        self._recent_results: dict[str, dict[str, Any]] = {}
        self._completed_steps: dict[
            str, list[str]
        ] = {}  # Track completed steps per prospect
        self._initial_queue_positions: dict[
            str, int
        ] = {}  # Track initial queue positions

        # Add a real queue for individual enhancements
        self._individual_queue: list[dict[str, Any]] = []
        self._queue_worker_thread: threading.Thread | None = None
        self._queue_worker_running = False

    def set_app(self, app):
        """Set the Flask app reference for use in background threads"""
        self._app = app
        logger.info("Flask app reference set in enhancement queue")

    def _process_queue_worker(self):
        """Background worker to process queued enhancements"""
        logger.info("Queue worker started")

        # Check if app is set
        if not self._app:
            logger.error("Flask app not set in enhancement queue - worker cannot start")
            return

        while self._queue_worker_running:
            item_to_process = None
            with self._lock:
                # Find next queued item (don't remove it yet)
                for item in self._individual_queue:
                    if item["status"] == "queued":
                        item["status"] = "processing"
                        item_to_process = item
                        break

            if not item_to_process:
                time.sleep(1)
                continue

            # Process the item outside the lock, but within app context
            with self._app.app_context():
                try:
                    logger.info(
                        f"Processing queued enhancement for prospect {item_to_process['prospect_id'][:8]}..."
                    )
                    result = self.enhance_single_prospect(
                        item_to_process["prospect_id"],
                        item_to_process["enhancement_type"],
                        item_to_process["user_id"],
                        item_to_process["force_redo"],
                    )

                    # Update item status
                    with self._lock:
                        item_to_process["status"] = (
                            "completed"
                            if result.get("status") in ["completed", "no_changes"]
                            else "failed"
                        )
                        item_to_process["completed_at"] = time.time()
                        item_to_process["result"] = result

                except Exception as e:
                    logger.error(
                        f"Error processing queued enhancement: {e}", exc_info=True
                    )
                    with self._lock:
                        item_to_process["status"] = "failed"
                        item_to_process["error"] = str(e)
                        item_to_process["completed_at"] = time.time()

            # Clean up old completed/failed items (older than 5 minutes)
            with self._lock:
                current_time = time.time()
                self._individual_queue = [
                    item
                    for item in self._individual_queue
                    if item["status"] in ["queued", "processing"]
                    or (current_time - item.get("completed_at", current_time)) < 300
                ]

            time.sleep(0.5)  # Small delay between items

        logger.info("Queue worker stopped")

    def start_queue_worker(self):
        """Start the background queue worker"""
        with self._lock:
            if self._queue_worker_running:
                return

            self._queue_worker_running = True
            self._queue_worker_thread = threading.Thread(
                target=self._process_queue_worker
            )
            self._queue_worker_thread.daemon = True
            self._queue_worker_thread.start()
            logger.info("Started queue worker thread")

    def stop_queue_worker(self):
        """Stop the background queue worker"""
        with self._lock:
            self._queue_worker_running = False

        if self._queue_worker_thread:
            self._queue_worker_thread.join(timeout=5)
            self._queue_worker_thread = None
            logger.info("Stopped queue worker thread")

    def add_to_queue(
        self, prospect_id: str, enhancement_type: str, user_id: int, force_redo: bool
    ) -> str:
        """Add an enhancement to the queue and return immediately"""
        queue_item_id = f"individual_{prospect_id[:8]}_{int(time.time())}"

        with self._lock:
            self._individual_queue.append(
                {
                    "queue_item_id": queue_item_id,
                    "prospect_id": prospect_id,
                    "enhancement_type": enhancement_type,
                    "user_id": user_id,
                    "force_redo": force_redo,
                    "status": "queued",
                    "created_at": time.time(),
                }
            )

            # Calculate actual queue position (only count queued items)
            queue_position = sum(
                1 for item in self._individual_queue if item["status"] == "queued"
            )

            # Store initial queue position
            self._initial_queue_positions[prospect_id] = queue_position

            # Initialize completed steps
            self._completed_steps[prospect_id] = []

        # Start worker if not running
        self.start_queue_worker()

        logger.info(
            f"Added enhancement to queue: {queue_item_id} at position {queue_position}"
        )
        return queue_item_id

    def get_status(self) -> dict[str, Any]:
        """Get current processing status"""
        with self._lock:
            # Create pending items list for API compatibility
            pending_items = []
            if self._processing and self._current_prospect_id:
                item_id = f"{self._current_processing_type}_{self._current_prospect_id}_{self._current_user_id or 1}"
                pending_items.append(
                    {
                        "id": item_id,
                        "prospect_id": self._current_prospect_id,
                        "user_id": self._current_user_id or 1,
                        "type": self._current_processing_type,
                        "enhancement_type": self._current_enhancement_type or "all",
                        "status": "processing" if self._processing else "pending",
                    }
                )

            return {
                "status": self._progress.status.value,
                "enhancement_type": self._progress.enhancement_type,
                "processed": self._progress.processed,
                "total": self._progress.total,
                "current_prospect_id": self._progress.current_prospect_id,
                "started_at": self._progress.started_at.isoformat()
                if self._progress.started_at
                else None,
                "completed_at": self._progress.completed_at.isoformat()
                if self._progress.completed_at
                else None,
                "errors": self._progress.errors[-10:],  # Keep only last 10 errors
                "is_processing": self._processing,
                "pending_items": pending_items,
                "queue_size": len(pending_items),
                "worker_running": self._processing,
            }

    def is_processing(self) -> bool:
        """Check if currently processing"""
        return self._processing

    def _create_progress_callback(self, prospect_id: str) -> callable:
        """Create a progress callback function for status updates"""

        def progress_callback(progress_data):
            try:
                # Log progress for debugging
                field = progress_data.get("field", "unknown")
                status = progress_data.get("status", "processing")

                # Update current enhancement type based on field
                with self._lock:
                    if field in ["title", "titles"]:
                        self._current_enhancement_type = "titles"
                    elif field in ["value", "values"]:
                        self._current_enhancement_type = "values"
                    elif field == "naics":
                        self._current_enhancement_type = "naics"
                    elif field in ["set_aside", "set_asides"]:
                        self._current_enhancement_type = "set_asides"

                    # Track completed steps - normalize field names to match frontend expectations
                    if status == "completed" and prospect_id in self._completed_steps:
                        # Map field names to expected frontend names
                        normalized_field = field
                        if field in ["title", "titles"]:
                            normalized_field = "titles"
                        elif field in ["value", "values"]:
                            normalized_field = "values"
                        elif field == "naics":
                            normalized_field = "naics"
                        elif field in ["set_aside", "set_asides"]:
                            normalized_field = "set_asides"

                        if normalized_field not in self._completed_steps[prospect_id]:
                            self._completed_steps[prospect_id].append(normalized_field)

                if status == "processing":
                    message = f"Processing {field}..."
                else:
                    message = f"Completed {field}"

                logger.debug(f"Enhancement progress for {prospect_id[:8]}: {message}")
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

        return progress_callback

    def enhance_single_prospect(
        self,
        prospect_id: str,
        enhancement_type: EnhancementType = "all",
        user_id: int | None = None,
        force_redo: bool = False,
    ) -> dict[str, Any]:
        """Enhance a single prospect immediately (synchronous).
        This is for real-time UI updates.
        """
        try:
            prospect = Prospect.query.get(prospect_id)
            if not prospect:
                return {
                    "status": "error",
                    "message": f"Prospect {prospect_id} not found",
                }

            # Track current enhancement details for API compatibility
            with self._lock:
                self._current_prospect_id = prospect_id
                self._current_user_id = user_id
                self._current_enhancement_type = enhancement_type
                self._current_processing_type = "individual"
                self._processing = True
                # Initialize completed steps tracking
                self._completed_steps[prospect_id] = []

            logger.info(
                f"Starting individual enhancement for prospect {prospect_id[:8]}... ({enhancement_type}, force_redo={force_redo})"
            )

            # Create progress callback for status updates
            progress_callback = self._create_progress_callback(prospect_id)

            # Pass force_redo to LLM service
            results = llm_service.enhance_single_prospect(
                prospect, enhancement_type, progress_callback, force_redo
            )

            if any(results.values()):
                db.session.commit()
                logger.info(
                    f"Successfully enhanced prospect {prospect_id[:8]}... - {results}"
                )

                # Store result for polling
                with self._lock:
                    self._recent_results[prospect_id] = {
                        "status": "completed",
                        "enhancements": results,
                        "completed_at": time.time(),
                        "completed_steps": self._completed_steps.get(
                            prospect_id, ["titles", "values", "naics", "set_asides"]
                        ),
                    }

                # Enhancement completed successfully

                return {
                    "status": "completed",
                    "prospect_id": prospect_id,
                    "enhancements": results,
                    "message": f"Enhanced {sum(results.values())} fields",
                }
            # No enhancements needed

            # Store result for polling
            with self._lock:
                self._recent_results[prospect_id] = {
                    "status": "no_changes",
                    "completed_at": time.time(),
                    "completed_steps": self._completed_steps.get(prospect_id, []),
                }

            return {
                "status": "no_changes",
                "prospect_id": prospect_id,
                "message": "No enhancements needed or possible",
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error enhancing single prospect {prospect_id}: {e}")

            # Enhancement failed

            return {"status": "error", "prospect_id": prospect_id, "message": str(e)}
        finally:
            # Clear current enhancement tracking
            # Add a small delay to allow final polling to see the processing state
            time.sleep(0.5)
            with self._lock:
                self._current_prospect_id = None
                self._current_user_id = None
                self._current_enhancement_type = None
                self._processing = False

    def start_bulk_enhancement(
        self,
        enhancement_type: EnhancementType = "all",
        prospect_ids: list[str] | None = None,
        skip_existing: bool = True,
    ) -> dict[str, Any]:
        """Start bulk enhancement processing in background thread."""
        if self._processing:
            return {"status": "error", "message": "Enhancement already in progress"}

        # Get prospects to process
        if prospect_ids:
            prospects = Prospect.query.filter(Prospect.id.in_(prospect_ids)).all()
        else:
            prospects = self._get_prospects_needing_enhancement(
                enhancement_type, skip_existing
            )

        if not prospects:
            return {
                "status": "completed",
                "message": "No prospects need enhancement",
                "total": 0,
            }

        # Initialize progress
        with self._lock:
            self._progress = EnhancementProgress(
                status=QueueStatus.PROCESSING,
                enhancement_type=enhancement_type,
                total=len(prospects),
                started_at=datetime.now(UTC),
            )

        self._processing = True
        self._stop_event.clear()

        # Start background thread
        self._thread = threading.Thread(
            target=self._bulk_processing_worker,
            args=(prospects, enhancement_type),
            daemon=True,
        )
        self._thread.start()

        logger.info(
            f"Started bulk enhancement: {len(prospects)} prospects for {enhancement_type}"
        )

        return {
            "status": "started",
            "enhancement_type": enhancement_type,
            "total": len(prospects),
            "message": f"Started bulk enhancement of {len(prospects)} prospects",
        }

    def stop_processing(self) -> dict[str, Any]:
        """Stop current processing"""
        if not self._processing:
            return {"status": "error", "message": "No processing currently running"}

        logger.info("Stopping enhancement processing...")
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        with self._lock:
            self._progress.status = QueueStatus.STOPPED
            self._progress.completed_at = datetime.now(UTC)

        self._processing = False

        return {"status": "stopped", "message": "Enhancement processing stopped"}

    # Backward compatibility methods for API
    def get_queue_status(self) -> dict[str, Any]:
        """Alias for get_status for backward compatibility"""
        return self.get_status()

    def get_item_status(self, item_id: str) -> dict[str, Any]:
        """Get status of a specific item"""
        with self._lock:
            # First check if item is in the queue
            for queue_item in self._individual_queue:
                if queue_item.get("queue_item_id") == item_id:
                    prospect_id = queue_item["prospect_id"]

                    if queue_item["status"] == "queued":
                        # Calculate queue position
                        position = 1
                        for idx, item in enumerate(self._individual_queue):
                            if item["status"] == "queued":
                                if item["queue_item_id"] == item_id:
                                    break
                                position += 1

                        return {
                            "item_id": item_id,
                            "status": "queued",
                            "position": position,
                            "current_step": None,
                            "completed_steps": [],
                            "error": None,
                        }
                    if queue_item["status"] == "processing":
                        # Item is currently being processed
                        current_step = None
                        if self._current_enhancement_type:
                            if self._current_enhancement_type == "titles":
                                current_step = "Enhancing title..."
                            elif self._current_enhancement_type == "values":
                                current_step = "Parsing contract values..."
                            elif self._current_enhancement_type == "naics":
                                current_step = "Classifying NAICS code..."
                            elif self._current_enhancement_type == "set_asides":
                                current_step = "Processing set asides..."
                            else:
                                current_step = "Processing..."

                        return {
                            "item_id": item_id,
                            "status": "processing",
                            "position": None,
                            "current_step": current_step,
                            "completed_steps": self._completed_steps.get(
                                prospect_id, []
                            ),
                            "error": None,
                        }
                    if queue_item["status"] == "completed":
                        return {
                            "item_id": item_id,
                            "status": "completed",
                            "position": None,
                            "current_step": None,
                            "completed_steps": self._completed_steps.get(
                                prospect_id, ["titles", "values", "naics", "set_asides"]
                            ),
                            "error": None,
                        }
                    if queue_item["status"] == "failed":
                        return {
                            "item_id": item_id,
                            "status": "failed",
                            "position": None,
                            "current_step": None,
                            "completed_steps": self._completed_steps.get(
                                prospect_id, []
                            ),
                            "error": queue_item.get("error", "Unknown error"),
                        }

            # Extract prospect_id from item_id for backward compatibility
            parts = item_id.split("_")
            if len(parts) >= 2:
                prospect_id = parts[1]
            else:
                prospect_id = None

            # First check if we have cached results
            if prospect_id and prospect_id in self._recent_results:
                result = self._recent_results[prospect_id]
                # Clean up old results (older than 5 minutes)
                if time.time() - result.get("completed_at", 0) > 300:
                    del self._recent_results[prospect_id]
                else:
                    # Return the cached result
                    return {
                        "item_id": item_id,
                        "status": result.get("status", "completed"),
                        "position": self._initial_queue_positions.get(prospect_id, 1),
                        "current_step": None,
                        "completed_steps": result.get(
                            "completed_steps",
                            ["titles", "values", "naics", "set_asides"],
                        ),
                        "error": None,
                    }

            # If currently processing, check if it matches this item
            if (
                self._processing
                and self._current_prospect_id
                and self._current_prospect_id == prospect_id
            ):
                # Item is currently being processed
                # Map enhancement_type to current_step
                current_step = None
                if self._current_enhancement_type:
                    if self._current_enhancement_type == "titles":
                        current_step = "Enhancing title..."
                    elif self._current_enhancement_type == "values":
                        current_step = "Parsing contract values..."
                    elif self._current_enhancement_type == "naics":
                        current_step = "Classifying NAICS code..."
                    elif self._current_enhancement_type == "set_asides":
                        current_step = "Processing set asides..."
                    else:
                        current_step = "Processing..."

                return {
                    "item_id": item_id,
                    "status": "processing",
                    "position": self._initial_queue_positions.get(prospect_id, 1),
                    "current_step": current_step,
                    "completed_steps": self._completed_steps.get(prospect_id, []),
                    "error": None,
                }

            # Check if item failed
            if hasattr(self._progress, "errors") and self._progress.errors:
                for error in self._progress.errors:
                    if item_id in str(error) or (
                        prospect_id and str(prospect_id) in str(error)
                    ):
                        return {
                            "item_id": item_id,
                            "status": "failed",
                            "position": None,
                            "current_step": None,
                            "completed_steps": [],
                            "error": str(error),
                        }

            # Check if prospect was processed successfully
            if prospect_id:
                # Query database to check if prospect has been enhanced
                from app.database.models import Prospect

                prospect = Prospect.query.get(prospect_id)
                if prospect and prospect.ollama_processed_at:
                    # Clean up cached initial position for completed item
                    if prospect_id in self._initial_queue_positions:
                        del self._initial_queue_positions[prospect_id]

                    return {
                        "item_id": item_id,
                        "status": "completed",
                        "position": None,
                        "current_step": None,
                        "completed_steps": ["titles", "values", "naics", "set_asides"],
                        "error": None,
                    }

            # Default to queued
            return {
                "item_id": item_id,
                "status": "queued",
                "position": 1,  # Simplified - always position 1 if queued
                "current_step": None,
                "completed_steps": [],
                "error": None,
            }

    def cancel_item(self, item_id: str) -> bool:
        """Cancel a specific item (simplified - just stops current processing)"""
        if self._processing:
            self.stop_processing()
            return True
        return False

    def start_worker(self) -> dict[str, Any]:
        """Start worker (no-op for simplified implementation)"""
        return {"status": "ready", "message": "Worker ready"}

    def stop_worker(self) -> dict[str, Any]:
        """Stop worker (alias for stop_processing)"""
        return self.stop_processing()

    @property
    def _queue_items(self) -> dict[str, MockQueueItem]:
        """Backward compatibility for queue items access"""
        with self._lock:
            items = {}
            # Add all queued items from the individual queue
            for queue_item in self._individual_queue:
                if queue_item["status"] in ["queued", "processing"]:
                    mock_item = MockQueueItem(
                        prospect_id=queue_item["prospect_id"],
                        user_id=queue_item.get("user_id", 1),
                        enhancement_type=queue_item.get("enhancement_type", "all"),
                        processing_type="individual",
                        status=queue_item["status"],
                        item_id=queue_item["queue_item_id"],
                    )
                    items[queue_item["queue_item_id"]] = mock_item

            # Also add current processing item if different
            if self._processing and self._current_prospect_id:
                # Create mock queue item with expected attributes and consistent ID
                item_id = f"{self._current_processing_type}_{self._current_prospect_id}_{self._current_user_id or 1}"
                if item_id not in items:
                    mock_item = MockQueueItem(
                        prospect_id=self._current_prospect_id,
                        user_id=self._current_user_id or 1,
                        enhancement_type=self._current_enhancement_type or "all",
                        processing_type=self._current_processing_type,
                        status="processing",
                        item_id=item_id,
                    )
                    items[item_id] = mock_item

            return items

    def _get_prospects_needing_enhancement(
        self, enhancement_type: EnhancementType, skip_existing: bool
    ) -> list[Prospect]:
        """Get prospects that need the specified enhancement type"""
        query = Prospect.query

        if skip_existing:
            if enhancement_type == "values":
                query = query.filter(Prospect.estimated_value_single.is_(None))
            elif enhancement_type == "naics":
                query = query.filter(
                    (Prospect.naics.is_(None))
                    | (Prospect.naics_source != "llm_inferred")
                )
            elif enhancement_type == "titles":
                query = query.filter(Prospect.ai_enhanced_title.is_(None))
            elif enhancement_type == "set_asides":
                query = query.filter(Prospect.set_aside_standardized.is_(None))
            # For "all", we don't filter - check each enhancement individually

        return query.limit(10000).all()  # Reasonable limit to prevent memory issues

    def _bulk_processing_worker(
        self, prospects: list[Prospect], enhancement_type: EnhancementType
    ):
        """Worker thread for bulk processing"""
        logger.info(f"Bulk processing worker started: {len(prospects)} prospects")

        try:
            for i, prospect in enumerate(prospects):
                if self._stop_event.is_set():
                    logger.info("Bulk processing stopped by user request")
                    break

                # Update progress
                with self._lock:
                    self._progress.current_prospect_id = prospect.id

                try:
                    results = llm_service.enhance_single_prospect(
                        prospect, enhancement_type
                    )

                    if any(results.values()):
                        db.session.commit()
                        logger.debug(
                            f"Enhanced prospect {prospect.id[:8]}... - {results}"
                        )

                    with self._lock:
                        self._progress.processed = i + 1

                except Exception as e:
                    logger.error(f"Error processing prospect {prospect.id}: {e}")
                    with self._lock:
                        self._progress.errors.append(
                            f"Prospect {prospect.id[:8]}...: {str(e)}"
                        )
                        self._progress.processed = i + 1  # Still count as processed

                # Brief pause to prevent overwhelming the system
                if not self._stop_event.wait(
                    0.1
                ):  # 100ms delay, but can be interrupted
                    continue
                break

            # Mark as completed
            with self._lock:
                if not self._stop_event.is_set():
                    self._progress.status = QueueStatus.COMPLETED
                    logger.info(
                        f"Bulk processing completed: {self._progress.processed}/{self._progress.total} prospects"
                    )
                else:
                    self._progress.status = QueueStatus.STOPPED
                    logger.info(
                        f"Bulk processing stopped: {self._progress.processed}/{self._progress.total} prospects"
                    )

                self._progress.completed_at = datetime.now(UTC)

        except Exception as e:
            logger.error(f"Error in bulk processing worker: {e}")
            with self._lock:
                self._progress.status = QueueStatus.FAILED
                self._progress.errors.append(f"Worker error: {str(e)}")
                self._progress.completed_at = datetime.now(UTC)
        finally:
            self._processing = False


# Global instance
enhancement_queue = SimpleEnhancementQueue()


# Backward compatibility functions
def add_individual_enhancement(
    prospect_id: str,
    enhancement_type: EnhancementType = "all",
    user_id: int | None = None,
    force_redo: bool = False,
) -> dict[str, Any]:
    """Add individual prospect enhancement to queue (asynchronous processing)"""
    # Add to queue instead of processing immediately
    queue_item_id = enhancement_queue.add_to_queue(
        prospect_id, enhancement_type, user_id or 1, force_redo
    )

    # Get current queue position
    with enhancement_queue._lock:
        queue_position = len(enhancement_queue._individual_queue)

    return {
        "queue_item_id": queue_item_id,
        "was_existing": False,  # For individual enhancements, always treat as new
        "status": "queued",
        "message": f"Enhancement queued for prospect {prospect_id}",
        "prospect_id": prospect_id,
        "enhancements": {},
        "queue_position": queue_position,
    }


def add_bulk_enhancement(
    prospect_ids: list[str], enhancement_type: EnhancementType = "all"
) -> str:
    """Add bulk enhancement (background processing)"""
    enhancement_queue.start_bulk_enhancement(enhancement_type, prospect_ids)
    return f"bulk_{enhancement_type}_{int(time.time())}"


def get_queue_status() -> dict[str, Any]:
    """Get current queue status"""
    return enhancement_queue.get_status()


def stop_processing() -> dict[str, Any]:
    """Stop current processing"""
    return enhancement_queue.stop_processing()
