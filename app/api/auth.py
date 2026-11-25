from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database.connection import get_db
from app.models.profile import Profile
from app.models.user import User
from app.schemas.auth import RegisterRequest


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        password_hash = hash_password(data.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    user = User(
        username=data.username.strip(),
        email=str(data.email).strip().lower(),
        password_hash=password_hash,
    )
    db.add(user)
    db.flush()

    profile = Profile(
        user_id=user.id,
        full_name=data.full_name,
        phone=data.phone,
        location=data.location,
        experience=data.experience,
        education=data.education,
        preferred_roles=data.preferred_roles,
        preferred_locations=data.preferred_locations,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    db.refresh(profile)

    return {
        "message": "Registration successful",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at,
        },
    }


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form_data.username).first()

    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(user.id)

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    }
