from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.database import get_db
from app.models.user import User
from app.models.case import Case, CaseMember, RoleEnum
from app.schemas.case import CaseMemberCreate, CaseMemberResponse, CaseMemberBase
from app.core.security import get_password_hash
from app.dependencies.auth import require_authenticated_user, require_case_admin, require_case_investigator_or_admin

router = APIRouter()

@router.get("/{case_id}/members", response_model=List[CaseMemberResponse])
def list_members(case_id: int, current_member: CaseMember = Depends(require_case_investigator_or_admin), db: Session = Depends(get_db)):
    members = db.query(CaseMember).filter(CaseMember.case_id == case_id, CaseMember.status == "ACTIVE").all()
    return members

@router.post("/{case_id}/members", response_model=CaseMemberResponse)
def add_member(case_id: int, member_in: CaseMemberCreate, current_admin: CaseMember = Depends(require_case_admin), db: Session = Depends(get_db)):
    # Check if user already exists
    user = db.query(User).filter(User.username == member_in.username).first()
    
    if user:
        # Check if already a member
        existing_member = db.query(CaseMember).filter(CaseMember.case_id == case_id, CaseMember.user_id == user.id).first()
        if existing_member:
            if existing_member.status == "ACTIVE":
                raise HTTPException(status_code=409, detail="User is already a member of this case")
            else:
                existing_member.status = "ACTIVE"
                existing_member.role = member_in.role
                db.commit()
                db.refresh(existing_member)
                return existing_member
    else:
        # Create new user
        if not member_in.password:
            raise HTTPException(status_code=422, detail="Password is required for new users")
        user = User(
            username=member_in.username,
            display_name=member_in.display_name,
            password_hash=get_password_hash(member_in.password)
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Database conflict")

    # Add member
    new_member = CaseMember(
        case_id=case_id,
        user_id=user.id,
        role=member_in.role
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    return new_member

@router.delete("/{case_id}/members/{user_id}")
def remove_member(case_id: int, user_id: int, current_admin: CaseMember = Depends(require_case_admin), db: Session = Depends(get_db)):
    # Cannot remove yourself if you're the only admin
    if current_admin.user_id == user_id:
        # Check if there are other admins
        other_admins = db.query(CaseMember).filter(
            CaseMember.case_id == case_id, 
            CaseMember.role == RoleEnum.ADMIN,
            CaseMember.status == "ACTIVE",
            CaseMember.user_id != user_id
        ).count()
        if other_admins == 0:
            raise HTTPException(status_code=403, detail="Cannot remove the final case administrator")
            
    member = db.query(CaseMember).filter(CaseMember.case_id == case_id, CaseMember.user_id == user_id, CaseMember.status == "ACTIVE").first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
        
    member.status = "INACTIVE"
    db.commit()
    return {"message": "Member removed"}

@router.put("/{case_id}/members/{user_id}/role", response_model=CaseMemberResponse)
def change_role(case_id: int, user_id: int, role_in: CaseMemberBase, current_admin: CaseMember = Depends(require_case_admin), db: Session = Depends(get_db)):
    # Cannot demote yourself if you're the only admin
    if current_admin.user_id == user_id and role_in.role != RoleEnum.ADMIN:
        other_admins = db.query(CaseMember).filter(
            CaseMember.case_id == case_id, 
            CaseMember.role == RoleEnum.ADMIN,
            CaseMember.status == "ACTIVE",
            CaseMember.user_id != user_id
        ).count()
        if other_admins == 0:
            raise HTTPException(status_code=403, detail="Cannot demote the final case administrator")

    member = db.query(CaseMember).filter(CaseMember.case_id == case_id, CaseMember.user_id == user_id, CaseMember.status == "ACTIVE").first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
        
    member.role = role_in.role
    db.commit()
    db.refresh(member)
    return member
