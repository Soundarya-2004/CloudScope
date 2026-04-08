from sqlalchemy import Column, Integer, String, Boolean
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="View-only") # Admin or View-only

class UserSetting(Base):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    aws_access_key = Column(String, index=True)
    aws_secret_key = Column(String)  # This will be encrypted
    aws_region = Column(String, default="us-east-1")
    is_configured = Column(Boolean, default=False)
