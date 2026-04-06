from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
import datetime
import os

Base = declarative_base()

class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
    symbol = Column(String, index=True)
    qty = Column(Integer)
    price = Column(Float)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

# Configure SQLite DB (Store in backend folder)
db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "trades.db")
engine = create_engine(
    f"sqlite:///{db_path}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
