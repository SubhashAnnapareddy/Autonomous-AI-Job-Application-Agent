import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.contact_message import ContactMessage


router = APIRouter(prefix="/api/contact", tags=["Contact"])


class ContactMessageRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    subject: str = Field(min_length=1, max_length=150)
    message: str = Field(min_length=10, max_length=3000)

    @field_validator("name", "subject", "message")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address")
        return value


@router.post("")
def submit_contact_message(
    data: ContactMessageRequest,
    db: Session = Depends(get_db),
):
    contact_message = ContactMessage(**data.model_dump())
    db.add(contact_message)
    db.commit()
    return {"message": "Your message has been saved for the project team."}
