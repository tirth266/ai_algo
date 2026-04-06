"""
SQLAlchemy Base Model

Declarative base for all database models.
Provides common functionality and metadata.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData

# Define naming convention for constraints
metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

# Create declarative base
Base = declarative_base(metadata=metadata)


# Common mixin for additional functionality
class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    
    from sqlalchemy import Column, DateTime
    from datetime import datetime
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


if __name__ == "__main__":
    print("✓ SQLAlchemy Base model created successfully")
    print(f"✓ Metadata naming convention configured")
