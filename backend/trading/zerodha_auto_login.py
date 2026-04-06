"""
Zerodha Auto Login System

Fully automated authentication with local callback server.
No manual token copying required!

Features:
- Automatic browser opening
- Local callback server to capture request_token
- Automatic access_token generation
- Secure token storage
- One-command daily login

Usage:
    python scripts/zerodha_login_server.py
    
Or programmatically:
    from trading.zerodha_auto_login import get_kite_client
    kite = get_kite_client()

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import os
import json
import logging
import webbrowser
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string
from werkzeug.serving import make_server

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


class ZerodhaAutoLogin:
    """
    Automated Zerodha authentication with local callback server.
    
    Flow:
    1. Generate login URL
    2. Open browser automatically
    3. User logs in to Zerodha
    4. Redirect to local callback server
    5. Capture request_token automatically
    6. Generate access_token
    7. Store token securely
    
    Usage:
        >>> auth = ZerodhaAutoLogin()
        >>> auth.start_login_flow()
        # Browser opens automatically
        # After login, token is saved automatically
    """
    
    def __init__(self, config_dir: str = None, callback_port: int = 5001):
        """
        Initialize auto login system.
        
        Args:
            config_dir: Directory to store token config
            callback_port: Port for local callback server
        """
        # Get API credentials
        self.api_key = os.getenv('ZERODHA_API_KEY')
        self.api_secret = os.getenv('ZERODHA_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "ZERODHA_API_KEY and ZERODHA_API_SECRET must be set in .env file"
            )
        
        # Configuration
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / 'config'
        
        self.config_dir = Path(config_dir)
        self.token_file = self.config_dir / 'zerodha_session.json'
        self.callback_port = callback_port
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Kite Connect instance
        self.kite: Optional[KiteConnect] = None
        
        # Token data
        self.token_data: Optional[Dict[str, Any]] = None
        
        # Callback server
        self.server: Optional[ServerThread] = None
        
        logger.info(f"ZerodhaAutoLogin initialized (API Key: {self.api_key[:4]}***)")
    
    def start_login_flow(self):
        """
        Start the automated login flow.
        
        This will:
        1. Generate login URL
        2. Open browser automatically
        3. Start callback server
        4. Wait for redirect with request_token
        5. Generate and save access_token
        """
        try:
            print("\n" + "="*70)
            print("ZERODHA AUTOMATED LOGIN SYSTEM")
            print("="*70 + "\n")
            
            # Step 1: Generate login URL
            print("[1/4] Generating login URL...")
            login_url = self.get_login_url()
            print(f"      Login URL: {login_url[:60]}...")
            
            # Step 2: Open browser automatically
            print("\n[2/4] Opening browser automatically...")
            webbrowser.open(login_url)
            print("      Browser opened! Please login to Zerodha.")
            
            # Step 3: Start callback server
            print(f"\n[3/4] Starting callback server on port {self.callback_port}...")
            print("      Waiting for Zerodha redirect...")
            
            self.server = ServerThread(self.callback_port, self)
            self.server.start()
            
            # Step 4: Wait for callback (blocking)
            self.server.join()
            
            if self.server.request_token:
                print(f"\n[4/4] Request token captured!")
                print(f"      Generating access token...")
                
                # Generate access token
                result = self.generate_access_token(self.server.request_token)
                
                print(f"\n✅ Authentication Successful!")
                print(f"\nUser ID: {result['user_id']}")
                print(f"User Name: {result['user_name']}")
                print(f"Access Token: {result['access_token'][:20]}...")
                print(f"\nToken saved to: {self.token_file}")
                print("\n🎉 You can now start trading!")
                
                return result
            
            else:
                print("\n❌ Login cancelled or failed")
                return None
        
        except Exception as e:
            print(f"\n❌ Error during login: {str(e)}")
            logger.error(f"Login flow failed: {str(e)}")
            return None
        
        finally:
            print("\n" + "="*70 + "\n")
    
    def get_login_url(self) -> str:
        """
        Generate Zerodha login URL.
        
        Returns:
            Login URL string
        """
        try:
            kite = KiteConnect(api_key=self.api_key)
            login_url = kite.login_url()
            
            logger.info(f"Login URL generated")
            return login_url
        
        except Exception as e:
            logger.error(f"Failed to generate login URL: {str(e)}")
            raise
    
    def generate_access_token(self, request_token: str) -> Dict[str, Any]:
        """
        Exchange request_token for access_token.
        
        Args:
            request_token: Request token from callback
        
        Returns:
            Dictionary with access_token and user info
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
                print("\n⚠️  Token expired or missing. Starting auto-login...")
                result = self.start_login_flow()
                
                if result:
                    return self.kite
                else:
                    raise RuntimeError("Authentication failed")
            else:
                raise RuntimeError("No valid token found")
        
        except Exception as e:
            logger.error(f"Failed to get authenticated client: {str(e)}")
            raise
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        try:
            self._load_token()
            
            if not self.token_data:
                return False
            
            # Test token by making API call
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.token_data['access_token'])
            
            profile = self.kite.profile()
            return profile.get('user_id') is not None
        
        except Exception:
            return False
    
    def validate_token(self) -> bool:
        """Validate current access token."""
        return self._is_token_valid()
    
    def logout(self):
        """Clear stored token."""
        try:
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info("Token file deleted - logged out")
            
            self.token_data = None
            self.kite = None
        
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            raise
    
    def _load_token(self):
        """Load token from file."""
        try:
            if not self.token_file.exists():
                self.token_data = None
                return
            
            with open(self.token_file, 'r', encoding='utf-8') as f:
                self.token_data = json.load(f)
            
            logger.debug(f"Token loaded for user: {self.token_data.get('user_id')}")
        
        except Exception as e:
            logger.error(f"Failed to load token: {str(e)}")
            self.token_data = None
    
    def _save_token(self, token_data: Dict[str, Any]):
        """Save token to file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
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
            
            if datetime.now() > expiry_date:
                logger.warning("Token has expired")
                return False
            
            # Verify API key matches
            if self.token_data.get('api_key') != self.api_key:
                logger.warning("API key mismatch")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return False
    
    def get_token_info(self) -> Optional[Dict[str, Any]]:
        """Get current token information."""
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


class ServerThread(threading.Thread):
    """
    Flask server thread for handling OAuth callback.
    """
    
    def __init__(self, port: int, auth: ZerodhaAutoLogin):
        super().__init__()
        self.port = port
        self.auth = auth
        self.request_token: Optional[str] = None
        self.server: Optional[make_server] = None
        self.app = self.create_app()
    
    def create_app(self) -> Flask:
        """Create Flask app for callback server."""
        app = Flask(__name__)
        
        @app.route('/callback')
        def callback():
            """Handle Zerodha OAuth callback."""
            request_token = request.args.get('request_token')
            
            if request_token:
                self.request_token = request_token
                
                # Show success page
                return render_template_string('''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Login Successful</title>
                        <style>
                            body {
                                font-family: Arial, sans-serif;
                                text-align: center;
                                padding: 50px;
                                background: #f0f0f0;
                            }
                            .success {
                                color: #28a745;
                                font-size: 24px;
                                margin-bottom: 20px;
                            }
                            .info {
                                color: #666;
                                font-size: 16px;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="success">✅ Login Successful!</div>
                        <div class="info">
                            Your access token has been generated automatically.<br>
                            You can close this window and return to the terminal.
                        </div>
                    </body>
                    </html>
                ''')
            else:
                # Show error page
                return render_template_string('''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Login Failed</title>
                        <style>
                            body {
                                font-family: Arial, sans-serif;
                                text-align: center;
                                padding: 50px;
                                background: #f0f0f0;
                            }
                            .error {
                                color: #dc3545;
                                font-size: 24px;
                                margin-bottom: 20px;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="error">❌ Login Failed</div>
                        <div>Please try again.</div>
                    </body>
                    </html>
                ''')
        
        @app.route('/health')
        def health():
            """Health check endpoint."""
            return jsonify({'status': 'ok'})
        
        return app
    
    def run(self):
        """Run the Flask server."""
        try:
            self.server = make_server('localhost', self.port, self.app, threaded=True)
            logger.info(f"Callback server running on http://localhost:{self.port}")
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            raise
    
    def shutdown(self):
        """Shutdown the server."""
        if self.server:
            self.server.shutdown()
            logger.info("Callback server shutdown")


# Global authentication manager instance
_auth_manager: Optional[ZerodhaAutoLogin] = None


def get_auth_manager() -> ZerodhaAutoLogin:
    """Get global authentication manager instance."""
    global _auth_manager
    
    if _auth_manager is None:
        _auth_manager = ZerodhaAutoLogin()
    
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
        >>> from trading.zerodha_auto_login import get_kite_client
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
    """Check if Zerodha connection is active."""
    try:
        auth_manager = get_auth_manager()
        return auth_manager.is_authenticated()
    
    except Exception:
        return False


def get_token_details() -> Optional[Dict[str, Any]]:
    """Get details about current authentication token."""
    auth_manager = get_auth_manager()
    return auth_manager.get_token_info()


def interactive_login():
    """Interactive login flow."""
    auth_manager = get_auth_manager()
    return auth_manager.start_login_flow()


# CLI entry point
if __name__ == '__main__':
    print("\n" + "="*70)
    print("ZERODHA AUTOMATED LOGIN SYSTEM")
    print("="*70 + "\n")
    
    auth = get_auth_manager()
    
    # Check existing token
    details = auth.get_token_info()
    
    if details and details['is_valid']:
        print("✅ You are already authenticated!")
        print(f"\nLogged in as: {details['user_name']} ({details['user_id']})")
        print(f"Token expires: {details['expiry_date']}")
        
        choice = input("\nDo you want to re-login? (y/n): ").strip().lower()
        
        if choice != 'y':
            print("\nExiting...")
            exit(0)
        else:
            print("\nStarting re-authentication...\n")
    
    # Run interactive login
    result = interactive_login()
    
    if result:
        print("\n🎉 SUCCESS! You can now start trading.")
        exit(0)
    else:
        print("\n❌ Authentication failed.")
        exit(1)
