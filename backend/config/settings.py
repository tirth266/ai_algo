"""
Central Configuration Manager

Loads and validates environment variables.
Provides global configuration access for the entire platform.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


class Config:
    """
    Central configuration class.
    
    All settings are loaded from environment variables.
    Provides type-safe access to configuration values.
    """
    
    # ========================================================================
    # DATABASE CONFIGURATION
    # ========================================================================
    
    @property
    def DATABASE_URL(self) -> str:
        """Get database URL."""
        url = os.getenv('DATABASE_URL')
        if not url:
            # Auto-construct from components
            db = os.getenv('POSTGRES_DB', 'algo_trading')
            user = os.getenv('POSTGRES_USER', 'postgres')
            password = os.getenv('POSTGRES_PASSWORD', 'securepassword123')
            port = os.getenv('DB_PORT', '5432')
            url = f"postgresql://{user}:{password}@localhost:{port}/{db}"
        return url
    
    @property
    def REDIS_URL(self) -> str:
        """Get Redis URL."""
        return os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # ========================================================================
    # ZERODHA BROKER CONFIGURATION
    # ========================================================================
    
    @property
    def ZERODHA_API_KEY(self) -> Optional[str]:
        """Get Zerodha API key."""
        return os.getenv('ZERODHA_API_KEY')
    
    @property
    def ZERODHA_API_SECRET(self) -> Optional[str]:
        """Get Zerodha API secret."""
        return os.getenv('ZERODHA_API_SECRET')
    
    @property
    def ZERODHA_USER_ID(self) -> Optional[str]:
        """Get Zerodha user ID."""
        return os.getenv('ZERODHA_USER_ID')
    
    @property
    def ZERODHA_PASSWORD(self) -> Optional[str]:
        """Get Zerodha password."""
        return os.getenv('ZERODHA_PASSWORD')
    
    @property
    def ZERODHA_TOTP_SECRET(self) -> Optional[str]:
        """Get Zerodha TOTP secret."""
        return os.getenv('ZERODHA_TOTP_SECRET')
    
    @property
    def ZERODHA_PRODUCT_TYPE(self) -> str:
        """Get default product type."""
        return os.getenv('ZERODHA_PRODUCT_TYPE', 'MIS')
    
    @property
    def ZERODHA_EXCHANGE(self) -> str:
        """Get default exchange."""
        return os.getenv('ZERODHA_EXCHANGE', 'NSE')
    
    # ========================================================================
    # TRADING CONFIGURATION
    # ========================================================================
    
    @property
    def TRADING_MODE(self) -> str:
        """Get trading mode (paper or live)."""
        return os.getenv('TRADING_MODE', 'paper').lower()
    
    @property
    def is_paper_trading(self) -> bool:
        """Check if paper trading mode."""
        return self.TRADING_MODE == 'paper'
    
    @property
    def MAX_RISK_PER_TRADE(self) -> float:
        """Get maximum risk per trade (as fraction of capital)."""
        return float(os.getenv('MAX_RISK_PER_TRADE', '0.02'))
    
    @property
    def MAX_DAILY_LOSS(self) -> float:
        """Get maximum daily loss (as fraction of capital)."""
        return float(os.getenv('MAX_DAILY_LOSS', '0.05'))
    
    @property
    def MAX_OPEN_POSITIONS(self) -> int:
        """Get maximum open positions allowed."""
        return int(os.getenv('MAX_OPEN_POSITIONS', '5'))
    
    @property
    def MAX_TRADES_PER_DAY(self) -> int:
        """Get maximum trades per day."""
        return int(os.getenv('MAX_TRADES_PER_DAY', '20'))
    
    @property
    def CAPITAL_PER_TRADE(self) -> float:
        """Get capital allocation per trade."""
        return float(os.getenv('CAPITAL_PER_TRADE', '50000'))
    
    # ========================================================================
    # SERVER CONFIGURATION
    # ========================================================================
    
    @property
    def BACKEND_PORT(self) -> int:
        """Get backend server port."""
        return int(os.getenv('BACKEND_PORT', '8000'))
    
    @property
    def FRONTEND_PORT(self) -> int:
        """Get frontend server port."""
        return int(os.getenv('FRONTEND_PORT', '3000'))
    
    @property
    def HOST(self) -> str:
        """Get server host."""
        return os.getenv('HOST', '0.0.0.0')
    
    @property
    def DEBUG(self) -> bool:
        """Check if debug mode enabled."""
        return os.getenv('DEBUG', 'false').lower() == 'true'
    
    # ========================================================================
    # LOGGING CONFIGURATION
    # ========================================================================
    
    @property
    def LOG_LEVEL(self) -> str:
        """Get logging level."""
        return os.getenv('LOG_LEVEL', 'INFO').upper()
    
    @property
    def LOG_FORMAT(self) -> str:
        """Get log format string."""
        return os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # ========================================================================
    # STRATEGY CONFIGURATION
    # ========================================================================
    
    @property
    def DEFAULT_STRATEGIES(self) -> list:
        """Get list of default strategies."""
        strategies = os.getenv('DEFAULT_STRATEGIES', 'LuxAlgoTrendlineStrategy')
        return [s.strip() for s in strategies.split(',')]
    
    @property
    def STRATEGY_RUN_INTERVAL(self) -> int:
        """Get strategy run interval in seconds."""
        return int(os.getenv('STRATEGY_RUN_INTERVAL', '300'))
    
    @property
    def MARKET_DATA_TIMEFRAME(self) -> str:
        """Get default market data timeframe."""
        return os.getenv('MARKET_DATA_TIMEFRAME', '5m')
    
    # ========================================================================
    # RISK MANAGEMENT
    # ========================================================================
    
    @property
    def STOP_LOSS_PERCENTAGE(self) -> float:
        """Get stop loss percentage."""
        return float(os.getenv('STOP_LOSS_PERCENTAGE', '2.0'))
    
    @property
    def TARGET_PERCENTAGE(self) -> float:
        """Get target profit percentage."""
        return float(os.getenv('TARGET_PERCENTAGE', '4.0'))
    
    @property
    def TRAILING_STOP_LOSS(self) -> bool:
        """Check if trailing stop loss enabled."""
        return os.getenv('TRAILING_STOP_LOSS', 'true').lower() == 'true'
    
    @property
    def MAX_PORTFOLIO_RISK(self) -> float:
        """Get maximum portfolio risk."""
        return float(os.getenv('MAX_PORTFOLIO_RISK', '0.10'))
    
    # ========================================================================
    # SECURITY
    # ========================================================================
    
    @property
    def SECRET_KEY(self) -> str:
        """Get Flask secret key."""
        return os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    @property
    def CORS_ORIGINS(self) -> list:
        """Get allowed CORS origins."""
        origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000')
        return [o.strip() for o in origins.split(',')]
    
    @property
    def ALLOWED_HOSTS(self) -> list:
        """Get allowed hosts."""
        hosts = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1')
        return [h.strip() for h in hosts.split(',')]
    
    # ========================================================================
    # VALIDATION
    # ========================================================================
    
    def validate(self) -> bool:
        """
        Validate required configuration.
        
        Returns:
            True if valid, raises exception otherwise
        
        Raises:
            ValueError: If required config missing
        """
        required_keys = []
        
        # Only require these keys in live trading mode
        if not self.is_paper_trading:
            required_keys.extend([
                'ZERODHA_API_KEY',
                'ZERODHA_API_SECRET',
                'ZERODHA_USER_ID'
            ])
        
        missing = [key for key in required_keys if not os.getenv(key)]
        
        if missing:
            error_msg = f"Missing required config keys: {', '.join(missing)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Configuration validated successfully")
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            'DATABASE_URL': self.DATABASE_URL,
            'REDIS_URL': self.REDIS_URL,
            'TRADING_MODE': self.TRADING_MODE,
            'MAX_RISK_PER_TRADE': self.MAX_RISK_PER_TRADE,
            'MAX_DAILY_LOSS': self.MAX_DAILY_LOSS,
            'MAX_OPEN_POSITIONS': self.MAX_OPEN_POSITIONS,
            'MAX_TRADES_PER_DAY': self.MAX_TRADES_PER_DAY,
            'CAPITAL_PER_TRADE': self.CAPITAL_PER_TRADE,
            'BACKEND_PORT': self.BACKEND_PORT,
            'FRONTEND_PORT': self.FRONTEND_PORT,
            'DEBUG': self.DEBUG,
            'LOG_LEVEL': self.LOG_LEVEL,
            'DEFAULT_STRATEGIES': self.DEFAULT_STRATEGIES,
            'STOP_LOSS_PERCENTAGE': self.STOP_LOSS_PERCENTAGE,
            'TARGET_PERCENTAGE': self.TARGET_PERCENTAGE,
        }


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance.
    
    Returns:
        Config instance
    """
    global _config
    
    if _config is None:
        _config = Config()
    
    return _config


def init_config() -> Config:
    """
    Initialize and validate configuration.
    
    Returns:
        Validated Config instance
    """
    global _config
    
    _config = Config()
    _config.validate()
    
    logger.info(f"Configuration initialized: Trading Mode={_config.TRADING_MODE}")
    
    return _config


if __name__ == "__main__":
    # Test configuration
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("CONFIGURATION TEST")
    print("=" * 60)
    
    config = get_config()
    
    print(f"\nDatabase URL: {config.DATABASE_URL.split('@')[-1] if '@' in config.DATABASE_URL else 'SQLite'}")
    print(f"Trading Mode: {config.TRADING_MODE}")
    print(f"Max Risk/Trade: {config.MAX_RISK_PER_TRADE:.1%}")
    print(f"Max Daily Loss: {config.MAX_DAILY_LOSS:.1%}")
    print(f"Max Open Positions: {config.MAX_OPEN_POSITIONS}")
    print(f"Capital/Trade: ₹{config.CAPITAL_PER_TRADE:,.0f}")
    print(f"Backend Port: {config.BACKEND_PORT}")
    print(f"Frontend Port: {config.FRONTEND_PORT}")
    print(f"Debug Mode: {config.DEBUG}")
    print(f"Default Strategies: {', '.join(config.DEFAULT_STRATEGIES)}")
    
    print("\n✓ Configuration test successful!")
