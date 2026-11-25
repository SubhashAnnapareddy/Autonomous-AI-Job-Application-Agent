from datetime import datetime
from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.models.resume import Resume
from app.models.user import User
from app.services.resume_intelligence import analyze_resume_file, analyze_resume, extract_resume_text


router = APIRouter(prefix="/api/resumes", tags=["Resumes"])

UPLOAD_DIR = Path("uploads/resumes")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload")
def upload_resume(
    name: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    original_name = file.filename or ""
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are allowed")

    filename = f"{current_user.id}_{uuid4().hex}{extension}"
    file_path = UPLOAD_DIR / filename
    size = 0

    try:
        with file_path.open("wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(status_code=413, detail="Resume file must be 10 MB or smaller")
                buffer.write(chunk)
    except Exception:
        if file_path.exists():
            file_path.unlink()
        raise

    try:
        extracted_text, analysis = analyze_resume_file(str(file_path))
    except Exception:
        if file_path.exists():
            file_path.unlink()
        raise

    resume = Resume(
        user_id=current_user.id,
        name=name.strip() or Path(original_name).stem,
        file_path=str(file_path),
        extracted_text=extracted_text,
        analysis_json=analysis,
        analyzed_at=datetime.utcnow(),
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    return {
        "message": analysis.get("warning")
        or "Resume uploaded, analyzed, and is ready for job matching.",
        "resume": {
            "id": resume.id,
            "name": resume.name,
            "file_path": resume.file_path,
            "user_id": resume.user_id,
            "analysis": resume.analysis_json,
        },
    }


@router.get("")
def get_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resumes = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.id.desc())
        .all()
    )
    return {
        "resumes": [
            {
                "id": resume.id,
                "name": resume.name,
                "file_path": resume.file_path,
                "extracted_text": resume.extracted_text,
                "analysis": resume.analysis_json,
                "analyzed_at": resume.analyzed_at,
            }
            for resume in resumes
        ]
    }


@router.post("/{resume_id}/analyze")
def analyze_uploaded_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    text = extract_resume_text(resume.file_path)
    analysis = analyze_resume(text)
    resume.extracted_text = text
    resume.analysis_json = analysis
    resume.analyzed_at = datetime.utcnow()
    db.commit()
    db.refresh(resume)

    return {
        "message": analysis.get("warning") or "Resume analyzed successfully",
        "resume_id": resume.id,
        "analysis": resume.analysis_json,
        "analyzed_at": resume.analyzed_at,
    }


@router.get("/{resume_id}/analysis")
def get_resume_analysis(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.analysis_json is None:
        raise HTTPException(status_code=404, detail="Resume has not been analyzed yet")
    return {
        "resume_id": resume.id,
        "analysis": resume.analysis_json,
        "analyzed_at": resume.analyzed_at,
    }


@router.delete("/{resume_id}")
def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = (
        db.query(Resume)
        .filter(Resume.id == resume_id, Resume.user_id == current_user.id)
        .first()
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.applications:
        raise HTTPException(status_code=409, detail="Resume cannot be deleted because it is linked to an application")

    file_path = Path(resume.file_path)
    db.delete(resume)
    db.commit()
    if file_path.is_file():
        file_path.unlink()

    return {"message": "Resume deleted successfully", "resume_id": resume_id}
