from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)

    full_name: str | None = Field(default=None, max_length=150)
    phone: str | None = None
    location: str | None = None
    experience: str | None = None
    education: str | None = None
    preferred_roles: str | None = None
    preferred_locations: str | None = None
