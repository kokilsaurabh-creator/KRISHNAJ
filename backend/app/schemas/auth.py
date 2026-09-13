from pydantic import BaseModel, ConfigDict

from app.models import UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
