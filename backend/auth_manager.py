import os
import logging
import requests

try:
    from SmartApi import SmartConnect
except ImportError:
    SmartConnect = None

logger = logging.getLogger(__name__)

class SmartSession:
    def __init__(self):
        self.api_key = os.getenv("ANGEL_ONE_API_KEY", "LFHr3Azz")
        self.client_id = os.getenv("ANGEL_ONE_CLIENT_ID")
        self.mpin = os.getenv("ANGEL_ONE_MPIN") or os.getenv("ANGEL_ONE_PASSWORD")
        self.totp_seed = os.getenv("ANGEL_ONE_TOTP_SEED")
        
        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None
        self.client = None

    def _check_static_ip_warning(self):
        try:
            ip = requests.get('https://api.ipify.org').text
            logger.warning(f"Static IP Check (2026 Requirement): Ensure your public IP {ip} is whitelisted in Angel One Console (App {self.api_key}).")
        except Exception:
            logger.warning("Static IP Check failed. Ensure your server's IP is whitelisted.")

    def login(self, retries: int = 3):
        self._check_static_ip_warning()
        if not SmartConnect:
            raise Exception("SmartApi package not found")
        
        if not all([self.api_key, self.client_id, self.mpin, self.totp_seed]):
            raise Exception(
                "Missing API credentials. Check ANGEL_ONE_API_KEY, ANGEL_ONE_CLIENT_ID, "
                "ANGEL_ONE_MPIN (or ANGEL_ONE_PASSWORD), and ANGEL_ONE_TOTP_SEED"
            )
            
        last_error = "Login could not be completed"

        for attempt in range(1, retries + 1):
            try:
                import pyotp
                self.client = SmartConnect(api_key=self.api_key)
                totp = pyotp.TOTP(self.totp_seed).now()

                data = self.client.generateSession(self.client_id, self.mpin, totp)
                
                if data and data.get('status'):
                    self.feed_token = self.client.getfeedToken()
                    self.jwt_token = data['data']['jwtToken']
                    self.refresh_token = data['data']['refreshToken']
                    logger.info(
                        f"Angel One session generated successfully on attempt {attempt}."
                    )
                    return True

                last_error = data or 'Unknown error'
                logger.warning(
                    f"Angel One login attempt {attempt} failed: {last_error}"
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Angel One login attempt {attempt} failed: {last_error}"
                )

        logger.error(f"Angel One login failed after {retries} attempts: {last_error}")
        return False

    def is_valid_session(self):
        if not self.client or not self.refresh_token:
            return False
            
        try:
            profile = self.client.getProfile(self.refresh_token)
            return profile and profile.get('status') is True
        except Exception:
            return False

    def finalize_from_callback(self, auth_token: str):
        """
        Finalizes session natively matching the frontend flow.
        """
        self.jwt_token = auth_token
        # Try doing backend login automatically in tandem
        self.login()
        return True

global_smart_session = SmartSession()
