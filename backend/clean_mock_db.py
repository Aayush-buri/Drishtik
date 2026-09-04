from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.models.evidence import Evidence
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

mock_files = ["test_vid.mp4", "v1.mp4", "v2.mp4"]
evidence_to_delete = db.query(Evidence).filter(Evidence.original_filename.in_(mock_files)).all()

for e in evidence_to_delete:
    print(f"Deleting {e.original_filename} (ID: {e.id})")
    db.delete(e)

db.commit()
db.close()
