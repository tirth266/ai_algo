from flask import Blueprint, request
from pydantic import BaseModel
import os
import pyotp
import logging

from backend.flask_compat import ApiError

try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


class SessionManager:
    def __init__(self):
        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None
        self.api_key = os.getenv("ANGEL_ONE_API_KEY")

    def set_tokens(self, jwt_token, refresh_token, feed_token):
        self.jwt_token = jwt_token
        self.refresh_token = refresh_token
        self.feed_token = feed_token

    def is_authenticated(self):
        return self.jwt_token is not None


global_session_manager = SessionManager()


def get_smart_client():
    if not SmartConnect:
        raise ApiError(500, "SmartApi package not found")

    api_key = global_session_manager.api_key or os.getenv("ANGEL_ONE_API_KEY")

    if not api_key or not global_session_manager.is_authenticated():
        raise ApiError(401, "Not authenticated. Please login first.")

    client = SmartConnect(api_key=api_key)

    # We assign the token to the client. This mirrors how the underlying SmartApi Python SDK checks access_token headers
    client.access_token = global_session_manager.jwt_token

    return client


@auth_bp.route("/login", methods=["POST"])
def login_angel_one():
    api_key = os.getenv("ANGEL_ONE_API_KEY")
    client_id = os.getenv("ANGEL_ONE_CLIENT_ID")
    totp_seed = os.getenv("ANGEL_ONE_TOTP_SEED")

    if not all([api_key, client_id, totp_seed]):
        raise ApiError(500, "Missing required environment variables for Angel One")

    try:
        obj = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_seed).now()
        data = obj.generateSession(client_id, client_id, totp)

        if data.get("status"):
            feed_token = obj.getfeedToken()
            jwt_token = data["data"]["jwtToken"]
            refresh_token = data["data"]["refreshToken"]
            global_session_manager.set_tokens(jwt_token, refresh_token, feed_token)
            return {
                "status": "Success",
                "message": "Angel One session generated successfully",
            }
        else:
            raise ApiError(
                400,
                f"Login failed: {data.get('message', 'Unknown Error')}",
            )
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise ApiError(500, str(e))


class VerifyCallbackRequest(BaseModel):
    auth_token: str


@auth_bp.route("/verify-callback", methods=["POST"])
def verify_callback():
    try:
        data = request.get_json(silent=True) or {}
        req = VerifyCallbackRequest(**data)
    except Exception as exc:
        raise ApiError(400, str(exc))

    global_session_manager.set_tokens(req.auth_token, None, None)
    return {
        "status": "Success",
        "message": "Callback verified and session instantiated",
    }
