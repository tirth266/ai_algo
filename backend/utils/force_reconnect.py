"""
Force Broker Reconnection Script

Bypasses UI and directly generates fresh access token using Zerodha API.
Saves token to token.json for immediate use.

Usage:
    python backend/utils/force_reconnect.py
    
Requirements:
    - Valid Zerodha API Key
    - Valid Zerodha API Secret
    - Request Token (from manual login or OAuth flow)
"""

import json
import os
from pathlib import Path
from datetime import datetime
import logging

try:
    from kiteconnect import KiteConnect
except ImportError:
    print("❌ KiteConnect not installed. Run: pip install kiteconnect")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_credentials():
    """Load API credentials from .env file or environment."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv('ZERODHA_API_KEY')
        api_secret = os.getenv('ZERODHA_API_SECRET')
        
        if not api_key or not api_secret:
            logger.warning("API credentials not found in .env file")
            logger.info("\nPlease add to .env:")
            logger.info("  ZERODHA_API_KEY=your_api_key")
            logger.info("  ZERODHA_API_SECRET=your_api_secret")
            
            # Fallback: Ask user
            print("\n" + "="*70)
            api_key = input("Enter API Key: ").strip()
            api_secret = input("Enter API Secret: ").strip()
        
        return api_key, api_secret
        
    except Exception as e:
        logger.error(f"Error loading credentials: {e}")
        return None, None


def get_request_token_manual(api_key):
    """
    Guide user through manual request token generation.
    
    Args:
        api_key: Zerodha API key
    
    Returns:
        Request token string
    """
    print("\n" + "="*70)
    print("  MANUAL REQUEST TOKEN GENERATION")
    print("="*70)
    print("\nStep 1: Open this URL in your browser:")
    print(f"https://kite.trade/connect/login?api_key={api_key}&v=3")
    print("\nStep 2: Login with your Zerodha credentials")
    print("Step 3: After login, you'll be redirected to a URL like:")
    print("  http://localhost/?request_token=abc123&status=success")
    print("\nStep 4: Copy the request_token value from the URL")
    print("="*70)
    
    request_token = input("\nEnter Request Token: ").strip()
    
    if not request_token:
        logger.error("No request token provided")
        return None
    
    return request_token


def generate_access_token(api_key, api_secret, request_token):
    """
    Exchange request token for access token.
    
    Args:
        api_key: Zerodha API key
        api_secret: Zerodha API secret
        request_token: Request token from OAuth flow
    
    Returns:
        Access token string or None
    """
    try:
        logger.info("Exchanging request token for access token...")
        
        # Initialize KiteConnect
        kite = KiteConnect(api_key=api_key)
        
        # Generate session
        data = kite.generate_session(request_token, api_secret=api_secret)
        
        access_token = data['access_token']
        
        logger.info(f"✅ Access token generated successfully!")
        logger.info(f"   User ID: {data['user_id']}")
        logger.info(f"   User Name: {data.get('user_name', 'N/A')}")
        
        return access_token, data
        
    except Exception as e:
        logger.error(f"Failed to generate access token: {e}")
        logger.error("\nPossible reasons:")
        logger.error("  • Invalid request token")
        logger.error("  • Invalid API secret")
        logger.error("  • Request token expired (valid for ~10 minutes)")
        return None, None


def save_token_to_file(access_token, user_data, filepath='trading/token.json'):
    """
    Save access token and user data to JSON file.
    
    Args:
        access_token: Access token string
        user_data: User info dictionary
        filepath: Output file path
    
    Returns:
        True if saved successfully
    """
    try:
        # Create directory if needed
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare token data
        token_data = {
            'access_token': access_token,
            'user_id': user_data.get('user_id'),
            'user_name': user_data.get('user_name'),
            'email': user_data.get('email'),
            'login_time': datetime.now().isoformat(),
            'expiry_date': datetime.now().replace(hour=15, minute=30).isoformat(),
            'broker': 'Zerodha'
        }
        
        # Save to file
        with open(output_path, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        logger.info(f"✅ Token saved to {filepath}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving token: {e}")
        return False


def verify_connection(api_key, access_token):
    """
    Verify the access token works by fetching user profile.
    
    Args:
        api_key: API key
        access_token: Access token to test
    
    Returns:
        True if connection successful
    """
    try:
        logger.info("Verifying connection...")
        
        # Initialize KiteConnect with new token
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        # Try to get user profile
        profile = kite.profile()
        
        logger.info(f"✅ Connection verified!")
        logger.info(f"   User ID: {profile['user_id']}")
        logger.info(f"   Email: {profile.get('email', 'N/A')}")
        logger.info(f"   Broker: {profile.get('broker', 'Zerodha')}")
        
        return True
        
    except Exception as e:
        logger.error(f"Connection verification failed: {e}")
        return False


def main():
    """Main function to force reconnect broker."""
    print("="*70)
    print("  ZERODHA FORCE RECONNECT")
    print("="*70)
    print("\nThis will generate a fresh access token and save it.")
    print("No UI required - completely automated after you provide credentials.\n")
    
    # Step 1: Load credentials
    api_key, api_secret = load_credentials()
    
    if not api_key or not api_secret:
        print("\n❌ ABORTED - Missing credentials")
        print("\nTo fix:")
        print("  1. Edit .env file in project root")
        print("  2. Add:")
        print("     ZERODHA_API_KEY=your_key_here")
        print("     ZERODHA_API_SECRET=your_secret_here")
        print("  3. Re-run this script")
        return
    
    # Step 2: Get request token
    request_token = get_request_token_manual(api_key)
    
    if not request_token:
        print("\n❌ ABORTED - No request token")
        return
    
    # Step 3: Generate access token
    access_token, user_data = generate_access_token(api_key, api_secret, request_token)
    
    if not access_token:
        print("\n❌ FAILED - Could not generate access token")
        print("\nTry again:")
        print("  1. Make sure request token is correct")
        print("  2. Ensure API secret is valid")
        print("  3. Generate request token quickly (expires in ~10 min)")
        return
    
    # Step 4: Verify connection
    if not verify_connection(api_key, access_token):
        print("\n⚠️  Connection verification failed")
        print("   Token may still work, but verify manually")
    
    # Step 5: Save token
    success = save_token_to_file(access_token, user_data)
    
    if success:
        print("\n" + "="*70)
        print("  ✅ RECONNECT SUCCESSFUL!")
        print("="*70)
        print(f"\nYour trading platform can now:")
        print(f"  ✓ Fetch historical data from Zerodha")
        print(f"  ✓ Receive live market ticks")
        print(f"  ✓ Execute real trades")
        print(f"\nNext Steps:")
        print(f"  1. Restart Flask backend: python backend/app.py")
        print(f"  2. Refresh browser: http://localhost:3000")
        print(f"  3. Check broker status - should show 'Connected'")
        print(f"  4. Run backtest: python run_terminal_backtest.py --diagnostic")
        print("="*70 + "\n")
    else:
        print("\n❌ Failed to save token")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
