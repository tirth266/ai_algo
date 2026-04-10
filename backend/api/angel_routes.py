"""Angel One API routes implemented with Flask Blueprints."""

import logging
import os

from flask import Blueprint, jsonify, request

from backend.flask_compat import ApiError
from backend.services.angelone_service import get_angel_one_service

logger = logging.getLogger(__name__)

angel_bp = Blueprint("angel", __name__, url_prefix="/api/angel")


def get_service():
    return get_angel_one_service()


@angel_bp.route("/login", methods=["POST"])
def angel_login():
    try:
        data = request.get_json(silent=True) or {}
        totp = data.get("totp")
        if not totp:
            raise ApiError(400, "Missing required field: totp")

        service = get_service()
        client_code = os.getenv("ANGEL_ONE_CLIENT_ID")
        password = os.getenv("ANGEL_ONE_PASSWORD")

        if not client_code or not password:
            raise ApiError(500, "Server configuration missing. Contact admin.")

        result = service.login(client_code, password, totp)
        if result.get("success"):
            return jsonify(
                {
                    "status": "success",
                    "message": "Login successful",
                    "data": {"connected": True},
                }
            )

        raise ApiError(401, result.get("message", "Login failed"))
    except ApiError:
        raise
    except Exception as exc:
        logger.error(f"Login error: {exc}")
        raise ApiError(500, str(exc))


@angel_bp.route("/auto-login", methods=["POST"])
def angel_auto_login():
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
            )

        raise ApiError(401, result.get("message", "Auto-login failed"))
    except ApiError:
        raise
    except Exception as exc:
        logger.error(f"Auto-login error: {exc}")
        raise ApiError(500, str(exc))


@angel_bp.route("/profile", methods=["GET"])
def angel_profile():
    try:
        service = get_service()
        if not service.is_authenticated:
            raise ApiError(401, "Not authenticated")

        result = service.get_profile()
        if result.get("success"):
            return jsonify(
                {
                    "status": "success",
                    "message": "Profile retrieved",
                    "data": result["data"],
                }
            )

        raise ApiError(400, result.get("message", "Failed to get profile"))
    except ApiError:
        raise
    except Exception as exc:
        logger.error(f"Profile error: {exc}")
        raise ApiError(500, str(exc))


@angel_bp.route("/status", methods=["GET"])
def angel_status():
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
        )
    except Exception as exc:
        logger.error(f"Status error: {exc}")
        raise ApiError(500, str(exc))


@angel_bp.route("/logout", methods=["POST"])
def angel_logout():
    try:
        service = get_service()
        service.logout()
        return jsonify({"status": "success", "message": "Logged out successfully"})
    except Exception as exc:
        logger.error(f"Logout error: {exc}")
        raise ApiError(500, str(exc))
