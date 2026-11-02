"""Authentication API endpoints for JPS Prospect Aggregate.

Provides simple email-based authentication without passwords.
"""

import datetime

UTC = datetime.UTC
from functools import wraps

from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from app.database import db
from app.database.user_models import User
from app.utils.logger import logger

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Setup logging
logger = logger.bind(name="api.auth")

# Add session debugging in production
import os

if os.getenv("ENVIRONMENT") == "production":

    @auth_bp.before_request
    def log_session_before():
        """Debug session issues in production."""
        logger.debug(f"Session before request to {request.endpoint}: {dict(session)}")
        logger.debug(
            f"Session cookie: {request.cookies.get('session', 'none')[:50] if request.cookies.get('session') else 'none'}..."
        )

    @auth_bp.after_request
    def log_session_after(response):
        """Debug session issues in production."""
        logger.debug(f"Session after request to {request.endpoint}: {dict(session)}")
        return response


def login_required(f):
    """Decorator to require login for endpoints."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(
                {"status": "error", "message": "Authentication required"}
            ), 401
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """Decorator to require admin role for endpoints."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(
                {"status": "error", "message": "Authentication required"}
            ), 401

        user_role = session.get("user_role", "user")
        if user_role not in ["admin", "super_admin"]:
            return jsonify({"status": "error", "message": "Admin access required"}), 403

        return f(*args, **kwargs)

    return decorated_function


def super_admin_required(f):
    """Decorator to require super_admin role for endpoints."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(
                {"status": "error", "message": "Authentication required"}
            ), 401

        user_role = session.get("user_role", "user")
        if user_role != "super_admin":
            return jsonify(
                {"status": "error", "message": "Super admin access required"}
            ), 403

        return f(*args, **kwargs)

    return decorated_function


@auth_bp.route("/signup", methods=["POST"])
def signup():
    """Create a new user account with email and first name only."""
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"status": "error", "message": "Request body is required"}
            ), 400

        email = data.get("email", "").strip().lower()
        first_name = data.get("first_name", "").strip()

        if not email or not first_name:
            return jsonify(
                {"status": "error", "message": "Email and first name are required"}
            ), 400

        # Validate email format (basic validation)
        if "@" not in email or "." not in email:
            return jsonify({"status": "error", "message": "Invalid email format"}), 400

        # Check if user already exists
        existing_user = db.session.query(User).filter_by(email=email).first()
        if existing_user:
            return jsonify(
                {"status": "error", "message": "User with this email already exists"}
            ), 409

        # Create new user
        user = User(email=email, first_name=first_name)

        db.session.add(user)
        db.session.commit()

        # Log user in
        session["user_id"] = user.id
        session["user_email"] = user.email
        session["user_first_name"] = user.first_name
        session["user_role"] = user.role

        logger.info(f"New user signed up: {email}")

        return jsonify(
            {
                "status": "success",
                "data": {
                    "user": user.to_dict(),
                    "message": "Account created successfully",
                },
            }
        )

    except IntegrityError:
        db.session.rollback()
        return jsonify(
            {"status": "error", "message": "User with this email already exists"}
        ), 409
    except Exception as e:
        logger.error(f"Error in signup: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to create account"}), 500


@auth_bp.route("/signin", methods=["POST"])
def signin():
    """Sign in user with email only."""
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"status": "error", "message": "Request body is required"}
            ), 400

        email = data.get("email", "").strip().lower()

        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        # Find user by email
        user = db.session.query(User).filter_by(email=email).first()
        if not user:
            return jsonify(
                {
                    "status": "error",
                    "message": "No account found with this email address",
                }
            ), 404

        # Update last login
        user.last_login_at = datetime.datetime.now(UTC)
        db.session.commit()

        # Log user in
        session["user_id"] = user.id
        session["user_email"] = user.email
        session["user_first_name"] = user.first_name
        session["user_role"] = user.role

        logger.info(f"User signed in: {email}")

        return jsonify(
            {
                "status": "success",
                "data": {"user": user.to_dict(), "message": "Signed in successfully"},
            }
        )

    except Exception as e:
        logger.error(f"Error in signin: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to sign in"}), 500


@auth_bp.route("/signout", methods=["POST"])
def signout():
    """Sign out current user."""
    try:
        if "user_id" in session:
            logger.info(f"User signed out: {session.get('user_email')}")

        session.clear()

        return jsonify({"status": "success", "message": "Signed out successfully"})

    except Exception as e:
        logger.error(f"Error in signout: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to sign out"}), 500


@auth_bp.route("/me", methods=["GET"])
@login_required
def get_current_user():
    """Get current authenticated user information."""
    try:
        user_id = session.get("user_id")
        user = db.session.query(User).filter_by(id=user_id).first()

        if not user:
            session.clear()
            return jsonify({"status": "error", "message": "User not found"}), 404

        # Sync session data with current database state
        session["user_role"] = user.role
        session["user_email"] = user.email
        session["user_first_name"] = user.first_name

        return jsonify({"status": "success", "data": {"user": user.to_dict()}})

    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}", exc_info=True)
        return jsonify(
            {"status": "error", "message": "Failed to get user information"}
        ), 500


@auth_bp.route("/status", methods=["GET"])
def get_auth_status():
    """Check if user is currently authenticated."""
    try:
        if "user_id" in session:
            user_id = session.get("user_id")
            user = db.session.query(User).filter_by(id=user_id).first()

            if user:
                # Sync session data with current database state
                session["user_role"] = user.role
                session["user_email"] = user.email
                session["user_first_name"] = user.first_name

                return jsonify(
                    {
                        "status": "success",
                        "data": {"authenticated": True, "user": user.to_dict()},
                    }
                )
            # Clear invalid session
            session.clear()

        return jsonify(
            {"status": "success", "data": {"authenticated": False, "user": None}}
        )

    except Exception as e:
        logger.error(f"Error checking auth status: {str(e)}", exc_info=True)
        return jsonify(
            {"status": "error", "message": "Failed to check authentication status"}
        ), 500


@auth_bp.route("/debug-session", methods=["GET"])
@login_required
def debug_session():
    """Debug endpoint to check current session state (admin only in production)."""
    try:
        # Only allow in development or for admins
        user_role = session.get("user_role", "user")
        if user_role != "admin":
            return jsonify({"status": "error", "message": "Admin access required"}), 403

        return jsonify(
            {
                "status": "success",
                "data": {
                    "session": {
                        "user_id": session.get("user_id"),
                        "user_email": session.get("user_email"),
                        "user_first_name": session.get("user_first_name"),
                        "user_role": session.get("user_role"),
                    }
                },
            }
        )
    except Exception as e:
        logger.error(f"Error in debug session: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to debug session"}), 500
