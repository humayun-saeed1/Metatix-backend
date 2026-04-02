from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# This is the "Address" of your Postgres warehouse
DATABASE_URL = settings.DB_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# This 'Base' is what all your tables will inherit from
Base = declarative_base()

# Add this new function at the bottom:
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()