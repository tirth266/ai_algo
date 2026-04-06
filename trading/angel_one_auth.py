"""
Angel One SmartAPI Authentication Manager

Automated authentication with TOTP support for Angel One SmartAPI.

Features:
- TOTP-based automated login using pyotp
- Session management with SmartConnect
- Token persistence and validation
- Auto re-authentication on expiry
- Secure credential management

Usage:
    from trading.angel_one_auth import get_smartapi_client
    
    # Automatically handles authentication
    smart_api = get_smartapi_client()
    
    # Use smart_api client for trading
    positions = smart_api.getPositions()

Author: Quantitative Trading Systems Engineer
Date: March 28, 2026
"""

import os
import json
import logging
import pyotp
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

try:
    from smartapi import SmartConnect
    from smartapi.exceptions import SmartApiException
except ImportError:
    SmartConnect = None
    SmartApiException = None

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AngelOneAuthManager:
    """
    Manages Angel One SmartAPI authentication with TOTP automation.
    
    Features:
    - Stores API key/secret permanently in environment
    - Generates TOTP automatically using pyotp
    - Creates and manages access tokens
    - Validates token expiry
    - Auto re-authenticates when needed
    
    Usage:
        >>> auth = AngelOneAuthManager()
        >>> smart_api = auth.get_authenticated_client()
        >>> print(f"Connected: {auth.is_authenticated()}")
    """
    
    def __init__(self, config_dir: str = None):
        """
        Initialize Angel One authentication manager.
        
        Args:
            config_dir: Directory to store token config (default: config/)
        """
        # Get API credentials from environment
        self.api_key = os.getenv('ANGEL_ONE_API_KEY')
        self.secret_key = os.getenv('ANGEL_ONE_SECRET_KEY')
        self.client_id = os.getenv('ANGEL_ONE_CLIENT_ID')
        self.totp_seed = os.getenv('ANGEL_ONE_TOTP_SEED')
        
        # Validate required credentials
        if not self.api_key or not self.secret_key or not self.client_id:
            raise ValueError(
                "ANGEL_ONE_API_KEY, ANGEL_ONE_SECRET_KEY, and ANGEL_ONE_CLIENT_ID "
                "must be set in .env file"
            )
        
        if not self.totp_seed:
            logger.warning(
                "ANGEL_ONE_TOTP_SEED not set. TOTP auto-generation will fail. "
                "Please add your TOTP seed to .env file."
            )
        
        # Configuration directory
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / 'config'
        
        self.config_dir = Path(config_dir)
        self.token_file = self.config_dir / 'angelone_token.json'
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # SmartConnect instance
        self.smart_api: Optional[SmartConnect] = None
        
        # Token data
        self.token_data: Optional[Dict[str, Any]] = None
        
        logger.info(f"AngelOneAuthManager initialized (API Key: {self.api_key[:4]}***)")
    
    def generate_totp(self) -> str:
        """
        Generate 6-digit TOTP code using pyotp.
        
        Returns:
            6-digit TOTP string
        
        Example:
            >>> totp = auth.generate_totp()
            >>> print(f"Current TOTP: {totp}")
        """
        if not self.totp_seed:
            raise ValueError("TOTP_SEED not configured in environment")
        
        try:
            # Create TOTP object with the seed
            totp = pyotp.TOTP(self.totp_seed)
            
            # Generate current 6-digit code
            current_totp = totp.now()
            
            logger.debug(f"Generated TOTP: {current_totp}")
            return current_totp
        
        except Exception as e:
            logger.error(f"Failed to generate TOTP: {str(e)}")
            raise
    
    def authenticate(self) -> Dict[str, Any]:
        """
        Authenticate with Angel One SmartAPI using TOTP.
        
        Returns:
            Dictionary with access_token, user info, and authentication status
        
        Example:
            >>> result = auth.authenticate()
            >>> print(f"Access Token: {result['access_token']}")
        """
        try:
            logger.info("Starting Angel One authentication with TOTP...")
            
            # Initialize SmartConnect
            self.smart_api = SmartConnect(api_key=self.api_key)
            
            # Generate TOTP
            totp = self.generate_totp()
            
            # Generate session using TOTP
            session_data = self.smart_api.generateSession(
                self.client_id,
                self.secret_key,
                totp
            )
            
            # Extract authentication details
            access_token = session_data.get('token')
            user_id = session_data.get('usercode')
            user_name = session_data.get('name', 'Unknown')
            
            if not access_token:
                raise ValueError("No access token received from SmartAPI")
            
            # Create token data
            token_data = {
                'access_token': access_token,
                'refresh_token': session_data.get('refreshToken'),
                'user_id': user_id,
                'user_name': user_name,
                'login_time': datetime.now().isoformat(),
                'expiry_date': (datetime.now() + timedelta(days=1)).isoformat(),
                'api_key': self.api_key,
                'client_id': self.client_id
            }
            
            # Save token
            self._save_token(token_data)
            
            # Set access token in smart_api
            self.smart_api.setAccessToken(access_token)
            
            logger.info(f"Authentication successful for user: {user_id}")
            
            return {
                'status': 'success',
                'access_token': access_token,
                'refresh_token': token_data['refresh_token'],
                'user_id': user_id,
                'user_name': user_name,
                'message': 'Authentication successful'
            }
        
        except SmartApiException as e:
            logger.error(f"SmartAPI authentication error: {str(e)}")
            raise ValueError(f"SmartAPI authentication failed: {str(e)}")
        
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise
    
    def get_authenticated_client(self, auto_renew: bool = True) -> SmartConnect:
        """
        Get authenticated SmartConnect client.
        
        Args:
            auto_renew: Automatically renew expired token
        
        Returns:
            Authenticated SmartConnect instance
        
        Example:
            >>> smart_api = auth.get_authenticated_client()
            >>> positions = smart_api.getPositions()
        """
        try:
            # Load existing token
            self._load_token()
            
            # Check if token is valid
            if self.token_data and self._is_token_valid():
                logger.info("Using existing valid token")
                
                # Initialize with existing token
                self.smart_api = SmartConnect(api_key=self.api_key)
                self.smart_api.setAccessToken(self.token_data['access_token'])
                
                return self.smart_api
            
            # Token expired or missing
            if auto_renew:
                logger.warning("Token expired or missing. Auto-authenticating...")
                result = self.authenticate()
                
                if result:
                    return self.smart_api
                else:
                    raise RuntimeError("Authentication failed")
            else:
                raise RuntimeError("No valid token found")
        
        except Exception as e:
            logger.error(f"Failed to get authenticated client: {str(e)}")
            raise
    
    def is_authenticated(self) -> bool:
        """
        Check if currently authenticated with valid token.
        
        Returns:
            True if authenticated, False otherwise
        
        Example:
            >>> if auth.is_authenticated():
            ...     print("Ready to trade!")
        """
        try:
            self._load_token()
            
            if not self.token_data:
                return False
            
            # Test token by making API call
            self.smart_api = SmartConnect(api_key=self.api_key)
            self.smart_api.setAccessToken(self.token_data['access_token'])
            
            # Try to get profile
            profile = self.smart_api.getProfile()
            
            return profile.get('status', False)
        
        except SmartApiException:
            logger.warning("Token is invalid/expired")
            return False
        
        except Exception as e:
            logger.error(f"Authentication check failed: {str(e)}")
            return False
    
    def validate_token(self) -> bool:
        """
        Validate current access token.
        
        Returns:
            True if token is valid, False otherwise
        """
        return self._is_token_valid()
    
    def logout(self):
        """Clear stored token and logout."""
        try:
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info("Token file deleted - logged out successfully")
            
            self.token_data = None
            self.smart_api = None
        
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            raise
    
    def _load_token(self):
        """Load token from file."""
        try:
            if not self.token_file.exists():
                logger.debug("No existing token file found")
                self.token_data = None
                return
            
            with open(self.token_file, 'r', encoding='utf-8') as f:
                self.token_data = json.load(f)
            
            logger.debug(f"Token loaded for user: {self.token_data.get('user_id', 'Unknown')}")
        
        except Exception as e:
            logger.error(f"Failed to load token: {str(e)}")
            self.token_data = None
    
    def _save_token(self, token_data: Dict[str, Any]):
        """Save token to file."""
        try:
            # Ensure config directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Save to file
            with open(self.token_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=2)
            
            logger.info(f"Token saved to {self.token_file}")
        
        except Exception as e:
            logger.error(f"Failed to save token: {str(e)}")
            raise
    
    def _is_token_valid(self) -> bool:
        """Check if token is still valid."""
        try:
            if not self.token_data:
                return False
            
            # Check expiry
            expiry_str = self.token_data.get('expiry_date')
            
            if not expiry_str:
                return False
            
            expiry_date = datetime.fromisoformat(expiry_str)
            
            # Token expires after 1 day
            if datetime.now() > expiry_date:
                logger.warning("Token has expired")
                return False
            
            # Verify API key matches
            if self.token_data.get('api_key') != self.api_key:
                logger.warning("API key mismatch - token invalid")
                return False
            
            logger.debug("Token is valid")
            return True
        
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return False
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current token information.
        
        Returns:
            Token info dictionary or None if no token
        
        Example:
            >>> info = auth.get_token_info()
            >>> if info:
            ...     print(f"User: {info['user_name']}")
            ...     print(f"Expires: {info['expiry_date']}")
        """
        self._load_token()
        
        if not self.token_data:
            return None
        
        return {
            'user_id': self.token_data.get('user_id'),
            'user_name': self.token_data.get('user_name'),
            'login_time': self.token_data.get('login_time'),
            'expiry_date': self.token_data.get('expiry_date'),
            'is_valid': self._is_token_valid()
        }
    
    def refresh_token_manually(self) -> Dict[str, Any]:
        """
        Manually refresh token.
        
        Returns:
            Result dictionary with new access token
        """
        logger.info("Manual token refresh requested")
        
        # Clear old token
        self.token_data = None
        
        # Generate new token
        result = self.authenticate()
        
        logger.info("Token refreshed successfully")
        
        return result


# Global authentication manager instance
_auth_manager: Optional[AngelOneAuthManager] = None


def get_auth_manager() -> AngelOneAuthManager:
    """
    Get global authentication manager instance.
    
    Returns:
        AngelOneAuthManager instance
    
    Example:
        >>> auth = get_auth_manager()
        >>> smart_api = auth.get_authenticated_client()
    """
    global _auth_manager
    
    if _auth_manager is None:
        _auth_manager = AngelOneAuthManager()
    
    return _auth_manager


def get_smartapi_client(auto_renew: bool = True) -> SmartConnect:
    """
    Get authenticated SmartConnect client.
    
    This is the main function you'll use in your trading code.
    
    Args:
        auto_renew: Automatically handle token renewal
    
    Returns:
        Authenticated SmartConnect instance
    
    Example:
        >>> from trading.angel_one_auth import get_smartapi_client
        >>> 
        >>> # In your trading code:
        >>> smart_api = get_smartapi_client()
        >>> 
        >>> # Now use it like normal
        >>> positions = smart_api.getPositions()
        >>> orders = smart_api.getOrders()
        >>> quote = smart_api.quote("SBIN-EQ")
    """
    auth_manager = get_auth_manager()
    return auth_manager.get_authenticated_client(auto_renew=auto_renew)


def is_angelone_connected() -> bool:
    """
    Check if Angel One connection is active and authenticated.
    
    Returns:
        True if connected and authenticated
    
    Example:
        >>> if is_angelone_connected():
        ...     print("Ready to trade!")
        ... else:
        ...     print("Please login first")
    """
    try:
        auth_manager = get_auth_manager()
        return auth_manager.is_authenticated()
    
    except Exception:
        return False


def get_token_details() -> Optional[Dict[str, Any]]:
    """
    Get details about current authentication token.
    
    Returns:
        Token details dictionary or None
    
    Example:
        >>> details = get_token_details()
        >>> if details:
        ...     print(f"Logged in as: {details['user_name']}")
        ...     print(f"Expires at: {details['expiry_date']}")
    """
    auth_manager = get_auth_manager()
    return auth_manager.get_token_info()


def manual_login_flow():
    """
    Interactive manual login flow for command line.
    
    Guides user through the authentication process.
    
    Example:
        >>> # Run this once to authenticate
        >>> manual_login_flow()
    """
    print("\n" + "="*70)
    print("ANGEL ONE SMARTAPI - AUTHENTICATION")
    print("="*70 + "\n")
    
    auth_manager = get_auth_manager()
    
    # Check TOTP configuration
    if not auth_manager.totp_seed:
        print("❌ TOTP_SEED not configured!")
        print("\nPlease add ANGEL_ONE_TOTP_SEED to your .env file.")
        print("This is required for automated TOTP generation.")
        print("\nExiting...")
        return
    
    # Step 1: Generate TOTP
    print("Step 1: Generating TOTP...")
    try:
        totp = auth_manager.generate_totp()
        print(f"      Generated TOTP: {totp}")
    except Exception as e:
        print(f"\n❌ Failed to generate TOTP: {str(e)}")
        return
    
    # Step 2: Authenticate
    print("\nStep 2: Authenticating with SmartAPI...")
    
    try:
        result = auth_manager.authenticate()
        
        print("\n✅ Authentication Successful!")
        print(f"\nUser ID: {result['user_id']}")
        print(f"User Name: {result['user_name']}")
        print(f"Access Token: {result['access_token'][:20]}...")
        print(f"\nToken saved to: {auth_manager.token_file}")
        print("\nYou can now start trading!")
        
    except Exception as e:
        print(f"\n❌ Authentication Failed: {str(e)}")
        print("\nPlease check your credentials and TOTP seed.")
    
    print("\n" + "="*70 + "\n")


# CLI entry point
if __name__ == '__main__':
    manual_login_flow()
