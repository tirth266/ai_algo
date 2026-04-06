"""
Trading Platform Backend Runner

Starts the Flask web application with all services.

Features:
- Loads environment variables
- Initializes database
- Starts Flask server with SocketIO
- Enables CORS for frontend communication

Usage:
    python run_backend.py
    
Or via npm:
    npm start (production)
    npm run dev (development with auto-reload)

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / '.env')
    print("[OK] Environment variables loaded")
except ImportError:
    print("[WARN] python-dotenv not installed, using system environment variables")

def ensure_directories():
    """Create necessary directories."""
    dirs = [
        project_root / 'logs',
        project_root / 'config',
    ]
    
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)

def setup_logging():
    """Setup logging configuration."""
    # Ensure logs directory exists first
    ensure_directories()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(project_root / 'logs' / 'backend.log', encoding='utf-8')
        ]
    )

# Setup logging (before anything else)
setup_logging()
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if required packages are installed."""
    missing = []
    
    try:
        import flask
    except ImportError:
        missing.append('flask')
    
    try:
        import flask_socketio
    except ImportError:
        missing.append('flask-socketio')
    
    try:
        import flask_cors
    except ImportError:
        missing.append('flask-cors')
    
    try:
        import kiteconnect
    except ImportError:
        missing.append('kiteconnect')
    
    if missing:
        logger.error(f"[ERROR] Missing dependencies: {missing}")
        logger.error(f"[ERROR] Install with: pip install {' '.join(missing)}")
        return False
    
    logger.info("[OK] All dependencies checked")
    return True

def check_zerodha_auth():
    """Verify Zerodha authentication is configured."""
    api_key = os.getenv('ZERODHA_API_KEY')
    api_secret = os.getenv('ZERODHA_API_SECRET')
    
    if not api_key or not api_secret:
        logger.warning("[WARN] Zerodha API credentials not found in .env")
        logger.warning("[WARN] Trading features will be limited")
        logger.warning("[INFO] Add credentials to .env file:")
        logger.warning("  ZERODHA_API_KEY=your_key")
        logger.warning("  ZERODHA_API_SECRET=your_secret")
        return False
    
    # Check if token exists
    token_file = project_root / 'config' / 'zerodha_token.json'
    
    if token_file.exists():
        logger.info("[OK] Zerodha token found")
        
        try:
            import json
            with open(token_file, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            
            if token_data.get('expiry_date'):
                from datetime import datetime
                expiry = datetime.fromisoformat(token_data['expiry_date'])
                
                if datetime.now() > expiry:
                    logger.warning("[WARN] Zerodha token expired")
                    logger.warning("[INFO] Run: python scripts/login_zerodha.py")
                else:
                    logger.info("[OK] Zerodha token valid")
            else:
                logger.info("[OK] Zerodha credentials configured")
        
        except Exception as e:
            logger.warning(f"Could not validate token: {str(e)}")
    else:
        logger.info("[INFO] No Zerodha token found (first-time setup)")
        logger.info("[INFO] Run: python scripts/login_zerodha.py")
    
    return True

def ensure_directories():
    """Create necessary directories."""
    dirs = [
        project_root / 'logs',
        project_root / 'config',
    ]
    
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    logger.info("[OK] Directories verified")

def setup_logging():
    """Setup logging configuration."""
    # Ensure logs directory exists first
    ensure_directories()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(project_root / 'logs' / 'backend.log', encoding='utf-8')
        ]
    )

def start_server(host='0.0.0.0', port=5000, debug=False):
    """Start the Flask server."""
    # Add webapp to path for imports
    webapp_path = project_root / 'webapp'
    if str(webapp_path) not in sys.path:
        sys.path.insert(0, str(webapp_path))
    
    from app import app, socketio
    
    logger.info("="*70)
    logger.info("TRADING PLATFORM BACKEND")
    logger.info("="*70)
    logger.info(f"[START] Starting server on http://{host}:{port}")
    logger.info(f"[WEBSOCKET] Enabled")
    logger.info(f"[DEBUG] Mode: {debug}")
    logger.info("="*70)
    
    try:
        # Run with SocketIO
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            use_reloader=debug,
            log_output=True
        )
    
    except KeyboardInterrupt:
        logger.info("\n👋 Server stopped by user")
    
    except Exception as e:
        logger.error(f"❌ Server error: {str(e)}")
        raise

def main():
    """Main entry point."""
    print("\n" + "="*70)
    print("TRADING PLATFORM BACKEND - STARTING")
    print("="*70 + "\n")
    
    # Check dependencies
    if not check_dependencies():
        print("\n[ERROR] Missing dependencies. Install with:")
        print("   pip install -r webapp/requirements.txt")
        sys.exit(1)
    
    # Ensure directories exist
    ensure_directories()
    
    # Check Zerodha auth
    check_zerodha_auth()
    
    # Get configuration from environment
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5000'))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    
    print(f"\n[INFO] Server Configuration:")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Debug: {debug}")
    print(f"\n[INFO] Frontend URL: http://localhost:{port}")
    print(f"\n[INFO] Press Ctrl+C to stop\n")
    
    # Start server
    try:
        start_server(host=host, port=port, debug=debug)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
