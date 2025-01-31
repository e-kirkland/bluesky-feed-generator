from datetime import datetime
import os
from sqlalchemy import create_engine, Column, String, DateTime, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from server.config import SUPABASE_URL, SUPABASE_DB_PASSWORD

# Create database URL from Supabase credentials
DATABASE_URL = f"postgresql://postgres:{SUPABASE_DB_PASSWORD}@{SUPABASE_URL}:5432/postgres"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)

Base = declarative_base()

class Post(Base):
    __tablename__ = "posts"

    uri = Column(String, primary_key=True, index=True)
    cid = Column(String, nullable=False)
    reply_parent = Column(String, nullable=True)
    reply_root = Column(String, nullable=True)
    indexed_at = Column(DateTime, default=datetime.utcnow)

class SubscriptionState(Base):
    __tablename__ = "subscription_states"

    service = Column(String, primary_key=True)
    cursor = Column(BigInteger, nullable=False)

# Create all tables
Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
