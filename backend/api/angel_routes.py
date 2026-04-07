"""
Angel One API Routes

Flask endpoints for Angel One SmartAPI authentication.

Endpoints:
- POST /api/angel/login - Login with credentials
- GET /api/angel/profile - Get user profile
- GET /api/angel/status - Get connection status
- POST /api/angel/logout - Logout
- POST /api/angel/auto-login - Auto-login with env credentials

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

from flask import Blueprint, jsonify, request
import logging

logger = logging.getLogger(__name__)

angel_bp = Blueprint("angel", __name__, url_prefix="/api/angel")


def get_service():
    """Get Angel One service singleton."""
    from backend.services.angelone_service import get_angel_one_service

    return get_angel_one_service()


@angel_bp.route("/login", methods=["POST"])
def angel_login():
    """
    Login to Angel One with credentials.

    Request Body:
        {
            "client_code": "...",
            "password": "...",
            "totp": "..."
        }

    Returns:
        JSON with login status and tokens
    """
    try:
        data = request.get_json() or {}
        client_code = data.get("client_code")
        password = data.get("password")
        totp = data.get("totp")

        if not all([client_code, password, totp]):
            return jsonify(
                {
                    "status": "error",
                    "message": "Missing required fields: client_code, password, totp",
                    "success": False,
                }
            ), 400

        service = get_service()
        result = service.login(client_code, password, totp)

        if result.get("success"):
            return jsonify(
                {
                    "status": "success",
                    "message": "Login successful",
                    "data": {
                        "jwt_token": result["data"].get("jwt_token"),
                        "feed_token": result["data"].get("feed_token"),
                    },
                }
            ), 200
        else:
            return jsonify(
                {
                    "status": "error",
                    "message": result.get("message", "Login failed"),
                    "success": False,
                }
            ), 401

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({"status": "error", "message": str(e), "success": False}), 500


@angel_bp.route("/auto-login", methods=["POST"])
def angel_auto_login():
    """
    Auto-login using environment credentials.

    Uses ANGEL_ONE_CLIENT_ID and ANGEL_ONE_TOTP_SEED from .env

    Returns:
        JSON with login status
    """
    try:
        service = get_service()
        result = service.auto_login()

        if result.get("success"):
            return jsonify(
                {
                    "status": "success",
                    "message": "Auto-login successful",
                    "data": {
                        "jwt_token": result["data"].get("jwt_token"),
                        "feed_token": result["data"].get("feed_token"),
                    },
                }
            ), 200
        else:
            return jsonify(
                {
                    "status": "error",
                    "message": result.get("message", "Auto-login failed"),
                    "success": False,
                }
            ), 401

    except Exception as e:
        logger.error(f"Auto-login error: {str(e)}")
        return jsonify({"status": "error", "message": str(e), "success": False}), 500


@angel_bp.route("/profile", methods=["GET"])
def angel_profile():
    """
    Get user profile from Angel One.

    Returns:
        JSON with user profile data
    """
    try:
        service = get_service()

        if not service.is_authenticated:
            return jsonify(
                {"status": "error", "message": "Not authenticated", "success": False}
            ), 401

        result = service.get_profile()

        if result.get("success"):
            return jsonify(
                {
                    "status": "success",
                    "message": "Profile retrieved",
                    "data": result["data"],
                }
            ), 200
        else:
            return jsonify(
                {
                    "status": "error",
                    "message": result.get("message", "Failed to get profile"),
                    "success": False,
                }
            ), 400

    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return jsonify({"status": "error", "message": str(e), "success": False}), 500


@angel_bp.route("/status", methods=["GET"])
def angel_status():
    """
    Get Angel One connection status.

    Returns:
        JSON with connection status
    """
    try:
        service = get_service()
        status = service.get_status()

        return jsonify(
            {
                "status": "success",
                "data": {
                    "authenticated": status.get("authenticated", False),
                    "api_key_set": status.get("api_key_set", False),
                    "client_id": status.get("client_id"),
                    "user_name": status.get("user_profile", {}).get("name")
                    if status.get("user_profile")
                    else None,
                },
            }
        ), 200

    except Exception as e:
        logger.error(f"Status error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@angel_bp.route("/logout", methods=["POST"])
def angel_logout():
    """
    Logout from Angel One.

    Returns:
        JSON with logout status
    """
    try:
        service = get_service()
        result = service.logout()

        return jsonify({"status": "success", "message": "Logged out successfully"}), 200

    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
