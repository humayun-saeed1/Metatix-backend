import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 1. Get the URL and fix the 'postgres' vs 'postgresql' prefix
DATABASE_URL = settings.DB_URL
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 2. Upgrade the Engine with SSL and Connection Pinging
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,           # Fixes "SSL connection closed"
    pool_recycle=300,             # Refreshes connection every 5 mins
    connect_args={"sslmode": "require"}  # Required for Railway
)

# --- THE REST STAYS THE SAME ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()