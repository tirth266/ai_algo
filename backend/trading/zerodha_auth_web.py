"""
Zerodha Kite Connect Web Authentication Module

Handles browser-based authentication flow for Zerodha Kite Connect.
Provides API endpoints for login, callback handling, and session management.

Features:
- Generate login URL for browser authentication
- Handle callback with request_token
- Generate and store access_token
- Session persistence and validation
- Auto-reconnection on startup

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from kiteconnect import KiteConnect
    from kiteconnect.exceptions import TokenException, NetworkException
except ImportError:
    KiteConnect = None
    TokenException = None
    NetworkException = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ZerodhaAuthWeb:
    """
    Manages Zerodha Kite Connect authentication for web interface.
    
    This class handles the complete OAuth-like flow:
    1. Generate login URL
    2. User authenticates in browser
    3. Callback with request_token
    4. Exchange for access_token
    5. Store session for API use
    
    Usage:
        >>> auth = ZerodhaAuthWeb()
        >>> url = auth.generate_login_url()
        >>> # User logs in via browser
        >>> result = auth.handle_callback(request_token)
    """
    
    def __init__(self, config_dir: str = None):
        """
        Initialize Zerodha web authentication.
        
        Args:
            config_dir: Directory to store session config (default: backend/config/)
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
        self.session_file = self.config_dir / 'zerodha_session.json'
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Kite Connect instance
        self.kite: Optional[KiteConnect] = None
        
        # Session data
        self.session_data: Optional[Dict[str, Any]] = None
        
        # Load existing session
        self._load_session()
        
        logger.info(f"ZerodhaAuthWeb initialized (API Key: {self.api_key[:4]}***)")
    
    def generate_login_url(self) -> str:
        """
        Generate Zerodha Kite Connect login URL.
        
        Returns:
            Login URL to open in browser
            
        Example:
            >>> auth = ZerodhaAuthWeb()
            >>> url = auth.generate_login_url()
            >>> # Redirect user to this URL
        """
        try:
            if not KiteConnect:
                raise ImportError("kiteconnect package not installed")
            
            kite = KiteConnect(api_key=self.api_key)
            login_url = kite.login_url()
            
            logger.info(f"Login URL generated successfully")
            return login_url
        
        except Exception as e:
            logger.error(f"Failed to generate login URL: {str(e)}")
            raise
    
    def handle_callback(self, request_token: str) -> Dict[str, Any]:
        """
        Handle callback from Zerodha after user login.
        
        Exchanges request_token for access_token and stores session.
        
        Args:
            request_token: Request token from callback URL
            
        Returns:
            Dictionary with access_token and user info
            
        Example:
            >>> # After user logs in, Zerodha redirects to:
            >>> # /api/broker/callback?request_token=abc123
            >>> result = auth.handle_callback('abc123')
            >>> print(f"Access Token: {result['access_token']}")
        """
        try:
            logger.info(f"Handling callback with request token...")
            
            if not KiteConnect:
                raise ImportError("kiteconnect package not installed")
            
            # Initialize Kite Connect
            kite = KiteConnect(api_key=self.api_key)
            
            # Generate session
            data = kite.generate_session(request_token, api_secret=self.api_secret)
            
            access_token = data['access_token']
            user_id = data['user_id']
            user_name = data.get('user_name', 'Unknown')
            email = data.get('email', '')
            
            # Create session data
            session_data = {
                'access_token': access_token,
                'user_id': user_id,
                'user_name': user_name,
                'email': email,
                'login_time': datetime.now().isoformat(),
                'expiry_date': (datetime.now() + timedelta(days=1)).isoformat(),
                'api_key': self.api_key,
                'broker': 'Zerodha'
            }
            
            # Save session
            self._save_session(session_data)
            
            # Initialize kite client
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(access_token)
            
            logger.info(f"✅ Authentication successful for user: {user_id}")
            
            return {
                'status': 'success',
                'access_token': access_token,
                'user_id': user_id,
                'user_name': user_name,
                'email': email,
                'message': 'Authentication successful'
            }
        
        except TokenException as e:
            logger.error(f"Invalid request token: {str(e)}")
            raise ValueError(f"Invalid request token: {str(e)}")
        
        except NetworkException as e:
            logger.error(f"Network error during authentication: {str(e)}")
            raise ConnectionError(f"Network error: {str(e)}")
        
        except Exception as e:
            logger.error(f"Callback handling failed: {str(e)}")
            raise
    
    def get_kite_client(self) -> Optional[KiteConnect]:
        """
        Get authenticated Kite Connect client.
        
        Returns:
            Authenticated KiteConnect instance or None if not connected
            
        Example:
            >>> kite = auth.get_kite_client()
            >>> if kite:
            ...     positions = kite.positions()
        """
        try:
            # Load existing session
            self._load_session()
            
            if not self.session_data or not self._is_session_valid():
                logger.warning("No valid session found")
                return None
            
            # Initialize with existing token
            if not KiteConnect:
                raise ImportError("kiteconnect package not installed")
            
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.session_data['access_token'])
            
            logger.info("Using existing valid session")
            return self.kite
        
        except Exception as e:
            logger.error(f"Failed to get kite client: {str(e)}")
            return None
    
    def is_connected(self) -> bool:
        """
        Check if currently connected to Zerodha with valid session.
        
        Returns:
            True if connected and authenticated
            
        Example:
            >>> if auth.is_connected():
            ...     print("Broker connected!")
        """
        try:
            self._load_session()
            
            if not self.session_data:
                return False
            
            # Test connection by making API call
            if not self.kite:
                if not KiteConnect:
                    raise ImportError("kiteconnect package not installed")
                
                self.kite = KiteConnect(api_key=self.api_key)
                self.kite.set_access_token(self.session_data['access_token'])
            
            # Try to get profile
            profile = self.kite.profile()
            
            return profile.get('user_id') is not None
        
        except TokenException:
            logger.warning("Session token is invalid/expired")
            return False
        
        except Exception as e:
            logger.error(f"Connection check failed: {str(e)}")
            return False
    
    def logout(self):
        """Clear stored session and logout."""
        try:
            if self.session_file.exists():
                self.session_file.unlink()
                logger.info("Session file deleted - logged out successfully")
            
            self.session_data = None
            self.kite = None
        
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            raise
    
    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current session information.
        
        Returns:
            Session info dictionary or None if no session
            
        Example:
            >>> info = auth.get_session_info()
            >>> if info:
            ...     print(f"User: {info['user_name']}")
            ...     print(f"Expires: {info['expiry_date']}")
        """
        self._load_session()
        
        if not self.session_data:
            return None
        
        return {
            'user_id': self.session_data.get('user_id'),
            'user_name': self.session_data.get('user_name'),
            'email': self.session_data.get('email'),
            'login_time': self.session_data.get('login_time'),
            'expiry_date': self.session_data.get('expiry_date'),
            'broker': self.session_data.get('broker'),
            'is_valid': self._is_session_valid()
        }
    
    def _load_session(self):
        """Load session from file."""
        try:
            if not self.session_file.exists():
                logger.debug("No existing session file found")
                self.session_data = None
                return
            
            with open(self.session_file, 'r', encoding='utf-8') as f:
                self.session_data = json.load(f)
            
            logger.debug(f"Session loaded for user: {self.session_data.get('user_id', 'Unknown')}")
        
        except Exception as e:
            logger.error(f"Failed to load session: {str(e)}")
            self.session_data = None
    
    def _save_session(self, session_data: Dict[str, Any]):
        """Save session to file."""
        try:
            # Ensure config directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Save to file
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            
            logger.info(f"Session saved to {self.session_file}")
        
        except Exception as e:
            logger.error(f"Failed to save session: {str(e)}")
            raise
    
    def _is_session_valid(self) -> bool:
        """Check if session is still valid."""
        try:
            if not self.session_data:
                return False
            
            # Check expiry
            expiry_str = self.session_data.get('expiry_date')
            
            if not expiry_str:
                return False
            
            expiry_date = datetime.fromisoformat(expiry_str)
            
            # Session expires after 1 day
            if datetime.now() > expiry_date:
                logger.warning("Session has expired")
                return False
            
            # Verify API key matches
            if self.session_data.get('api_key') != self.api_key:
                logger.warning("API key mismatch - session invalid")
                return False
            
            logger.debug("Session is valid")
            return True
        
        except Exception as e:
            logger.error(f"Session validation failed: {str(e)}")
            return False


# Global authentication instance
_auth_web: Optional[ZerodhaAuthWeb] = None


def get_zerodha_auth_web() -> ZerodhaAuthWeb:
    """
    Get global Zerodha web authentication instance.
    
    Returns:
        ZerodhaAuthWeb instance
        
    Example:
        >>> auth = get_zerodha_auth_web()
        >>> url = auth.generate_login_url()
    """
    global _auth_web
    
    if _auth_web is None:
        _auth_web = ZerodhaAuthWeb()
    
    return _auth_web


def get_zerodha_kite_client() -> Optional[KiteConnect]:
    """
    Get authenticated Zerodha Kite Connect client.
    
    Returns:
        Authenticated KiteConnect instance or None
        
    Example:
        >>> kite = get_zerodha_kite_client()
        >>> if kite:
        ...     # Use kite client for trading
        ...     positions = kite.positions()
    """
    auth = get_zerodha_auth_web()
    return auth.get_kite_client()


def is_zerodha_connected() -> bool:
    """
    Check if Zerodha is connected and authenticated.
    
    Returns:
        True if connected
        
    Example:
        >>> if is_zerodha_connected():
        ...     print("Ready to trade!")
    """
    try:
        auth = get_zerodha_auth_web()
        return auth.is_connected()
    except Exception:
        return False


# CLI entry point for testing
if __name__ == '__main__':
    print("\n" + "="*70)
    print("ZERODHA WEB AUTHENTICATION TEST")
    print("="*70 + "\n")
    
    auth = get_zerodha_auth_web()
    
    # Check existing session
    if auth.is_connected():
        print("✅ Already connected to Zerodha!")
        info = auth.get_session_info()
        print(f"\nUser: {info['user_name']} ({info['user_id']})")
        print(f"Email: {info['email']}")
        print(f"Login Time: {info['login_time']}")
        print(f"Expires: {info['expiry_date']}")
    else:
        print("❌ Not connected to Zerodha")
        print("\nGenerate login URL:")
        url = auth.generate_login_url()
        print(f"\n{url}")
        print("\nOpen this URL in your browser to login.")
    
    print("\n" + "="*70 + "\n")
