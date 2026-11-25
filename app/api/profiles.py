from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.models.profile import Profile
from app.models.user import User


router = APIRouter(prefix="/profiles", tags=["Profiles"])


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    phone: str | None = None
    location: str | None = None
    experience: str | None = None
    education: str | None = None
    preferred_roles: str | None = None
    preferred_locations: str | None = None


@router.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "username": current_user.username,
        "email": current_user.email,
        "full_name": profile.full_name,
        "phone": profile.phone,
        "location": profile.location,
        "experience": profile.experience,
        "education": profile.education,
        "preferred_roles": profile.preferred_roles,
        "preferred_locations": profile.preferred_locations,
    }


@router.put("/me")
def update_my_profile(
    data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.full_name = data.full_name
    profile.phone = data.phone
    profile.location = data.location
    profile.experience = data.experience
    profile.education = data.education
    profile.preferred_roles = data.preferred_roles
    profile.preferred_locations = data.preferred_locations

    db.commit()
    db.refresh(profile)

    return {"message": "Profile updated successfully", "profile": data.model_dump()}
