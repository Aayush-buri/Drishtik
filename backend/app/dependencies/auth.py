from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import InvalidTokenError

from app.db.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.case import Case, CaseMember, RoleEnum

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def require_authenticated_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return current_user

def require_case_member(case_identifier: str = None, case_id: int = None, current_user: User = Depends(require_authenticated_user), db: Session = Depends(get_db)) -> CaseMember:
    if case_identifier:
        case = db.query(Case).filter(Case.case_identifier == case_identifier).first()
        if not case and case_identifier.isdigit():
            case = db.query(Case).filter(Case.id == int(case_identifier)).first()
    elif case_id:
        case = db.query(Case).filter(Case.id == case_id).first()
    else:
        raise HTTPException(status_code=400, detail="Must provide case_id or case_identifier")
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    member = db.query(CaseMember).filter(CaseMember.case_id == case.id, CaseMember.user_id == current_user.id, CaseMember.status == "ACTIVE").first()
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to access this case")
    member.case = case
    return member

def require_case_admin(member: CaseMember = Depends(require_case_member)) -> CaseMember:
    if member.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return member

def require_case_investigator_or_admin(member: CaseMember = Depends(require_case_member)) -> CaseMember:
    if member.role not in (RoleEnum.ADMIN, RoleEnum.INVESTIGATOR):
        raise HTTPException(status_code=403, detail="Investigator privileges required")
    return member

