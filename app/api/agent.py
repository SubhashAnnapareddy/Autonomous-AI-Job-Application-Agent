import base64
import hashlib
import hmac
import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.database.connection import get_db
from app.models.application import Application
from app.models.job import Job
from app.models.profile import Profile
from app.models.resume import Resume
from app.models.user import User
from app.services.application_agent import ApplicationAgent
from app.services.greenhouse import submit_application as submit_greenhouse_application
from app.services.job_agent import discover_and_match
from app.services.resume_intelligence import analyze_resume_file

application_agent = ApplicationAgent()

SUPPORTED_PLATFORMS = {"Remotive", "Arbeitnow", "Greenhouse"}
RECOMMENDATION_TOKEN_TTL = 600


router = APIRouter(prefix="/api/agent", tags=["AI Agent"])


class JobRecommendation(BaseModel):
    source_job_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    description: str | None = None
    application_url: HttpUrl
    platform: str = Field(min_length=1, max_length=100)


class ApplyRecommendationRequest(BaseModel):
    job: JobRecommendation
    resume_id: int
    match_score: float = Field(ge=0, le=100)
    recommendation_token: str = Field(min_length=1)


def _encode_token_part(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _recommendation_token(item: dict, user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "job": JobRecommendation.model_validate(item["job"]).model_dump(mode="json"),
        "resume_id": item["resume"].id,
        "match_score": float(item["score"]),
        "expires_at": int(time.time()) + RECOMMENDATION_TOKEN_TTL,
    }
    encoded_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(settings.secret_key.encode(), encoded_payload, hashlib.sha256).digest()
    return f"{_encode_token_part(encoded_payload)}.{_encode_token_part(signature)}"


def _validate_recommendation_token(request: ApplyRecommendationRequest, user_id: int) -> None:
    try:
        encoded_payload, encoded_signature = request.recommendation_token.split(".", 1)
        payload_bytes = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        expected_signature = hmac.new(settings.secret_key.encode(), payload_bytes, hashlib.sha256).digest()
        payload = json.loads(payload_bytes)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail="Invalid or expired job recommendation") from error

    job = request.job.model_dump(mode="json")
    matches_recommendation = (
        hmac.compare_digest(signature, expected_signature)
        and payload.get("user_id") == user_id
        and payload.get("job") == job
        and payload.get("resume_id") == request.resume_id
        and payload.get("match_score") == float(request.match_score)
        and payload.get("expires_at", 0) > int(time.time())
    )
    if not matches_recommendation:
        raise HTTPException(status_code=400, detail="Invalid or expired job recommendation")


def _recommendation_response(item: dict, user_id: int) -> dict:
    job = item["job"]
    resume = item["resume"]
    return {
        "job": {
            **job,
        },
        "match_score": item["score"],
        "matched_terms": item["matched_terms"],
        "selected_resume": {"id": resume.id, "name": resume.name},
        "recommendation_token": _recommendation_token(item, user_id),
    }


def _submit_saved_application(
    application: Application,
    resume: Resume,
    profile: Profile | None,
    current_user: User,
    db: Session,
) -> dict:
    if application.status == "applied":
        return {
            "message": "This application is already recorded as applied.",
            "submitted": True,
            "attempted": True,
            "status": application.status,
        }

    applicant = {
        "full_name": profile.full_name if profile else None,
        "email": current_user.email,
        "phone": profile.phone if profile else None,
        "location": profile.location if profile else None,
    }
    if application.job and application.job.platform == "Greenhouse":
        greenhouse_result = submit_greenhouse_application(
            board_token=settings.greenhouse_board_token,
            api_key=settings.greenhouse_api_key,
            job_id=application.job.source_job_id or "",
            resume_path=resume.file_path,
            applicant=applicant,
        )
        result = {
            "message": greenhouse_result.message,
            "submitted": greenhouse_result.submitted,
            "attempted": greenhouse_result.attempted,
        }
    else:
        browser_result = application_agent.submit_application(
            application_url=application.application_url or "",
            resume_path=resume.file_path,
            applicant=applicant,
        )
        result = {
            "message": browser_result.message,
            "submitted": browser_result.submitted,
            "attempted": browser_result.attempted,
        }
    if result["submitted"]:
        application.status = "applied"
        application.applied_at = datetime.utcnow()
    db.commit()

    return {
        "message": result["message"],
        "submitted": result["submitted"],
        "attempted": result["attempted"],
        "status": application.status,
    }


@router.post("/run")
def run_agent(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    resumes = db.query(Resume).filter(Resume.user_id == current_user.id).all()

    if not resumes:
        raise HTTPException(status_code=400, detail="Upload at least one resume first")

    analyzed_resumes = False
    analysis_warnings = []
    for resume in resumes:
        if resume.extracted_text and resume.analysis_json:
            warning = (resume.analysis_json or {}).get("warning")
            if warning:
                analysis_warnings.append(f"{resume.name}: {warning}")
            continue
        resume.extracted_text, resume.analysis_json = analyze_resume_file(resume.file_path)
        resume.analyzed_at = datetime.utcnow()
        analyzed_resumes = True
        warning = (resume.analysis_json or {}).get("warning")
        if warning:
            analysis_warnings.append(f"{resume.name}: {warning}")
    if analyzed_resumes:
        db.commit()

    recommendations, source_errors = discover_and_match(profile, resumes)

    return {
        "message": "Job discovery and matching completed. Apply to save a job to your applications.",
        "source_errors": source_errors,
        "analysis_warnings": analysis_warnings,
        "recommendations": [
            _recommendation_response(item, current_user.id)
            for item in recommendations
        ],
    }


@router.get("/jobs")
def list_discovered_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = db.query(Job).order_by(Job.id.desc()).limit(100).all()
    return {
        "jobs": [
            {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "platform": job.platform,
                "application_url": job.application_url,
            }
            for job in jobs
        ]
    }


@router.post("/apply/{application_id}")
def launch_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = (
        db.query(Application)
        .filter(
            Application.id == application_id,
            Application.user_id == current_user.id,
        )
        .first()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if not application.application_url:
        raise HTTPException(status_code=409, detail="This job has no application URL")

    resume = (
        db.query(Resume)
        .filter(Resume.id == application.resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(status_code=409, detail="The selected resume is unavailable")
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    result = _submit_saved_application(application, resume, profile, current_user, db)
    return {
        "message": result["message"],
        "saved": True,
        "application_id": application.id,
        "application_url": application.application_url,
        "submitted": result["submitted"],
        "attempted": result["attempted"],
        "status": result["status"],
    }


@router.post("/apply")
def apply_to_recommendation(
    request: ApplyRecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_recommendation_token(request, current_user.id)
    job_data = request.job
    if job_data.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail="Unsupported job platform")

    resume = (
        db.query(Resume)
        .filter(Resume.id == request.resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Selected resume not found")

    job = (
        db.query(Job)
        .filter(
            Job.platform == job_data.platform,
            Job.source_job_id == job_data.source_job_id,
        )
        .first()
    )
    job_values = job_data.model_dump()
    job_values["application_url"] = str(job_data.application_url)
    if job is None:
        job = Job(**job_values)
        db.add(job)
        db.flush()
    else:
        for key, value in job_values.items():
            setattr(job, key, value)

    application = (
        db.query(Application)
        .filter(Application.user_id == current_user.id, Application.job_id == job.id)
        .first()
    )
    if application is None:
        application = Application(
            user_id=current_user.id,
            job_id=job.id,
            resume_id=resume.id,
            match_score=request.match_score,
            status="ready",
            application_url=job.application_url,
        )
        db.add(application)
    else:
        application.resume_id = resume.id
        application.match_score = request.match_score
        application.application_url = job.application_url
        if application.status in {"rejected", "withdrawn"}:
            application.status = "ready"
            application.applied_at = None

    db.commit()
    db.refresh(application)

    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    submission = _submit_saved_application(application, resume, profile, current_user, db)

    return {
        "message": submission["message"],
        "saved": True,
        "application_id": application.id,
        "application_url": application.application_url,
        "submitted": submission["submitted"],
        "attempted": submission["attempted"],
        "status": submission["status"],
    }
