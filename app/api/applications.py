from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.models.application import Application
from app.models.user import User


router = APIRouter(prefix="/api/applications", tags=["Applications"])


@router.get("")
def list_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    applications = (
        db.query(Application)
        .filter(
            Application.user_id == current_user.id,
            Application.status.in_(("ready", "applied")),
        )
        .order_by(Application.id.desc())
        .all()
    )

    return {
        "applications": [
            {
                "id": item.id,
                "job_id": item.job_id,
                "job_title": item.job.title if item.job else None,
                "company": item.job.company if item.job else None,
                "location": item.job.location if item.job else None,
                "platform": item.job.platform if item.job else None,
                "resume_id": item.resume_id,
                "resume_name": item.resume.name if item.resume else None,
                "match_score": item.match_score,
                "status": item.status,
                "applied_at": item.applied_at,
                "application_url": item.application_url,
            }
            for item in applications
        ]
    }
