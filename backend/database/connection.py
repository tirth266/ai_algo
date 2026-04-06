"""
Database Connection Module

Handles PostgreSQL database connection and engine creation.
Manages connection pooling for optimal performance.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def get_database_url() -> str:
    """
    Get database URL from environment variable.
    
    Returns:
        Database URL string
    
    Raises:
        ValueError: If DATABASE_URL is not set
    """
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        # Default to SQLite for development if PostgreSQL not configured
        logger.warning("DATABASE_URL not set, using SQLite for development")
        return "sqlite:///./algo_trading.db"
    
    return database_url


def create_database_engine(
    pool_size: int = 10,
    max_overflow: int = 20,
    echo: bool = False
):
    """
    Create SQLAlchemy database engine with connection pooling.
    
    Args:
        pool_size: Number of connections to keep in pool (default: 10)
        max_overflow: Max connections above pool_size (default: 20)
        echo: Log SQL statements (default: False)
    
    Returns:
        SQLAlchemy Engine instance
    """
    database_url = get_database_url()
    
    logger.info(f"Creating database engine for: {database_url.split('@')[-1] if '@' in database_url else 'SQLite'}")
    
    try:
        # Create engine with connection pooling
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,   # Recycle connections after 1 hour
            echo=echo
        )
        
        # Test connection
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        
        logger.info("Database connection successful")
        return engine
        
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise


# Global engine instance
_engine = None


def get_engine():
    """
    Get or create global database engine instance.
    
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    
    if _engine is None:
        _engine = create_database_engine()
    
    return _engine


def init_db():
    """
    Initialize database by creating all tables.
    
    This should be called once at application startup.
    """
    from models.base import Base
    from models.order import Order
    from models.trade import Trade
    from models.position import Position
    from models.strategy_run import StrategyRun
    from models.equity_curve import EquityCurve
    
    engine = get_engine()
    
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization complete")


if __name__ == "__main__":
    # Test database connection
    logging.basicConfig(level=logging.INFO)
    
    print("Testing database connection...")
    engine = get_engine()
    
    print(f"✓ Engine created: {engine}")
    print(f"✓ Database URL: {get_database_url()}")
    
    # Test connection
    with engine.connect() as conn:
        result = conn.execute("SELECT 1 as test")
        row = result.fetchone()
        print(f"✓ Connection test successful: {row[0]}")
    
    print("\n✓ Database connection working!")
