"""Maintenance Mode Middleware

This middleware checks if the application is in maintenance mode and serves
a maintenance page to all users except for the admin toggle endpoint.
"""

from flask import make_response, request

from app.database import db
from app.database.models import Settings


def get_maintenance_status():
    """Get the current maintenance mode status from the database."""
    try:
        setting = db.session.query(Settings).filter_by(key="maintenance_mode").first()
        if setting:
            return setting.value.lower() == "true"
        return False
    except Exception:
        # If database is not available or error occurs, default to not in maintenance
        return False


def maintenance_middleware(app):
    """Register maintenance mode middleware with the Flask app.

    This middleware will intercept all requests and serve a maintenance page
    if maintenance mode is enabled, except for the admin toggle endpoint.
    """

    @app.before_request
    def check_maintenance_mode():
        # Skip maintenance check for all admin endpoints
        if request.endpoint and request.endpoint.startswith("admin."):
            return None

        # Skip maintenance check for static files
        if request.endpoint == "static":
            return None

        # Check if we're in maintenance mode
        if get_maintenance_status():
            return make_maintenance_response()

        return None


def make_maintenance_response():
    """Create the maintenance mode response."""
    maintenance_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Down for Maintenance</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background-color: #f8f9fa;
                color: #333;
                text-align: center;
                padding: 50px 20px;
                margin: 0;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #dc3545;
                margin-bottom: 20px;
            }
            p {
                font-size: 18px;
                line-height: 1.6;
                margin-bottom: 15px;
            }
            .icon {
                font-size: 48px;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">🔧</div>
            <h1>Down for Maintenance</h1>
            <p>We're currently performing scheduled maintenance to improve your experience.</p>
            <p>We'll be back online shortly. Thank you for your patience!</p>
            <p><strong>If you're an administrator</strong>, you can toggle maintenance mode via the API endpoint.</p>
        </div>
    </body>
    </html>
    """

    response = make_response(maintenance_html, 503)
    response.headers["Content-Type"] = "text/html"
    response.headers["Retry-After"] = "3600"  # Suggest retry after 1 hour
    return response
