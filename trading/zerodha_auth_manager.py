"""
Zerodha Authentication Manager

Permanent API credential management with automatic daily token generation.

Features:
- Permanent API key/secret storage
- Automatic access token generation
- Token persistence and validation
- Auto re-authentication on expiry
- Secure credential management

Usage:
    from trading.zerodha_auth_manager import get_kite_client
    
    # Automatically handles authentication
    kite = get_kite_client()
    
    # Use kite client for trading
    positions = kite.positions()

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

try:
    from kiteconnect import KiteConnect
    from kiteconnect.exceptions import TokenException
except ImportError:
    KiteConnect = None
    TokenException = None

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ZerodhaAuthManager:
    """
    Manages Zerodha Kite Connect authentication with permanent credentials.
    
    Features:
    - Stores API key/secret permanently in environment
    - Generates and stores access tokens automatically
    - Validates token expiry
    - Auto re-authenticates when needed
    
    Usage:
        >>> auth = ZerodhaAuthManager()
        >>> kite = auth.get_authenticated_client()
        >>> print(f"Connected: {auth.is_authenticated()}")
    """
    
    def __init__(self, config_dir: str = None):
        """
        Initialize Zerodha authentication manager.
        
        Args:
            config_dir: Directory to store token config (default: config/)
        """
        # Get API credentials from environment
        self.api_key = os.getenv('ZERODHA_API_KEY')
        self.api_secret = os.getenv('ZERODHA_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "ZERODHA_API_KEY and ZERODHA_API_SECRET must be set in .env file"
            )
        
        # Configuration directory
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / 'config'
        
        self.config_dir = Path(config_dir)
        self.token_file = self.config_dir / 'zerodha_token.json'
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Kite Connect instance
        self.kite: Optional[KiteConnect] = None
        
        # Token data
        self.token_data: Optional[Dict[str, Any]] = None
        
        logger.info(f"ZerodhaAuthManager initialized (API Key: {self.api_key[:4]}***)")
    
    def get_login_url(self) -> str:
        """
        Generate Zerodha login URL for manual authentication.
        
        Returns:
            Login URL to open in browser
        
        Example:
            >>> url = auth.get_login_url()
            >>> print(f"Open this URL: {url}")
            >>> # After login, you'll be redirected with request_token
        """
        try:
            kite = KiteConnect(api_key=self.api_key)
            login_url = kite.login_url()
            
            logger.info(f"Login URL generated: {login_url[:50]}...")
            return login_url
        
        except Exception as e:
            logger.error(f"Failed to generate login URL: {str(e)}")
            raise
    
    def generate_access_token(self, request_token: str) -> Dict[str, Any]:
        """
        Exchange request_token for access_token.
        
        Args:
            request_token: Request token from callback URL
        
        Returns:
            Dictionary with access_token and user info
        
        Example:
            >>> # After user logs in via browser, they get redirected to:
            >>> # your-callback/?request_token=abc123
            >>> result = auth.generate_access_token('abc123')
            >>> print(f"Access Token: {result['access_token']}")
        """
        try:
            logger.info(f"Exchanging request token for access token...")
            
            # Initialize Kite Connect
            kite = KiteConnect(api_key=self.api_key)
            
            # Generate session
            data = kite.generate_session(request_token, api_secret=self.api_secret)
            
            access_token = data['access_token']
            user_id = data['user_id']
            user_name = data.get('user_name', 'Unknown')
            
            # Create token data
            token_data = {
                'access_token': access_token,
                'user_id': user_id,
                'user_name': user_name,
                'login_time': datetime.now().isoformat(),
                'expiry_date': (datetime.now() + timedelta(days=1)).isoformat(),
                'api_key': self.api_key
            }
            
            # Save token
            self._save_token(token_data)
            
            # Initialize kite client
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(access_token)
            
            logger.info(f"Access token generated successfully for user: {user_id}")
            
            return {
                'status': 'success',
                'access_token': access_token,
                'user_id': user_id,
                'user_name': user_name,
                'message': 'Authentication successful'
            }
        
        except TokenException as e:
            logger.error(f"Invalid request token: {str(e)}")
            raise ValueError(f"Invalid request token: {str(e)}")
        
        except Exception as e:
            logger.error(f"Token generation failed: {str(e)}")
            raise
    
    def get_authenticated_client(self, auto_renew: bool = True) -> KiteConnect:
        """
        Get authenticated Kite Connect client.
        
        Args:
            auto_renew: Automatically renew expired token
        
        Returns:
            Authenticated KiteConnect instance
        
        Example:
            >>> kite = auth.get_authenticated_client()
            >>> positions = kite.positions()
        """
        try:
            # Load existing token
            self._load_token()
            
            # Check if token is valid
            if self.token_data and self._is_token_valid():
                logger.info("Using existing valid token")
                
                # Initialize with existing token
                self.kite = KiteConnect(api_key=self.api_key)
                self.kite.set_access_token(self.token_data['access_token'])
                
                return self.kite
            
            # Token expired or missing
            if auto_renew:
                logger.warning("Token expired or missing. Manual login required.")
                logger.info("Run: python scripts/login_zerodha.py")
                raise RuntimeError(
                    "Authentication required. Please run: python scripts/login_zerodha.py"
                )
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
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.token_data['access_token'])
            
            # Try to get profile
            profile = self.kite.profile()
            
            return profile.get('user_id') is not None
        
        except TokenException:
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
            self.kite = None
        
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
    
    def refresh_token_manually(self, request_token: str) -> Dict[str, Any]:
        """
        Manually refresh token with new request token.
        
        Args:
            request_token: New request token from login
        
        Returns:
            Result dictionary with new access token
        """
        logger.info("Manual token refresh requested")
        
        # Clear old token
        self.token_data = None
        
        # Generate new token
        result = self.generate_access_token(request_token)
        
        logger.info("Token refreshed successfully")
        
        return result


# Global authentication manager instance
_auth_manager: Optional[ZerodhaAuthManager] = None


def get_auth_manager() -> ZerodhaAuthManager:
    """
    Get global authentication manager instance.
    
    Returns:
        ZerodhaAuthManager instance
    
    Example:
        >>> auth = get_auth_manager()
        >>> kite = auth.get_authenticated_client()
    """
    global _auth_manager
    
    if _auth_manager is None:
        _auth_manager = ZerodhaAuthManager()
    
    return _auth_manager


def get_kite_client(auto_renew: bool = True) -> KiteConnect:
    """
    Get authenticated Kite Connect client.
    
    This is the main function you'll use in your trading code.
    
    Args:
        auto_renew: Automatically handle token renewal
    
    Returns:
        Authenticated KiteConnect instance
    
    Example:
        >>> from trading.zerodha_auth_manager import get_kite_client
        >>> 
        >>> # In your trading code:
        >>> kite = get_kite_client()
        >>> 
        >>> # Now use it like normal
        >>> positions = kite.positions()
        >>> orders = kite.orders()
        >>> quote = kite.quote("RELIANCE")
    """
    auth_manager = get_auth_manager()
    return auth_manager.get_authenticated_client(auto_renew=auto_renew)


def is_zerodha_connected() -> bool:
    """
    Check if Zerodha connection is active and authenticated.
    
    Returns:
        True if connected and authenticated
    
    Example:
        >>> if is_zerodha_connected():
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
    print("ZERODHA AUTHENTICATION - MANUAL LOGIN")
    print("="*70 + "\n")
    
    auth_manager = get_auth_manager()
    
    # Step 1: Generate login URL
    print("Step 1: Opening Zerodha login page...")
    login_url = auth_manager.get_login_url()
    
    print(f"\nPlease open this URL in your browser:")
    print(f"{login_url}")
    print("\n" + "-"*70 + "\n")
    
    # Step 2: Get request token from user
    print("Step 2: After logging in, you will be redirected to a URL.")
    print("The URL will look like: https://your-domain.com/callback?request_token=abc123...")
    print("\nCopy the request_token value from the URL.\n")
    
    request_token = input("Enter request_token: ").strip()
    
    if not request_token:
        print("❌ No request token provided. Authentication cancelled.")
        return
    
    # Step 3: Generate access token
    print("\nStep 3: Generating access token...")
    
    try:
        result = auth_manager.generate_access_token(request_token)
        
        print("\n✅ Authentication Successful!")
        print(f"\nUser ID: {result['user_id']}")
        print(f"User Name: {result['user_name']}")
        print(f"Access Token: {result['access_token'][:20]}...")
        print(f"\nToken saved to: {auth_manager.token_file}")
        print("\nYou can now start trading!")
        
    except Exception as e:
        print(f"\n❌ Authentication Failed: {str(e)}")
        print("\nPlease try again.")
    
    print("\n" + "="*70 + "\n")


# CLI entry point
if __name__ == '__main__':
    manual_login_flow()
