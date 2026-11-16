"""
Pytest configuration and shared fixtures.
"""

import pytest

from app import create_app
from app.database import db as _db


@pytest.fixture(scope="session")
def app(request):
    """Session-wide test Flask application."""
    # create_app will use active_config.
    # For tests, FLASK_ENV should be 'testing' so active_config is TestingConfig.
    flask_app = create_app()

    # Establish an application context before running the tests.
    ctx = flask_app.app_context()
    ctx.push()

    def teardown():
        ctx.pop()

    request.addfinalizer(teardown)
    return flask_app


@pytest.fixture(scope="session")
def db(app, request):
    """Session-wide test database. Creates all tables."""

    def teardown():
        _db.drop_all()

    # _db.app = app # This is done by Flask-SQLAlchemy's init_app
    with app.app_context():  # Ensure operations are within app context
        _db.create_all()

    request.addfinalizer(teardown)
    return _db


@pytest.fixture(scope="function")
def db_session(db):  # Depends on the session-scoped db fixture
    """
    Provides a SQLAlchemy session for a test, ensuring test isolation
    by using a nested transaction that's rolled back.
    """
    # The db fixture ensures that the database tables are created.
    # _db.session is the session managed by Flask-SQLAlchemy, typically a scoped session.

    # Start a nested transaction (uses SAVEPOINT)
    nested = _db.session.begin_nested()

    # Yield the session to the test
    yield _db.session

    # Rollback the nested transaction after the test
    nested.rollback()

    # The main session used by Flask-SQLAlchemy is typically managed per request or per thread.
    # For tests, simple rollback of the nested transaction is often sufficient.
    # If full session cleanup beyond rollback is needed (e.g., expunge all), it can be added here.
    # However, Flask-SQLAlchemy's scoped session usually handles this.
    # For extra safety, ensure session is clean, though rollback should handle it.
    # _db.session.remove() # This might be too aggressive if session scope is broader than function.


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()
