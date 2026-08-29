from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create database engine
# Note: For SQLite, we need connect_args={"check_same_thread": False} for FastAPI
engine_kwargs = {}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency to get a database session for a request.
    Yields a session and ensures it's closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
