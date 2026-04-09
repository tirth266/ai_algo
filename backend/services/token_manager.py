import base64
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None

logger = logging.getLogger(__name__)


class TokenManager:
    """Manage Angel One SmartAPI token lifecycle.

    This class centralizes login, refresh, expiry tracking, and token access.
    It guarantees that the system never operates with an expired JWT.
    """

    def __init__(
        self,
        api_key: str,
        client_id: str,
        mpin: Optional[str],
        totp_seed: Optional[str],
        refresh_threshold_minutes: int = 10,
    ):
        self.api_key = api_key
        self.client_id = client_id
        self.mpin = mpin
        self.totp_seed = totp_seed
        self.refresh_threshold = timedelta(minutes=refresh_threshold_minutes)

        self.jwt_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.feed_token: Optional[str] = None
        self.issued_at: Optional[datetime] = None
        self.expires_at: Optional[datetime] = None
        self._secure_tokens: Dict[str, str] = {}

    def _create_client(self):
        if not SmartConnect:
            raise RuntimeError("SmartApi package not installed")

        return SmartConnect(api_key=self.api_key)

    def _parse_jwt_expiry(self, token: str) -> Optional[datetime]:
        try:
            payload = token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
            claims = json.loads(decoded)
            exp = claims.get("exp")
            if exp:
                return datetime.fromtimestamp(int(exp))
        except Exception:
            return None
        return None

    def _build_expiry(self, token: str) -> datetime:
        expiry = self._parse_jwt_expiry(token)
        if expiry:
            return expiry
        return datetime.now() + timedelta(hours=24)

    def _get_otp_code(self) -> str:
        if self.totp_seed:
            try:
                import pyotp

                return pyotp.TOTP(self.totp_seed).now()
            except Exception as e:
                raise RuntimeError(f"Failed to generate TOTP: {e}")

        otp_code = os.getenv("ANGEL_ONE_OTP") or os.getenv("ANGEL_ONE_OTP_CODE")
        if not otp_code:
            raise RuntimeError(
                "Missing ANGEL_ONE_TOTP_SEED or ANGEL_ONE_OTP / ANGEL_ONE_OTP_CODE"
            )
        return otp_code

    def _get_mpin(self) -> str:
        if not self.mpin:
            raise RuntimeError("Missing ANGEL_ONE_MPIN or ANGEL_ONE_PASSWORD environment variable")
        return self.mpin

    def _store_tokens(
        self,
        jwt_token: str,
        refresh_token: Optional[str],
        feed_token: Optional[str],
    ) -> None:
        self.jwt_token = jwt_token
        self.refresh_token = refresh_token
        self.feed_token = feed_token
        self.issued_at = datetime.now()
        self.expires_at = self._build_expiry(jwt_token)
        self._secure_tokens = {
            "jwt_token": jwt_token,
            "refresh_token": refresh_token or "",
            "feed_token": feed_token or "",
        }

        logger.info(
            "Angel One token state updated: expires_at=%s",
            self.expires_at.isoformat() if self.expires_at else "unknown",
        )

    def _is_expired(self) -> bool:
        if not self.expires_at:
            return True
        return datetime.now() >= self.expires_at

    def _is_near_expiry(self) -> bool:
        if not self.expires_at:
            return True
        return self.expires_at - datetime.now() <= self.refresh_threshold

    def _choose_refresh_method(self, client: Any):
        candidates = [
            "refreshToken",
            "refresh_session",
            "refreshSession",
            "renewToken",
            "renew_session",
            "renewSession",
        ]
        for method_name in candidates:
            if hasattr(client, method_name):
                return getattr(client, method_name)
        return None

    def _refresh_with_client(self, client: Any) -> Dict[str, Any]:
        refresh_method = self._choose_refresh_method(client)
        if refresh_method is None:
            raise RuntimeError("SmartApi client does not support token refresh")

        try:
            try:
                return refresh_method(self.refresh_token)
            except TypeError:
                return refresh_method()
        except Exception as exc:
            raise RuntimeError(f"Refresh token call failed: {exc}")

    def _extract_tokens(self, response: Dict[str, Any], client: Any) -> Dict[str, str]:
        if not response or not response.get("status"):
            raise RuntimeError(response.get("message", "Refresh/login returned invalid response"))

        data = response.get("data", {})
        jwt_token = data.get("jwtToken") or data.get("token")
        refresh_token = data.get("refreshToken") or self.refresh_token
        feed_token = None

        if hasattr(client, "getfeedToken"):
            try:
                feed_token = client.getfeedToken()
            except Exception:
                feed_token = None

        if not jwt_token:
            raise RuntimeError("Refresh/login response did not include a JWT token")

        return {
            "jwt_token": jwt_token,
            "refresh_token": refresh_token,
            "feed_token": feed_token,
        }

    def login(
        self,
        client_code: Optional[str] = None,
        password: Optional[str] = None,
        totp: Optional[str] = None,
        retries: int = 3,
    ) -> Dict[str, Any]:
        client_code = client_code or self.client_id
        password = password or self._get_mpin()
        totp = totp or self._get_otp_code()

        if not client_code or not password:
            return {
                "status": "error",
                "message": "Missing client_id or MPIN for Angel One login",
                "success": False,
            }

        last_error = "Login failed"
        for attempt in range(1, retries + 1):
            try:
                client = self._create_client()
                response = client.generateSession(client_code, password, totp)
                tokens = self._extract_tokens(response, client)
                self._store_tokens(
                    tokens["jwt_token"], tokens["refresh_token"], tokens["feed_token"]
                )
                return {"status": "success", "success": True, "data": tokens}
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Angel One login attempt %s/%s failed: %s",
                    attempt,
                    retries,
                    last_error,
                )

        logger.error("Angel One login failed after %s attempts: %s", retries, last_error)
        return {"status": "error", "message": last_error, "success": False}

    def refresh(self) -> Dict[str, Any]:
        if not self.refresh_token:
            logger.warning("No refresh token available, forcing login")
            return self.login()

        client = self._create_client()
        try:
            response = self._refresh_with_client(client)
            tokens = self._extract_tokens(response, client)
            self._store_tokens(
                tokens["jwt_token"], tokens["refresh_token"], tokens["feed_token"]
            )
            logger.info("Angel One token refreshed successfully")
            return {"status": "success", "success": True, "data": tokens}
        except Exception as exc:
            logger.warning("Angel One refresh failed: %s. Falling back to login", exc)
            return self.login()

    def get_valid_token(self) -> str:
        if self.jwt_token and not self._is_expired():
            if self._is_near_expiry():
                logger.info("Angel One token is near expiry, refreshing")
                result = self.refresh()
                if not result.get("success"):
                    raise RuntimeError(result.get("message", "Failed to refresh token"))
            return self.jwt_token

        result = self.refresh() if self.refresh_token else self.login()
        if not result.get("success"):
            raise RuntimeError(result.get("message", "Angel One authentication failed"))

        if not self.jwt_token:
            raise RuntimeError("Angel One token manager failed to obtain a valid JWT token")

        return self.jwt_token

    def get_feed_token(self) -> Optional[str]:
        if self.feed_token and not self._is_expired():
            return self.feed_token
        self.get_valid_token()
        return self.feed_token

    def is_authenticated(self) -> bool:
        return bool(self.jwt_token and not self._is_expired())

    def clear_tokens(self) -> None:
        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None
        self.issued_at = None
        self.expires_at = None
        self._secure_tokens = {}

    def get_token_state(self) -> Dict[str, Any]:
        return {
            "jwt_token": self.jwt_token,
            "refresh_token": self.refresh_token,
            "feed_token": self.feed_token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_authenticated": self.is_authenticated(),
        }
