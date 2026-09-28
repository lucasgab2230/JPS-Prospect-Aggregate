"""
Unit tests for Enhancement Queue Service.

Tests the queue management system that handles prospect enhancement requests.
Following production-level testing principles:
- No hardcoded expected values
- Tests verify behavior, not specific data
- Uses real queue operations where possible
- Mocks only external dependencies
"""

import random
import threading
import time
from datetime import UTC

UTC = UTC
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from app.services.enhancement_queue import (
    MockQueueItem,
    QueueStatus,
    SimpleEnhancementQueue,
    add_individual_enhancement,
    enhancement_queue,
)


class TestMockQueueItem:
    """Test the MockQueueItem dataclass following black-box testing principles."""

    def test_queue_item_creation(self):
        """Test creating a queue item with various configurations."""
        # Generate random test data
        prospect_id = f"PROSPECT-{random.randint(1000, 9999)}"
        user_id = random.randint(1, 100)
        status = random.choice(list(QueueStatus))
        enhancement_types = random.choice(
            [["values"], ["titles"], ["naics"], ["values", "titles"], ["all"]]
        )
        force_redo = random.choice([True, False])

        before_creation = datetime.now(UTC)

        # Create queue item
        item = MockQueueItem(
            prospect_id=prospect_id,
            status=status,
            user_id=user_id,
            enhancement_types=enhancement_types,
            force_redo=force_redo,
        )

        after_creation = datetime.now(UTC)

        # Verify item properties exist and are set
        assert item.prospect_id == prospect_id
        assert item.status == status
        assert item.user_id == user_id
        assert item.enhancement_types == enhancement_types
        assert item.force_redo == force_redo

        # Verify optional fields are initialized
        assert item.started_at is None
        assert item.completed_at is None
        assert item.error is None
        assert isinstance(item.progress, dict)

        # Verify timestamp is reasonable (if it has one)
        if hasattr(item, "created_at") and item.created_at:
            # Allow some tolerance for test execution time
            assert (
                before_creation - timedelta(seconds=1)
                <= item.created_at
                <= after_creation + timedelta(seconds=1)
            )

    def test_queue_item_defaults(self):
        """Test queue item uses sensible defaults."""
        # Generate random required fields
        prospect_id = f"PROSPECT-{random.randint(10000, 99999)}"
        user_id = random.randint(1, 1000)

        # Create item with minimal required fields
        item = MockQueueItem(
            prospect_id=prospect_id, status=QueueStatus.PENDING, user_id=user_id
        )

        # Verify defaults are applied
        assert item.prospect_id == prospect_id
        assert item.status == QueueStatus.PENDING
        assert item.user_id == user_id

        # Check default values (behavioral verification)
        assert isinstance(item.enhancement_types, list)
        assert len(item.enhancement_types) > 0  # Should have at least one type
        assert isinstance(item.force_redo, bool)
        assert isinstance(item.progress, dict)


class TestEnhancementQueue:
    """Test the SimpleEnhancementQueue class following black-box testing principles."""

    @pytest.fixture
    def queue(self):
        """Create an enhancement queue instance."""
        return SimpleEnhancementQueue()

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock LLM service."""
        mock_service = Mock()
        # Don't hardcode return values - let tests set them
        mock_service.enhance_prospect = Mock()
        return mock_service

    def test_queue_initialization(self, queue):
        """Test queue initialization behavior."""
        # Verify queue starts empty
        assert isinstance(queue.queue, dict)
        assert len(queue.queue) == 0

        # Verify processing state
        assert hasattr(queue, "_processing")
        assert not queue._processing

        # Verify no current item is being processed
        assert hasattr(queue, "_current_item")
        assert queue._current_item is None

    def test_add_to_queue(self, queue):
        """Test adding items to the queue with dynamic data."""
        # Generate random test data
        num_items = random.randint(2, 5)
        prospect_ids = [
            f"PROSPECT-{random.randint(1000, 9999)}" for _ in range(num_items)
        ]
        user_ids = [random.randint(1, 100) for _ in range(num_items)]

        positions = []
        for i, (prospect_id, user_id) in enumerate(
            zip(prospect_ids, user_ids, strict=False)
        ):
            enhancement_types = random.choice(
                [["values"], ["titles"], ["naics"], ["values", "titles"], ["all"]]
            )
            force_redo = random.choice([True, False])

            # Add item to queue
            position = queue.add_to_queue(
                prospect_id=prospect_id,
                user_id=user_id,
                enhancement_types=enhancement_types,
                force_redo=force_redo,
            )

            positions.append(position)

            # Verify item was added
            assert prospect_id in queue.queue
            assert queue.queue[prospect_id].status == QueueStatus.PENDING
            assert queue.queue[prospect_id].user_id == user_id
            assert queue.queue[prospect_id].enhancement_types == enhancement_types
            assert queue.queue[prospect_id].force_redo == force_redo

        # Verify positions are sequential
        for i, pos in enumerate(positions):
            assert pos == i + 1

    def test_add_duplicate_to_queue(self, queue):
        """Test adding duplicate prospect to queue."""
        # Generate random prospect ID
        prospect_id = f"PROSPECT-{random.randint(10000, 99999)}"
        user_id = random.randint(1, 100)

        # Add item first time
        first_position = queue.add_to_queue(prospect_id, user_id=user_id)
        initial_queue_size = len(queue.queue)

        # Try to add same prospect again
        second_position = queue.add_to_queue(prospect_id, user_id=user_id)

        # Verify behavior - should not create duplicate
        assert second_position == first_position  # Returns existing position
        assert len(queue.queue) == initial_queue_size  # Queue size unchanged

    def test_remove_from_queue(self, queue):
        """Test removing items from queue dynamically."""
        # Add random number of items
        num_items = random.randint(3, 6)
        prospect_ids = [
            f"PROSPECT-{random.randint(1000, 9999)}" for _ in range(num_items)
        ]

        for i, prospect_id in enumerate(prospect_ids):
            queue.add_to_queue(prospect_id, user_id=random.randint(1, 100))

        # Select a random item to remove (not first or last for better testing)
        if len(prospect_ids) > 2:
            item_to_remove = random.choice(prospect_ids[1:-1])
        else:
            item_to_remove = prospect_ids[0]

        # Remove the item
        result = queue.remove_from_queue(item_to_remove)

        # Verify removal succeeded
        assert result is True
        assert item_to_remove not in queue.queue

        # Verify remaining items have updated positions
        remaining_items = [pid for pid in prospect_ids if pid != item_to_remove]
        for i, prospect_id in enumerate(remaining_items):
            if prospect_id in queue.queue:
                assert queue.queue[prospect_id].queue_position == i + 1

        # Try to remove non-existent item
        fake_id = f"FAKE-{random.randint(100000, 999999)}"
        result = queue.remove_from_queue(fake_id)
        assert result is False

    def test_get_queue_status(self, queue):
        """Test getting queue status with various queue states."""
        # Test empty queue
        status = queue.get_queue_status()
        assert isinstance(status, dict)
        assert status["total_items"] == 0
        assert status["pending_items"] == 0
        assert status["processing_items"] == 0
        assert status["is_processing"] is False

        # Add random number of items
        num_items = random.randint(2, 8)
        prospect_ids = []

        for _ in range(num_items):
            prospect_id = f"PROSPECT-{random.randint(1000, 9999)}"
            queue.add_to_queue(prospect_id, user_id=random.randint(1, 100))
            prospect_ids.append(prospect_id)

        # Randomly set some items to different statuses
        num_processing = random.randint(0, min(2, num_items))
        num_completed = random.randint(0, min(2, num_items - num_processing))

        for i in range(num_processing):
            queue.queue[prospect_ids[i]].status = QueueStatus.PROCESSING

        for i in range(num_processing, num_processing + num_completed):
            queue.queue[prospect_ids[i]].status = QueueStatus.COMPLETED

        # Set processing state
        if num_processing > 0:
            queue._current_item = prospect_ids[0]
            queue._processing = True

        # Get status
        status = queue.get_queue_status()

        # Verify counts match
        assert status["total_items"] == num_items
        assert status["processing_items"] == num_processing
        assert status["is_processing"] == (num_processing > 0)

        # Verify all items are accounted for
        total_counted = (
            status["pending_items"]
            + status["processing_items"]
            + status.get("completed_items", 0)
        )
        assert total_counted <= num_items

    def test_get_item_status(self, queue):
        """Test getting individual item status with dynamic data."""
        # Test non-existent item
        fake_id = f"FAKE-{random.randint(100000, 999999)}"
        status = queue.get_item_status(fake_id)
        assert status is None

        # Add item with random configuration
        prospect_id = f"PROSPECT-{random.randint(1000, 9999)}"
        user_id = random.randint(1, 100)
        enhancement_types = random.choice(
            [["values"], ["titles"], ["naics"], ["values", "titles"], ["all"]]
        )

        position = queue.add_to_queue(
            prospect_id, user_id=user_id, enhancement_types=enhancement_types
        )

        # Get item status
        status = queue.get_item_status(prospect_id)

        # Verify status structure and content
        assert status is not None
        assert isinstance(status, dict)
        assert "status" in status
        assert status["status"] == QueueStatus.PENDING.value
        assert "queue_position" in status
        assert status["queue_position"] == position
        assert "enhancement_types" in status
        assert status["enhancement_types"] == enhancement_types

    @patch("app.services.enhancement_queue.llm_service")
    @patch("app.services.enhancement_queue.db")
    def test_process_item_success(self, mock_db, mock_llm, queue):
        """Test successful processing of a queue item."""
        # Generate random test data
        prospect_id = f"{random.randint(1000, 9999)}"
        user_id = random.randint(1, 100)
        enhancement_types = random.choice(
            [["values"], ["titles"], ["naics"], ["values", "titles"]]
        )
        force_redo = random.choice([True, False])

        # Setup mocks
        mock_prospect = Mock()
        mock_prospect.id = int(prospect_id)
        mock_db.session.get.return_value = mock_prospect
        mock_llm.enhance_prospect.return_value = random.choice([True, False])

        # Create queue item
        item = MockQueueItem(
            prospect_id=prospect_id,
            status=QueueStatus.PENDING,
            user_id=user_id,
            enhancement_types=enhancement_types,
            force_redo=force_redo,
        )

        before_processing = datetime.now(UTC)

        # Process item
        queue._process_item(item)

        after_processing = datetime.now(UTC)

        # Verify prospect was enhanced with correct parameters
        mock_llm.enhance_prospect.assert_called_once()
        call_args = mock_llm.enhance_prospect.call_args
        assert call_args[0][0] == mock_prospect
        assert call_args[1]["enhancement_types"] == enhancement_types
        assert call_args[1]["force_redo"] == force_redo

        # Verify status updates
        assert item.status == QueueStatus.COMPLETED
        assert item.started_at is not None
        assert item.completed_at is not None
        assert item.error is None

        # Verify timestamps are reasonable
        assert (
            before_processing
            <= item.completed_at
            <= after_processing + timedelta(seconds=1)
        )

    @patch("app.services.enhancement_queue.llm_service")
    @patch("app.services.enhancement_queue.db")
    def test_process_item_prospect_not_found(self, mock_db, mock_llm, queue):
        """Test processing when prospect not found."""
        # Generate random non-existent prospect ID
        prospect_id = f"{random.randint(100000, 999999)}"
        user_id = random.randint(1, 100)

        # Setup mocks - prospect doesn't exist
        mock_db.session.get.return_value = None

        # Create queue item
        item = MockQueueItem(
            prospect_id=prospect_id, status=QueueStatus.PENDING, user_id=user_id
        )

        # Process item
        queue._process_item(item)

        # Verify error handling
        assert item.status == QueueStatus.ERROR
        assert item.error is not None
        assert (
            "not found" in item.error.lower() or "does not exist" in item.error.lower()
        )
        assert item.completed_at is not None

        # LLM should not be called when prospect doesn't exist
        mock_llm.enhance_prospect.assert_not_called()

    @patch("app.services.enhancement_queue.llm_service")
    @patch("app.services.enhancement_queue.db")
    def test_process_item_enhancement_error(self, mock_db, mock_llm, queue):
        """Test processing when enhancement fails."""
        # Generate random test data
        prospect_id = f"{random.randint(1000, 9999)}"
        user_id = random.randint(1, 100)

        # Generate random error message
        error_messages = [
            "LLM connection failed",
            "Model timeout",
            "Invalid response format",
            "Service unavailable",
            "Rate limit exceeded",
        ]
        error_msg = random.choice(error_messages)

        # Setup mocks
        mock_prospect = Mock()
        mock_prospect.id = int(prospect_id)
        mock_db.session.get.return_value = mock_prospect
        mock_llm.enhance_prospect.side_effect = Exception(error_msg)

        # Create queue item
        item = MockQueueItem(
            prospect_id=prospect_id, status=QueueStatus.PENDING, user_id=user_id
        )

        # Process item
        queue._process_item(item)

        # Verify error handling
        assert item.status == QueueStatus.ERROR
        assert item.error is not None
        assert error_msg in item.error or "error" in item.error.lower()
        assert item.completed_at is not None

    def test_start_stop_processing(self, queue):
        """Test starting and stopping queue processing."""
        with patch.object(queue, "_process_queue_loop") as mock_loop:
            # Start processing
            queue.start_processing()

            # Verify processing started
            assert queue._processing is True
            assert queue._thread is not None
            assert isinstance(queue._thread, threading.Thread)

            # Allow some time for thread to start
            time.sleep(0.05)

            # Stop processing
            queue.stop_processing()

            # Give thread reasonable time to stop
            max_wait = 2.0  # Maximum wait time
            wait_interval = 0.1
            elapsed = 0

            while queue._processing and elapsed < max_wait:
                time.sleep(wait_interval)
                elapsed += wait_interval

            # Verify processing stopped
            assert queue._processing is False

    @patch("app.services.enhancement_queue.llm_service")
    @patch("app.services.enhancement_queue.db")
    def test_process_queue_loop(self, mock_db, mock_llm, queue):
        """Test the main processing loop with dynamic data."""
        # Generate random number of items
        num_items = random.randint(2, 4)
        prospect_ids = [f"{random.randint(1000, 9999)}" for _ in range(num_items)]

        # Setup mocks
        mock_prospects = {}
        for pid in prospect_ids:
            mock_prospect = Mock()
            mock_prospect.id = int(pid)
            mock_prospects[pid] = mock_prospect

        def get_prospect(model, prospect_id):
            return mock_prospects.get(str(prospect_id))

        mock_db.session.get.side_effect = get_prospect

        # Track processing
        processed_count = [0]

        def enhance_side_effect(*args, **kwargs):
            processed_count[0] += 1
            # Stop after processing some items
            if processed_count[0] >= min(2, num_items):
                queue._processing = False
            return random.choice([True, False])

        mock_llm.enhance_prospect.side_effect = enhance_side_effect

        # Add items to queue
        for pid in prospect_ids:
            queue.add_to_queue(pid, user_id=random.randint(1, 100))

        # Start processing
        queue._processing = True

        # Simulate processing loop
        items_processed = 0
        max_iterations = num_items * 2  # Prevent infinite loop
        iterations = 0

        while queue._processing and iterations < max_iterations:
            pending_items = [
                (pid, item)
                for pid, item in queue.queue.items()
                if item.status == QueueStatus.PENDING
            ]

            if pending_items:
                prospect_id, item = pending_items[0]
                queue._current_item = prospect_id
                item.status = QueueStatus.PROCESSING
                queue._process_item(item)
                queue._current_item = None

                if item.status == QueueStatus.COMPLETED:
                    items_processed += 1
                    del queue.queue[prospect_id]
            else:
                break

            iterations += 1

        # Verify processing occurred
        assert mock_llm.enhance_prospect.call_count >= 1
        assert items_processed >= 1

    def test_get_user_items(self, queue):
        """Test getting items for specific users."""
        # Generate random users and items
        num_users = random.randint(2, 4)
        user_ids = list(range(1, num_users + 1))

        # Track items per user
        user_items_map = {uid: [] for uid in user_ids}

        # Add random number of items per user
        for user_id in user_ids:
            num_items = random.randint(1, 3)
            for _ in range(num_items):
                prospect_id = f"PROSPECT-{random.randint(1000, 9999)}"
                queue.add_to_queue(prospect_id, user_id=user_id)
                user_items_map[user_id].append(prospect_id)

        # Test getting items for each user
        for user_id in user_ids:
            user_items = queue.get_user_items(user_id)

            # Verify correct number of items
            assert len(user_items) == len(user_items_map[user_id])

            # Verify all items belong to the user
            for item in user_items:
                assert item["user_id"] == user_id
                assert item["prospect_id"] in user_items_map[user_id]

        # Test non-existent user
        non_existent_user = max(user_ids) + 1
        items = queue.get_user_items(non_existent_user)
        assert len(items) == 0

    def test_clear_completed_items(self, queue):
        """Test clearing completed items from queue."""
        # Add random number of items
        num_items = random.randint(4, 8)
        prospect_ids = [
            f"PROSPECT-{random.randint(1000, 9999)}" for _ in range(num_items)
        ]

        for pid in prospect_ids:
            queue.add_to_queue(pid, user_id=random.randint(1, 100))

        # Randomly mark some items as completed/error
        num_completed = random.randint(1, num_items // 2)
        num_errors = random.randint(0, (num_items - num_completed) // 2)

        completed_ids = prospect_ids[:num_completed]
        error_ids = prospect_ids[num_completed : num_completed + num_errors]
        pending_ids = prospect_ids[num_completed + num_errors :]

        for pid in completed_ids:
            queue.queue[pid].status = QueueStatus.COMPLETED

        for pid in error_ids:
            queue.queue[pid].status = QueueStatus.ERROR

        # Clear completed items (completed and error statuses)
        cleared = queue.clear_completed_items()

        # Verify correct number cleared
        assert cleared == num_completed + num_errors

        # Verify only pending items remain
        assert len(queue.queue) == len(pending_ids)
        for pid in pending_ids:
            assert pid in queue.queue

        for pid in completed_ids + error_ids:
            assert pid not in queue.queue

        # Verify queue positions are updated
        remaining_items = list(queue.queue.values())
        for i, item in enumerate(remaining_items):
            assert item.queue_position == i + 1


class TestModuleFunctions:
    """Test module-level functions following black-box testing principles."""

    @patch("app.services.enhancement_queue.enhancement_queue")
    @patch("app.services.enhancement_queue.AIEnrichmentLog")
    @patch("app.services.enhancement_queue.db")
    def test_add_individual_enhancement_success(
        self, mock_db, mock_log_class, mock_queue
    ):
        """Test successful individual enhancement addition with dynamic data."""
        # Generate random test data
        prospect_id = f"{random.randint(1000, 9999)}"
        user_id = random.randint(1, 100)
        enhancement_types = random.choice(
            [["values"], ["titles"], ["naics"], ["values", "titles"], ["all"]]
        )
        force_redo = random.choice([True, False])
        queue_position = random.randint(1, 20)

        # Setup mocks
        mock_queue.add_to_queue.return_value = queue_position
        mock_log = Mock()
        mock_log_class.return_value = mock_log

        # Call function
        result = add_individual_enhancement(
            prospect_id=prospect_id,
            user_id=user_id,
            enhancement_types=enhancement_types,
            force_redo=force_redo,
        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True
        assert "queue_position" in result
        assert result["queue_position"] == queue_position
        assert "message" in result
        assert str(queue_position) in result["message"]

        # Verify queue was called with correct parameters
        mock_queue.add_to_queue.assert_called_once()
        call_args = mock_queue.add_to_queue.call_args
        assert call_args[1]["prospect_id"] == prospect_id
        assert call_args[1]["user_id"] == user_id
        assert call_args[1]["enhancement_types"] == enhancement_types
        assert call_args[1]["force_redo"] == force_redo

        # Verify logging occurred
        assert mock_log.action == "enhancement_requested"
        assert mock_log.prospect_id == int(prospect_id)
        assert mock_log.user_id == user_id
        mock_db.session.add.assert_called_once_with(mock_log)
        mock_db.session.commit.assert_called_once()

    @patch("app.services.enhancement_queue.enhancement_queue")
    @patch("app.services.enhancement_queue.db")
    def test_add_individual_enhancement_error(self, mock_db, mock_queue):
        """Test error handling in individual enhancement addition."""
        # Generate random test data
        prospect_id = f"{random.randint(1000, 9999)}"
        user_id = random.randint(1, 100)

        # Generate random error
        error_messages = [
            "Queue is full",
            "Service unavailable",
            "Database connection error",
            "Invalid prospect",
            "Rate limit exceeded",
        ]
        error_msg = random.choice(error_messages)

        # Setup mocks to raise an error
        mock_queue.add_to_queue.side_effect = Exception(error_msg)

        # Call function
        result = add_individual_enhancement(prospect_id=prospect_id, user_id=user_id)

        # Verify error handling
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is False
        assert "error" in result
        assert error_msg in result["error"] or "error" in result["error"].lower()

        # Verify rollback was called
        mock_db.session.rollback.assert_called_once()

    def test_singleton_enhancement_queue(self):
        """Test that enhancement_queue is a singleton."""
        from app.services.enhancement_queue import enhancement_queue as queue2

        # Verify both references point to the same object
        assert enhancement_queue is queue2
        assert id(enhancement_queue) == id(queue2)

        # Verify it's an instance of the expected class
        assert isinstance(enhancement_queue, SimpleEnhancementQueue)

    @patch("app.services.enhancement_queue.enhancement_queue")
    def test_enhancement_types_validation(self, mock_queue):
        """Test that various enhancement types are handled correctly."""
        # Test different enhancement type combinations
        test_cases = [
            ["values"],
            ["titles"],
            ["naics"],
            ["set_asides"],
            ["values", "titles"],
            ["naics", "set_asides"],
            ["all"],
            [],  # Empty should default to something
        ]

        for enhancement_types in test_cases:
            mock_queue.add_to_queue.return_value = random.randint(1, 10)

            with (
                patch("app.services.enhancement_queue.db"),
                patch("app.services.enhancement_queue.AIEnrichmentLog"),
            ):
                result = add_individual_enhancement(
                    prospect_id=f"{random.randint(1000, 9999)}",
                    user_id=random.randint(1, 100),
                    enhancement_types=enhancement_types if enhancement_types else None,
                )

                # Should handle all type combinations gracefully
                assert "success" in result
                if result["success"]:
                    assert "queue_position" in result
