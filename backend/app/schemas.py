from pydantic import BaseModel
from typing import List, Optional

class AWSConfigCreate(BaseModel):
    aws_access_key: str
    aws_secret_key: str
    aws_region: str

class AWSConfigResponse(BaseModel):
    aws_access_key: str  # Masked
    aws_region: str
    is_configured: bool

class PredictorResponse(BaseModel):
    dates: list[str]
    historical_costs: list[Optional[float]]
    predicted_costs: list[Optional[float]]
    total_current_month: float = 0.0
    total_projected: float = 0.0
    services: dict[str, float] = {}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "View-only"

class UserResponse(BaseModel):
    username: str
    role: str

class S3Bucket(BaseModel):
    name: str
    creation_date: str
    size_mb: float = 0.0

class RDSInstance(BaseModel):
    id: str
    state: str
    engine: str
    size: str

class LambdaFunction(BaseModel):
    name: str
    runtime: str
    state: str
    last_modified: str
