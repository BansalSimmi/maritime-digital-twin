# from sqlalchemy import Column, String, Text, DateTime, Enum
from sqlalchemy import *
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
# from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
# import uuid

from app.database import Base

#Account Table
class Account(Base):
    __tablename__ = "accounts"

    # account_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(Enum("admin", "user", name="role_enum"), default="user") #Only two roles allowed.
    created_at = Column(DateTime(timezone=True), server_default=func.now())