"""
Broker Authentication API Routes

Handles Zerodha Kite Connect authentication via web interface.
Provides endpoints for login, callback, and session management.

Endpoints:
- GET  /api/broker/login        - Generate login URL
- GET  /api/broker/callback     - Handle OAuth callback
- GET  /api/broker/status       - Check connection status
- POST /api/broker/logout       - Logout and clear session

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from flask import Blueprint, jsonify, request, redirect
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Create blueprint
broker_bp = Blueprint('broker', __name__, url_prefix='/api/broker')


@broker_bp.route('/login', methods=['GET'])
def broker_login():
    """
    Generate Zerodha login URL and redirect user.
    
    This endpoint:
    1. Generates login URL from Zerodha
    2. Redirects user's browser to login page
    
    Returns:
        Redirect to Zerodha login page
        
    Usage:
        Frontend calls: window.location.href = '/api/broker/login'
    """
    try:
        logger.info("Generating Zerodha login URL...")
        
        # Import auth module
        try:
            from trading.zerodha_auth_web import get_zerodha_auth_web
        except ImportError as e:
            logger.error(f"Failed to import auth module: {e}")
            return jsonify({
                'success': False,
                'message': f'Authentication module not found: {str(e)}'
            }), 500
        
        # Get auth instance
        auth = get_zerodha_auth_web()
        
        # Generate login URL
        login_url = auth.generate_login_url()
        
        logger.info(f"Login URL generated successfully")
        
        # Redirect user to Zerodha login page
        return redirect(login_url)
    
    except Exception as e:
        logger.error(f"Failed to generate login URL: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to generate login URL: {str(e)}'
        }), 500


@broker_bp.route('/callback', methods=['GET'])
def broker_callback():
    """
    Handle Zerodha OAuth callback.
    
    Zerodha redirects here after successful login with request_token.
    
    Query Parameters:
        - request_token: Token from Zerodha
        - status: Success/failure status
        
    Returns:
        HTML page with auto-redirect or JSON response
        
    Usage:
        Zerodha redirects to: /api/broker/callback?request_token=abc123&status=success
    """
    try:
        # Get parameters from query string
        request_token = request.args.get('request_token')
        status = request.args.get('status', 'success')
        
        logger.info(f"Received callback from Zerodha")
        
        # Check for errors
        if status == 'error' or not request_token:
            logger.error("Callback failed or no request token")
            
            # Redirect to frontend with error
            frontend_url = "http://localhost:3000/broker?status=error&message=Authentication_failed"
            return redirect(frontend_url)
        
        logger.info(f"Processing request token...")
        
        # Import auth module
        try:
            from trading.zerodha_auth_web import get_zerodha_auth_web
        except ImportError as e:
            logger.error(f"Failed to import auth module: {e}")
            return jsonify({
                'success': False,
                'message': f'Authentication module not found: {str(e)}'
            }), 500
        
        # Get auth instance
        auth = get_zerodha_auth_web()
        
        # Handle callback and get access token
        result = auth.handle_callback(request_token)
        
        logger.info(f"✅ Authentication successful: {result['user_id']}")
        
        # Redirect to frontend with success
        frontend_url = (
            f"http://localhost:3000/broker?"
            f"status=success&"
            f"user_id={result['user_id']}&"
            f"user_name={result['user_name']}"
        )
        
        return redirect(frontend_url)
    
    except Exception as e:
        logger.error(f"Callback handling failed: {str(e)}")
        
        # Redirect to frontend with error
        frontend_url = f"http://localhost:3000/broker?status=error&message={str(e)}"
        return redirect(frontend_url)


@broker_bp.route('/status', methods=['GET'])
def broker_status():
    """
    Get current broker connection status.
    
    Returns:
        JSON with connection status
        
    Response:
        {
            "connected": true,
            "broker": "Zerodha",
            "user_id": "ABC123",
            "user_name": "John Doe"
        }
        
    Usage:
        Frontend polls this endpoint to check connection status
    """
    try:
        logger.debug("Checking broker connection status...")
        
        # Import auth module
        try:
            from trading.zerodha_auth_web import get_zerodha_auth_web
        except ImportError as e:
            logger.error(f"Failed to import auth module: {e}")
            return jsonify({
                'success': False,
                'message': f'Authentication module not found: {str(e)}'
            }), 500
        
        # Get auth instance
        auth = get_zerodha_auth_web()
        
        # Check connection
        connected = auth.is_connected()
        
        if connected:
            # Get session info
            session_info = auth.get_session_info()
            
            return jsonify({
                'success': True,
                'connected': True,
                'broker': 'Zerodha',
                'user_id': session_info.get('user_id'),
                'user_name': session_info.get('user_name'),
                'email': session_info.get('email'),
                'login_time': session_info.get('login_time'),
                'expiry_date': session_info.get('expiry_date')
            }), 200
        
        else:
            return jsonify({
                'success': True,
                'connected': False,
                'broker': None,
                'message': 'Not connected to any broker'
            }), 200
    
    except Exception as e:
        logger.error(f"Failed to check broker status: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to check status: {str(e)}'
        }), 500


@broker_bp.route('/logout', methods=['POST'])
def broker_logout():
    """
    Logout from broker and clear session.
    
    Returns:
        JSON status response
        
    Usage:
        fetch('/api/broker/logout', { method: 'POST' })
    """
    try:
        logger.info("Logout requested")
        
        # Import auth module
        try:
            from trading.zerodha_auth_web import get_zerodha_auth_web
        except ImportError as e:
            logger.error(f"Failed to import auth module: {e}")
            return jsonify({
                'success': False,
                'message': f'Authentication module not found: {str(e)}'
            }), 500
        
        # Get auth instance
        auth = get_zerodha_auth_web()
        
        # Logout
        auth.logout()
        
        logger.info("✅ Logged out successfully")
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Logout failed: {str(e)}'
        }), 500


@broker_bp.route('/info', methods=['GET'])
def broker_info():
    """
    Get detailed broker connection information.
    
    Returns:
        JSON with session details
        
    Response:
        {
            "connected": true,
            "broker": "Zerodha",
            "session": {
                "user_id": "ABC123",
                "user_name": "John Doe",
                "login_time": "2026-03-17T10:30:00",
                "expiry_date": "2026-03-18T10:30:00"
            }
        }
    """
    try:
        # Import auth module
        try:
            from trading.zerodha_auth_web import get_zerodha_auth_web
        except ImportError as e:
            logger.error(f"Failed to import auth module: {e}")
            return jsonify({
                'success': False,
                'message': f'Authentication module not found: {str(e)}'
            }), 500
        
        # Get auth instance
        auth = get_zerodha_auth_web()
        
        # Get session info
        session_info = auth.get_session_info()
        
        if session_info:
            return jsonify({
                'success': True,
                'connected': True,
                'broker': 'Zerodha',
                'session': session_info
            }), 200
        
        else:
            return jsonify({
                'success': True,
                'connected': False,
                'broker': None,
                'session': None
            }), 200
    
    except Exception as e:
        logger.error(f"Failed to get broker info: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Failed to get info: {str(e)}'
        }), 500


@broker_bp.route('/profile', methods=['GET'])
def broker_profile():
    """
    Get broker account profile with margin details.
    
    Returns equity margin, commodity margin, and user profile.
    
    Response:
        {
            "status": "success",
            "data": {
                "user_id": "ABC123",
                "user_name": "John Doe",
                "equity": { "available_cash": 95000, ... },
                "commodity": { ... }
            }
        }
    
    Usage:
        Frontend BalanceWidget calls this on mount
    """
    try:
        # Try to get an authenticated kite instance
        kite = None
        
        # Method 1: Use web auth (zerodha_auth_web)
        try:
            from trading.zerodha_auth_web import get_zerodha_auth_web
            auth = get_zerodha_auth_web()
            if auth.is_connected():
                kite = auth.get_kite_client()
        except Exception as e:
            logger.debug(f"Web auth not available: {e}")
        
        # Method 2: Fallback to CLI auth manager (config/zerodha_token.json)
        if kite is None:
            try:
                from trading.zerodha_auth_manager import get_kite_client
                kite = get_kite_client(auto_renew=False)
            except Exception as e:
                logger.debug(f"CLI auth not available: {e}")
        
        if kite is None:
            return jsonify({
                'status': 'error',
                'message': 'Session expired, please re-login.'
            }), 401
        
        # Fetch margins and profile
        margins = kite.margins()
        profile = kite.profile()
        
        equity = margins.get('equity', {})
        commodity = margins.get('commodity', {})
        
        return jsonify({
            'status': 'success',
            'data': {
                'user_id': profile.get('user_id'),
                'user_name': profile.get('user_name'),
                'email': profile.get('email', ''),
                'broker': profile.get('broker', 'ZERODHA'),
                'equity': {
                    'available_cash': equity.get('available', {}).get('cash', 0),
                    'available_margin': equity.get('available', {}).get('live_balance', 0),
                    'used_margin': equity.get('utilised', {}).get('debits', 0),
                    'net': equity.get('net', 0),
                },
                'commodity': {
                    'available_cash': commodity.get('available', {}).get('cash', 0),
                    'available_margin': commodity.get('available', {}).get('live_balance', 0),
                    'used_margin': commodity.get('utilised', {}).get('debits', 0),
                    'net': commodity.get('net', 0),
                },
                'timestamp': datetime.now().isoformat()
            }
        })
    
    except Exception as e:
        logger.error(f"Broker profile fetch failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Session expired, please re-login.'
        }), 401
