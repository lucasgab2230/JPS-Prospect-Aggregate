"""Go/No-Go Decision API endpoints for JPS Prospect Aggregate.

Handles user decisions on prospects for company preferences.
"""

import datetime

UTC = datetime.UTC

from flask import Blueprint, jsonify, request, session
from sqlalchemy import desc, func

from app.api.auth import login_required
from app.database.models import GoNoGoDecision, Prospect, db
from app.utils.logger import logger
from app.utils.user_utils import get_user_by_id, get_user_data_dict, get_users_by_ids

decisions_bp = Blueprint("decisions", __name__, url_prefix="/api/decisions")

# Setup logging
logger = logger.bind(name="api.decisions")


@decisions_bp.route("/", methods=["POST"])
@login_required
def create_decision():
    """Create or update a Go/No-Go decision for a prospect."""
    try:
        data = request.get_json()
        if not data:
            return jsonify(
                {"status": "error", "message": "Request body is required"}
            ), 400

        prospect_id = data.get("prospect_id")
        decision = data.get("decision", "").strip().lower()
        reason_raw = data.get("reason")
        if reason_raw is not None:
            reason = reason_raw.strip() if reason_raw.strip() else None
        else:
            reason = None

        if not prospect_id or not decision:
            return jsonify(
                {"status": "error", "message": "prospect_id and decision are required"}
            ), 400

        if decision not in ["go", "no-go"]:
            return jsonify(
                {
                    "status": "error",
                    "message": 'decision must be either "go" or "no-go"',
                }
            ), 400

        # Verify prospect exists
        prospect = db.session.query(Prospect).filter_by(id=prospect_id).first()
        if not prospect:
            return jsonify({"status": "error", "message": "Prospect not found"}), 404

        user_id = session.get("user_id")

        # Check if decision already exists for this user and prospect
        existing_decision = (
            db.session.query(GoNoGoDecision)
            .filter_by(prospect_id=prospect_id, user_id=user_id)
            .first()
        )

        if existing_decision:
            # Update existing decision
            existing_decision.decision = decision
            existing_decision.reason = reason
            existing_decision.updated_at = datetime.datetime.now(UTC)
            db.session.commit()

            # Get user data for response
            user_data = get_user_data_dict(get_user_by_id(user_id))

            logger.info(
                f"Updated decision for prospect {prospect_id} by user {user_id}: {decision}"
            )

            return jsonify(
                {
                    "status": "success",
                    "data": {
                        "decision": existing_decision.to_dict(
                            include_user=True, user_data=user_data
                        ),
                        "message": "Decision updated successfully",
                    },
                }
            )
        # Create new decision
        new_decision = GoNoGoDecision(
            prospect_id=prospect_id,
            user_id=user_id,
            decision=decision,
            reason=reason,
        )

        db.session.add(new_decision)
        db.session.commit()

        # Get user data for response
        user_data = get_user_data_dict(get_user_by_id(user_id))

        logger.info(
            f"Created decision for prospect {prospect_id} by user {user_id}: {decision}"
        )

        return jsonify(
            {
                "status": "success",
                "data": {
                    "decision": new_decision.to_dict(
                        include_user=True, user_data=user_data
                    ),
                    "message": "Decision created successfully",
                },
            }
        )

    except Exception as e:
        logger.error(f"Error creating/updating decision: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to save decision"}), 500


@decisions_bp.route("/<prospect_id>", methods=["GET"])
@login_required
def get_prospect_decisions(prospect_id):
    """Get all decisions for a specific prospect."""
    try:
        # Verify prospect exists
        prospect = db.session.query(Prospect).filter_by(id=prospect_id).first()
        if not prospect:
            return jsonify({"status": "error", "message": "Prospect not found"}), 404

        # Get all decisions for this prospect
        decisions = (
            db.session.query(GoNoGoDecision)
            .filter_by(prospect_id=prospect_id)
            .order_by(desc(GoNoGoDecision.created_at))
            .all()
        )

        # Get user data for all decisions
        user_ids = [d.user_id for d in decisions]
        users_data = get_users_by_ids(user_ids)

        return jsonify(
            {
                "status": "success",
                "data": {
                    "prospect_id": prospect_id,
                    "decisions": [
                        decision.to_dict(
                            include_user=True,
                            user_data=get_user_data_dict(
                                users_data.get(decision.user_id)
                            ),
                        )
                        for decision in decisions
                    ],
                    "total_decisions": len(decisions),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting prospect decisions: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to get decisions"}), 500


@decisions_bp.route("/user/<int:user_id>", methods=["GET"])
@login_required
def get_user_decisions(user_id):
    """Get all decisions by a specific user."""
    try:
        # Only allow users to see their own decisions or all if admin
        current_user_id = session.get("user_id")
        if current_user_id != user_id:
            # For now, allow any authenticated user to see any user's decisions
            # In the future, you might want to add admin roles
            pass

        # Get pagination parameters
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 50, type=int), 100)

        # Get user decisions
        decisions_query = (
            db.session.query(GoNoGoDecision)
            .filter_by(user_id=user_id)
            .order_by(desc(GoNoGoDecision.created_at))
        )

        total = decisions_query.count()
        decisions = decisions_query.offset((page - 1) * per_page).limit(per_page).all()

        return jsonify(
            {
                "status": "success",
                "data": {
                    "user_id": user_id,
                    "decisions": [decision.to_dict() for decision in decisions],
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total,
                        "pages": (total + per_page - 1) // per_page,
                    },
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting user decisions: {str(e)}", exc_info=True)
        return jsonify(
            {"status": "error", "message": "Failed to get user decisions"}
        ), 500


@decisions_bp.route("/my", methods=["GET"])
@login_required
def get_my_decisions():
    """Get current user's decisions."""
    try:
        user_id = session.get("user_id")

        # Get pagination parameters
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 50, type=int), 100)

        # Get current user's decisions
        decisions_query = (
            db.session.query(GoNoGoDecision)
            .filter_by(user_id=user_id)
            .order_by(desc(GoNoGoDecision.created_at))
        )

        total = decisions_query.count()
        decisions = decisions_query.offset((page - 1) * per_page).limit(per_page).all()

        return jsonify(
            {
                "status": "success",
                "data": {
                    "decisions": [decision.to_dict() for decision in decisions],
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total,
                        "pages": (total + per_page - 1) // per_page,
                    },
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting my decisions: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": "Failed to get decisions"}), 500


@decisions_bp.route("/stats", methods=["GET"])
@login_required
def get_decision_stats():
    """Get decision statistics."""
    try:
        user_id = session.get("user_id")

        # Get overall stats
        total_decisions = (
            db.session.query(func.count(GoNoGoDecision.id))
            .filter_by(user_id=user_id)
            .scalar()
        )

        go_decisions = (
            db.session.query(func.count(GoNoGoDecision.id))
            .filter_by(user_id=user_id, decision="go")
            .scalar()
        )

        nogo_decisions = (
            db.session.query(func.count(GoNoGoDecision.id))
            .filter_by(user_id=user_id, decision="no-go")
            .scalar()
        )

        # Get recent activity (last 30 days)
        thirty_days_ago = datetime.datetime.now(UTC) - datetime.timedelta(days=30)
        recent_decisions = (
            db.session.query(func.count(GoNoGoDecision.id))
            .filter(
                GoNoGoDecision.user_id == user_id,
                GoNoGoDecision.created_at >= thirty_days_ago,
            )
            .scalar()
        )

        return jsonify(
            {
                "status": "success",
                "data": {
                    "total_decisions": total_decisions,
                    "go_decisions": go_decisions,
                    "nogo_decisions": nogo_decisions,
                    "recent_decisions_30d": recent_decisions,
                    "go_percentage": round((go_decisions / total_decisions) * 100, 1)
                    if total_decisions > 0
                    else 0,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error getting decision stats: {str(e)}", exc_info=True)
        return jsonify(
            {"status": "error", "message": "Failed to get decision statistics"}
        ), 500


@decisions_bp.route("/<int:decision_id>", methods=["DELETE"])
@login_required
def delete_decision(decision_id):
    """Delete a decision (only by the user who created it)."""
    try:
        user_id = session.get("user_id")

        # Find the decision
        decision = (
            db.session.query(GoNoGoDecision)
            .filter_by(id=decision_id, user_id=user_id)
            .first()
        )

        if not decision:
            return jsonify(
                {
                    "status": "error",
                    "message": "Decision not found or not authorized to delete",
                }
            ), 404

        db.session.delete(decision)
        db.session.commit()

        logger.info(f"Deleted decision {decision_id} by user {user_id}")

        return jsonify(
            {"status": "success", "message": "Decision deleted successfully"}
        )

    except Exception as e:
        logger.error(f"Error deleting decision: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to delete decision"}), 500
