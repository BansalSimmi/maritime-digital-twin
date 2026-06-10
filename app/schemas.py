from pydantic import BaseModel, EmailStr
from typing import Optional
# from uuid import UUID
from datetime import datetime

#Schemas ≠ Database Tables
#Schemas control API data validation.

#POST /users/signup
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "user"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[str] = None


#Used when returning data.
#from_attributes = True -->  This allows: SQLAlchemy object → JSON response (Without manual conversion.)
class UserResponse(BaseModel):
    account_id: int
    name: str
    email: EmailStr
    role: str
    created_at: datetime

    class Config:
        from_attributes = True