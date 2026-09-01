import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.database import get_db
from app.models.user import User
from app.models.case import Case, CaseMember, RoleEnum
from app.schemas.case import CaseCreate, CaseResponse
from app.schemas.user import UserCreate
from app.core.security import get_password_hash
from app.dependencies.auth import require_authenticated_user, require_case_member

router = APIRouter()

@router.post("", response_model=CaseResponse)
def create_case(case_in: CaseCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == case_in.username).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already exists")

    case_identifier = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    
    db_user = User(
        username=case_in.username,
        password_hash=get_password_hash(case_in.password),
        display_name=case_in.display_name
    )
    db.add(db_user)
    
    try:
        db.flush()
        db_case = Case(
            case_identifier=case_identifier,
            name=case_in.name,
            description=case_in.description,
            case_type=case_in.case_type,
            created_by=db_user.id
        )
        db.add(db_case)
        db.flush()
        
        db_member = CaseMember(
            case_id=db_case.id,
            user_id=db_user.id,
            role=RoleEnum.ADMIN
        )
        db.add(db_member)
        db.commit()
        db.refresh(db_case)
        db.refresh(db_member)
        db_case.role = db_member.role
        return db_case
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Database conflict")

@router.get("", response_model=List[CaseResponse])
def list_cases(db: Session = Depends(get_db)):
    # Local desktop app: return all cases. Specific case access requires authentication.
    return db.query(Case).all()

@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: int, current_user: User = Depends(require_authenticated_user), db: Session = Depends(get_db)):
    member = db.query(CaseMember).filter(CaseMember.case_id == case_id, CaseMember.user_id == current_user.id, CaseMember.status == "ACTIVE").first()
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to access this case")
    
    case = member.case
    case.role = member.role
    return case
