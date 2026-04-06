"""
Database Session Manager

Provides session management for database operations.
Handles session creation, commit, rollback, and cleanup.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
import logging

from database.connection import get_engine

logger = logging.getLogger(__name__)


# Create session factory
SessionFactory = None


def get_session_factory():
    """
    Get or create session factory.
    
    Returns:
        SQLAlchemy SessionFactory
    """
    global SessionFactory
    
    if SessionFactory is None:
        engine = get_engine()
        SessionFactory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
    
    return SessionFactory


def get_scoped_session():
    """
    Get thread-local scoped session.
    
    Returns:
        SQLAlchemy Session
    """
    session_factory = get_session_factory()
    return scoped_session(session_factory)


@contextmanager
def session_scope():
    """
    Provide a transactional scope around a series of operations.
    
    This context manager ensures proper session cleanup:
    - Commits on success
    - Rollbacks on failure
    - Always closes session
    
    Yields:
        SQLAlchemy Session
    
    Example:
        >>> with session_scope() as session:
        ...     order = Order(symbol='RELIANCE', quantity=100)
        ...     session.add(order)
        ...     # Automatically commits on exit
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Database error, rolling back: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()


def get_session():
    """
    Get a new database session.
    
    This should be used for dependency injection in API endpoints.
    
    Yields:
        SQLAlchemy Session
    
    Example:
        >>> @app.route('/orders')
        >>> def get_orders():
        ...     session = next(get_session())
        ...     orders = session.query(Order).all()
        ...     return jsonify([o.to_dict() for o in orders])
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def close_all_sessions():
    """
    Close all active sessions.
    
    Call this during application shutdown.
    """
    global SessionFactory
    
    if SessionFactory is not None:
        SessionFactory.close_all()
        logger.info("All database sessions closed")


if __name__ == "__main__":
    # Test session management
    from models.base import Base
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing session management...")
    
    # Test session scope
    with session_scope() as session:
        result = session.execute("SELECT 1 as test")
        row = result.fetchone()
        print(f"✓ Session scope test successful: {row[0]}")
    
    print("\n✓ Session management working!")
