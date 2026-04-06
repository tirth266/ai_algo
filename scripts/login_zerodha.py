"""
Zerodha Login Helper Script

Quick command-line authentication for Zerodha Kite Connect.

Usage:
    python scripts/login_zerodha.py

This will:
1. Generate login URL
2. Guide you through browser login
3. Capture request_token
4. Generate and save access_token automatically

After first login, system will auto-authenticate on subsequent runs.

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.zerodha_auth_manager import (
    get_auth_manager,
    manual_login_flow,
    get_token_details,
    is_zerodha_connected
)


def show_status():
    """Show current authentication status."""
    print("\n" + "="*70)
    print("ZERODHA AUTHENTICATION STATUS")
    print("="*70 + "\n")
    
    auth = get_auth_manager()
    details = auth.get_token_info()
    
    if details:
        print(f"✅ Authentication Status: {'VALID' if details['is_valid'] else 'EXPIRED'}")
        print(f"\nUser Details:")
        print(f"  User ID: {details['user_id']}")
        print(f"  User Name: {details['user_name']}")
        print(f"  Login Time: {details['login_time']}")
        print(f"  Expiry Date: {details['expiry_date']}")
        
        if not details['is_valid']:
            print("\n⚠️  Token has expired. Re-authentication required.")
            print("   Run this script again to generate new token.")
    
    else:
        print("❌ No authentication found.")
        print("\nYou need to login to Zerodha to start trading.")
    
    print("\n" + "="*70 + "\n")


def main():
    """Main login flow."""
    print("\n" + "="*70)
    print("ZERODHA KITE CONNECT - AUTHENTICATION WIZARD")
    print("="*70 + "\n")
    
    auth = get_auth_manager()
    
    # Check existing authentication
    details = auth.get_token_info()
    
    if details and details['is_valid']:
        print("✅ You are already authenticated!")
        print(f"\nLogged in as: {details['user_name']} ({details['user_id']})")
        print(f"Token expires: {details['expiry_date']}")
        
        print("\nOptions:")
        print("  1. Continue with current session")
        print("  2. Logout and login again")
        print("  3. Exit")
        
        choice = input("\nEnter choice (1/2/3): ").strip()
        
        if choice == '1':
            print("\n✅ Ready to trade!")
            return True
        
        elif choice == '2':
            print("\nLogging out...")
            auth.logout()
            print("Logged out successfully.\n")
        
        elif choice == '3':
            print("\nExiting...")
            return False
    
    # New login flow
    print("Starting authentication process...\n")
    
    try:
        # Run interactive login
        manual_login_flow()
        
        # Verify success
        new_details = auth.get_token_info()
        
        if new_details and new_details['is_valid']:
            print("\n🎉 SUCCESS!")
            print(f"You are now logged in as: {new_details['user_name']}")
            print(f"Trading will begin automatically when you start the system.")
            return True
        
        else:
            print("\n❌ Authentication failed. Please try again.")
            return False
    
    except KeyboardInterrupt:
        print("\n\n❌ Authentication cancelled by user.")
        return False
    
    except Exception as e:
        print(f"\n❌ Error during authentication: {str(e)}")
        print("\nPlease check your API credentials and internet connection.")
        return False


if __name__ == '__main__':
    # Show current status
    show_status()
    
    # Run login if needed
    success = main()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
