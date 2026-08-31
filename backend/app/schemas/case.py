from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from app.models.case import RoleEnum
from app.schemas.user import UserResponse

class CaseBase(BaseModel):
    name: str
    description: Optional[str] = None
    case_type: Optional[str] = None

class CaseCreate(CaseBase):
    username: str
    password: str
    display_name: str

class CaseResponse(CaseBase):
    id: int
    case_identifier: str
    status: str
    created_at: datetime
    updated_at: datetime
    role: Optional[RoleEnum] = None
    
    model_config = ConfigDict(from_attributes=True)

class CaseMemberBase(BaseModel):
    role: RoleEnum

class CaseMemberCreate(CaseMemberBase):
    username: str
    display_name: str
    password: Optional[str] = None

class CaseMemberResponse(CaseMemberBase):
    id: int
    case_id: int
    user_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    user: UserResponse
    
    model_config = ConfigDict(from_attributes=True)
