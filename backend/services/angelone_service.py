"""
Angel One SmartAPI Service

Provides authentication and API client functionality for Angel One SmartAPI.

Features:
- Login with client ID, password, and TOTP
- Token management (JWT, refresh, feed)
- Profile retrieval
- Session validation

Author: Quantitative Trading Systems Engineer
Date: April 7, 2026
"""

import os
import logging
from typing import Optional, Dict, Any

try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None

from services.token_manager import TokenManager

logger = logging.getLogger(__name__)


class AngelOneService:
    """
    Angel One SmartAPI authentication and API service.

    Usage:
        service = AngelOneService()
        success = service.login(client_id, password, totp)
        profile = service.get_profile()
    """

    def __init__(self):
        """Initialize with API key, MPIN, and TOTP config from environment."""
        self.api_key = os.getenv("ANGEL_ONE_API_KEY", "LFHr3Azz")
        self.client: Optional[SmartConnect] = None
        self.jwt_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.feed_token: Optional[str] = None
        self.user_profile: Optional[Dict[str, Any]] = None
        self.is_authenticated = False

        # Use MPIN for SmartAPI password authentication.
        self.mpin = os.getenv("ANGEL_ONE_MPIN") or os.getenv("ANGEL_ONE_PASSWORD")
        self.totp_seed = os.getenv("ANGEL_ONE_TOTP_SEED")
        self.token_manager = TokenManager(
            api_key=self.api_key,
            client_id=os.getenv("ANGEL_ONE_CLIENT_ID"),
            mpin=self.mpin,
            totp_seed=self.totp_seed,
        )

        logger.info(f"AngelOneService initialized with API key: {self.api_key[:8]}...")

    def login(self, client_code: str, password: str, totp: str) -> Dict[str, Any]:
        """
        Login to Angel One with credentials.

        Args:
            client_code: Angel One client ID
            password: Account password
            totp: Current TOTP code

        Returns:
            Dict with status, message, and tokens
        """
        if not SmartConnect:
            return {
                "status": "error",
                "message": "SmartApi package not installed",
                "success": False,
            }

        result = self.token_manager.login(
            client_code=client_code, password=password, totp=totp, retries=1
        )

        if result.get("success"):
            self.is_authenticated = True
            self.client = self.get_authenticated_client()
            self.jwt_token = self.token_manager.jwt_token
            self.refresh_token = self.token_manager.refresh_token
            self.feed_token = self.token_manager.feed_token

        return result

    def auto_login(self, retries: int = 3) -> Dict[str, Any]:
        """
        Auto-login using environment credentials and retry logic.

        The correct flow uses client_id + MPIN and OTP/TOTP.

        Returns:
            Dict with login status
        """
        result = self.token_manager.login(retries=retries)

        if result.get("success"):
            self.is_authenticated = True
            self.client = self.get_authenticated_client()
            self.jwt_token = self.token_manager.jwt_token
            self.refresh_token = self.token_manager.refresh_token
            self.feed_token = self.token_manager.feed_token

        return result

    def get_valid_token(self) -> str:
        """Return a valid JWT token, refreshing or logging in automatically if needed."""
        token = self.token_manager.get_valid_token()
        self.is_authenticated = True
        self.jwt_token = token
        self.refresh_token = self.token_manager.refresh_token
        self.feed_token = self.token_manager.feed_token
        return token

    def get_authenticated_client(self) -> SmartConnect:
        """Return a SmartConnect client with a valid access token attached."""
        if not SmartConnect:
            raise RuntimeError("SmartApi package not installed")

        token = self.get_valid_token()
        client = SmartConnect(api_key=self.api_key)
        client.setAccessToken(token)
        return client

    def get_token_state(self) -> Dict[str, Any]:
        return self.token_manager.get_token_state()

    def get_profile(self) -> Dict[str, Any]:
        """
        Get user profile information.

        Returns:
            Dict with user profile data
        """
        if not self.token_manager.is_authenticated():
            return {"status": "error", "message": "Not authenticated", "success": False}

        try:
            client = self.get_authenticated_client()
            profile = client.getProfile(self.refresh_token)

            if profile and profile.get("status"):
                self.user_profile = profile["data"]
                return {
                    "status": "success",
                    "message": "Profile retrieved",
                    "success": True,
                    "data": self.user_profile,
                }
            else:
                return {
                    "status": "error",
                    "message": profile.get("message", "Failed to get profile"),
                    "success": False,
                }

        except Exception as e:
            logger.error(f"Get profile error: {str(e)}")
            return {"status": "error", "message": str(e), "success": False}

    def is_valid_session(self) -> bool:
        """
        Check if current session is valid.

        Returns:
            True if session is valid
        """
        return self.token_manager.is_authenticated()

    def logout(self) -> Dict[str, Any]:
        """
        Logout and clear session.

        Returns:
            Dict with logout status
        """
        self.client = None
        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None
        self.user_profile = None
        self.is_authenticated = False
        self.token_manager.clear_tokens()

        logger.info("Logged out successfully")

        return {"status": "success", "message": "Logged out", "success": True}

    def get_status(self) -> Dict[str, Any]:
        """
        Get current service status.

        Returns:
            Dict with connection status
        """
        token_state = self.token_manager.get_token_state()
        return {
            "authenticated": token_state["is_authenticated"],
            "api_key_set": bool(self.api_key),
            "client_id": os.getenv("ANGEL_ONE_CLIENT_ID"),
            "user_profile": self.user_profile,
            "expires_at": token_state["expires_at"],
        }


def login() -> Dict[str, str]:
    """Perform Angel One login and return session tokens.

    Returns:
        dict: {"jwt_token", "refresh_token", "feed_token"}

    Raises:
        RuntimeError: If authentication fails after retries.
    """
    service = get_angel_one_service()
    result = service.auto_login(retries=3)

    if not result.get("success"):
        raise RuntimeError(result.get("message", "Angel One login failed"))

    tokens = service.token_manager.get_token_state()
    if not tokens.get("jwt_token"):
        raise RuntimeError("Angel One login succeeded but no JWT token is available")

    return {
        "jwt_token": tokens["jwt_token"],
        "refresh_token": tokens["refresh_token"],
        "feed_token": tokens["feed_token"],
    }


# Global singleton instance
_angel_one_service: Optional[AngelOneService] = None


def get_angel_one_service() -> AngelOneService:
    """Get or create AngelOneService singleton."""
    global _angel_one_service
    if _angel_one_service is None:
        _angel_one_service = AngelOneService()
    return _angel_one_service
