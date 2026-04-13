"""User preferences and profile API routes."""

import os
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db, User, UserPrefs, Resume, RemotePreference
from .auth import get_current_user
from ..services.sheets import GoogleSheetsLogger

router = APIRouter()


# Request/Response models
class PreferencesResponse(BaseModel):
    job_titles: list[str]
    locations: list[str]
    salary_min: Optional[int]
    work_auth: Optional[str]
    remote_pref: str
    generate_cover_letter: bool
    run_hour_1: int
    run_hour_2: int
    sheets_id: Optional[str]

    class Config:
        from_attributes = True


class PreferencesUpdate(BaseModel):
    job_titles: Optional[list[str]] = None
    locations: Optional[list[str]] = None
    salary_min: Optional[int] = None
    work_auth: Optional[str] = None
    remote_pref: Optional[str] = None
    generate_cover_letter: Optional[bool] = None
    run_hour_1: Optional[int] = None
    run_hour_2: Optional[int] = None


class ResumeResponse(BaseModel):
    id: int
    filename: str
    is_primary: bool
    uploaded_at: datetime

    class Config:
        from_attributes = True


# Routes
@router.get("/prefs", response_model=PreferencesResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user preferences."""
    prefs = db.query(UserPrefs).filter(UserPrefs.user_id == current_user.id).first()

    if not prefs:
        # Create default preferences
        prefs = UserPrefs(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)

    return PreferencesResponse(
        job_titles=prefs.job_titles or [],
        locations=prefs.locations or [],
        salary_min=prefs.salary_min,
        work_auth=prefs.work_auth,
        remote_pref=prefs.remote_pref.value if prefs.remote_pref else "any",
        generate_cover_letter=prefs.generate_cover_letter,
        run_hour_1=prefs.run_hour_1,
        run_hour_2=prefs.run_hour_2,
        sheets_id=prefs.sheets_id,
    )


@router.put("/prefs", response_model=PreferencesResponse)
async def update_preferences(
    update: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user preferences."""
    prefs = db.query(UserPrefs).filter(UserPrefs.user_id == current_user.id).first()

    if not prefs:
        prefs = UserPrefs(user_id=current_user.id)
        db.add(prefs)

    # Update fields
    if update.job_titles is not None:
        prefs.job_titles = update.job_titles

    if update.locations is not None:
        prefs.locations = update.locations

    if update.salary_min is not None:
        prefs.salary_min = update.salary_min

    if update.work_auth is not None:
        prefs.work_auth = update.work_auth

    if update.remote_pref is not None:
        try:
            prefs.remote_pref = RemotePreference(update.remote_pref)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid remote preference: {update.remote_pref}",
            )

    if update.generate_cover_letter is not None:
        prefs.generate_cover_letter = update.generate_cover_letter

    if update.run_hour_1 is not None:
        if not 0 <= update.run_hour_1 <= 23:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="run_hour_1 must be between 0 and 23",
            )
        prefs.run_hour_1 = update.run_hour_1

    if update.run_hour_2 is not None:
        if not 0 <= update.run_hour_2 <= 23:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="run_hour_2 must be between 0 and 23",
            )
        prefs.run_hour_2 = update.run_hour_2

    db.commit()
    db.refresh(prefs)

    return PreferencesResponse(
        job_titles=prefs.job_titles or [],
        locations=prefs.locations or [],
        salary_min=prefs.salary_min,
        work_auth=prefs.work_auth,
        remote_pref=prefs.remote_pref.value if prefs.remote_pref else "any",
        generate_cover_letter=prefs.generate_cover_letter,
        run_hour_1=prefs.run_hour_1,
        run_hour_2=prefs.run_hour_2,
        sheets_id=prefs.sheets_id,
    )


@router.post("/resume", response_model=ResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    is_primary: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a resume file."""
    # Validate file type
    allowed_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be PDF or Word document",
        )

    # Check file size
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size must be less than {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # Create user upload directory
    user_dir = settings.UPLOADS_DIR / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    file_path = user_dir / filename

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # If setting as primary, unset other primaries
    if is_primary:
        db.query(Resume).filter(
            Resume.user_id == current_user.id,
            Resume.is_primary == True,
        ).update({"is_primary": False})

    # Create resume record
    resume = Resume(
        user_id=current_user.id,
        filename=file.filename,
        file_path=str(file_path),
        is_primary=is_primary,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    # TODO: Parse resume content for auto-fill
    # This would extract text from PDF/Word for Claude to use

    return ResumeResponse(
        id=resume.id,
        filename=resume.filename,
        is_primary=resume.is_primary,
        uploaded_at=resume.uploaded_at,
    )


@router.get("/resumes", response_model=list[ResumeResponse])
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List user's uploaded resumes."""
    resumes = db.query(Resume).filter(
        Resume.user_id == current_user.id
    ).order_by(Resume.uploaded_at.desc()).all()

    return [
        ResumeResponse(
            id=r.id,
            filename=r.filename,
            is_primary=r.is_primary,
            uploaded_at=r.uploaded_at,
        )
        for r in resumes
    ]


@router.delete("/resume/{resume_id}")
async def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a resume."""
    resume = db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.user_id == current_user.id,
    ).first()

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Delete file
    if os.path.exists(resume.file_path):
        os.remove(resume.file_path)

    db.delete(resume)
    db.commit()

    return {"message": "Resume deleted"}


@router.put("/resume/{resume_id}/primary")
async def set_primary_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set a resume as primary."""
    resume = db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.user_id == current_user.id,
    ).first()

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    # Unset other primaries
    db.query(Resume).filter(
        Resume.user_id == current_user.id,
        Resume.is_primary == True,
    ).update({"is_primary": False})

    resume.is_primary = True
    db.commit()

    return {"message": "Primary resume updated"}


@router.post("/sheets/create")
async def create_google_sheet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Google Sheet for application logging."""
    prefs = db.query(UserPrefs).filter(UserPrefs.user_id == current_user.id).first()

    if prefs and prefs.sheets_id:
        return {
            "message": "Sheet already exists",
            "sheets_id": prefs.sheets_id,
            "url": f"https://docs.google.com/spreadsheets/d/{prefs.sheets_id}",
        }

    logger = GoogleSheetsLogger()
    sheets_id = logger.create_sheet_for_user(
        user_email=current_user.email,
        user_name=current_user.email.split("@")[0],
    )

    if not sheets_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create Google Sheet",
        )

    if not prefs:
        prefs = UserPrefs(user_id=current_user.id)
        db.add(prefs)

    prefs.sheets_id = sheets_id
    db.commit()

    return {
        "message": "Sheet created successfully",
        "sheets_id": sheets_id,
        "url": f"https://docs.google.com/spreadsheets/d/{sheets_id}",
    }
