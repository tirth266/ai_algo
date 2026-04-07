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
        """Initialize with API key from environment."""
        self.api_key = os.getenv("ANGEL_ONE_API_KEY", "LFHr3Azz")
        self.client: Optional[SmartConnect] = None
        self.jwt_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.feed_token: Optional[str] = None
        self.user_profile: Optional[Dict[str, Any]] = None
        self.is_authenticated = False

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

        try:
            self.client = SmartConnect(api_key=self.api_key)

            data = self.client.generateSession(client_code, password, totp)

            if data and data.get("status"):
                self.jwt_token = data["data"]["jwtToken"]
                self.refresh_token = data["data"]["refreshToken"]
                self.feed_token = self.client.getfeedToken()
                self.is_authenticated = True

                logger.info(f"Login successful for client: {client_code}")

                return {
                    "status": "success",
                    "message": "Login successful",
                    "success": True,
                    "data": {
                        "jwt_token": self.jwt_token,
                        "refresh_token": self.refresh_token,
                        "feed_token": self.feed_token,
                    },
                }
            else:
                error_msg = (
                    data.get("message", "Unknown error") if data else "No response"
                )
                logger.warning(f"Login failed: {error_msg}")

                return {"status": "error", "message": error_msg, "success": False}

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return {"status": "error", "message": str(e), "success": False}

    def auto_login(self) -> Dict[str, Any]:
        """
        Auto-login using environment credentials (client_id + TOTP seed).

        Uses client_id as password (standard for TOTP setups).

        Returns:
            Dict with login status
        """
        client_id = os.getenv("ANGEL_ONE_CLIENT_ID")
        totp_seed = os.getenv("ANGEL_ONE_TOTP_SEED")

        if not client_id or not totp_seed:
            return {
                "status": "error",
                "message": "Missing ANGEL_ONE_CLIENT_ID or ANGEL_ONE_TOTP_SEED",
                "success": False,
            }

        try:
            import pyotp

            totp = pyotp.TOTP(totp_seed).now()

            return self.login(client_id, client_id, totp)

        except Exception as e:
            logger.error(f"Auto-login error: {str(e)}")
            return {"status": "error", "message": str(e), "success": False}

    def get_profile(self) -> Dict[str, Any]:
        """
        Get user profile information.

        Returns:
            Dict with user profile data
        """
        if not self.is_authenticated or not self.refresh_token:
            return {"status": "error", "message": "Not authenticated", "success": False}

        try:
            profile = self.client.getProfile(self.refresh_token)

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
        if not self.is_authenticated:
            return False

        try:
            profile = self.get_profile()
            return profile.get("success", False)
        except Exception:
            return False

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

        logger.info("Logged out successfully")

        return {"status": "success", "message": "Logged out", "success": True}

    def get_status(self) -> Dict[str, Any]:
        """
        Get current service status.

        Returns:
            Dict with connection status
        """
        return {
            "authenticated": self.is_authenticated,
            "api_key_set": bool(self.api_key),
            "client_id": os.getenv("ANGEL_ONE_CLIENT_ID"),
            "user_profile": self.user_profile,
        }


# Global singleton instance
_angel_one_service: Optional[AngelOneService] = None


def get_angel_one_service() -> AngelOneService:
    """Get or create AngelOneService singleton."""
    global _angel_one_service
    if _angel_one_service is None:
        _angel_one_service = AngelOneService()
    return _angel_one_service
