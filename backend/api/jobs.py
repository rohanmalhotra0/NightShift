"""Jobs API routes."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db, User, UserPrefs, Job, Application
from api.auth import get_current_user

router = APIRouter()


# Response models
class JobResponse(BaseModel):
    id: str
    source: str
    title: str
    company: str
    location: Optional[str]
    url: str
    salary_range: Optional[str]
    job_type: Optional[str]
    is_easy_apply: bool
    scraped_at: datetime
    has_applied: bool = False

    class Config:
        from_attributes = True


class JobDetailResponse(JobResponse):
    description: Optional[str]
    external_id: str


class JobsListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    page: int
    per_page: int


# Routes
@router.get("", response_model=JobsListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    location: Optional[str] = None,
    source: Optional[str] = None,
    easy_apply_only: bool = False,
    hide_applied: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List jobs matching user preferences.

    Query parameters:
    - page: Page number (default 1)
    - per_page: Results per page (default 20, max 100)
    - search: Search in title and company
    - location: Filter by location
    - source: Filter by source (linkedin, indeed, etc.)
    - easy_apply_only: Only show Easy Apply jobs
    - hide_applied: Hide jobs already applied to
    """
    # Base query
    query = db.query(Job).filter(
        Job.scraped_at >= datetime.utcnow() - timedelta(days=14)
    )

    # Get user preferences for matching
    prefs = db.query(UserPrefs).filter(UserPrefs.user_id == current_user.id).first()

    # Apply user preference filters if no explicit search
    if not search and prefs and prefs.job_titles:
        title_filters = [Job.title.ilike(f"%{t}%") for t in prefs.job_titles]
        query = query.filter(or_(*title_filters))

    if not location and prefs and prefs.locations:
        loc_filters = [Job.location.ilike(f"%{loc}%") for loc in prefs.locations]
        query = query.filter(or_(*loc_filters))

    # Apply explicit filters
    if search:
        query = query.filter(
            or_(
                Job.title.ilike(f"%{search}%"),
                Job.company.ilike(f"%{search}%"),
            )
        )

    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))

    if source:
        query = query.filter(Job.source == source.lower())

    if easy_apply_only:
        query = query.filter(Job.is_easy_apply == True)

    # Hide applied jobs
    if hide_applied:
        applied_ids = db.query(Application.job_id).filter(
            Application.user_id == current_user.id
        ).scalar_subquery()
        query = query.filter(Job.id.notin_(applied_ids))

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * per_page
    jobs = query.order_by(Job.scraped_at.desc()).offset(offset).limit(per_page).all()

    # Get applied job IDs for this batch
    job_ids = [j.id for j in jobs]
    applied_set = set(
        a[0] for a in db.query(Application.job_id).filter(
            Application.user_id == current_user.id,
            Application.job_id.in_(job_ids),
        ).all()
    )

    # Build response
    job_responses = [
        JobResponse(
            id=j.id,
            source=j.source,
            title=j.title,
            company=j.company,
            location=j.location,
            url=j.url,
            salary_range=j.salary_range,
            job_type=j.job_type,
            is_easy_apply=j.is_easy_apply,
            scraped_at=j.scraped_at,
            has_applied=j.id in applied_set,
        )
        for j in jobs
    ]

    return JobsListResponse(
        jobs=job_responses,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get job details."""
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Check if applied
    applied = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.job_id == job_id,
    ).first()

    return JobDetailResponse(
        id=job.id,
        source=job.source,
        external_id=job.external_id,
        title=job.title,
        company=job.company,
        location=job.location,
        url=job.url,
        description=job.description,
        salary_range=job.salary_range,
        job_type=job.job_type,
        is_easy_apply=job.is_easy_apply,
        scraped_at=job.scraped_at,
        has_applied=applied is not None,
    )


@router.get("/sources/list")
async def list_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List available job sources."""
    sources = db.query(Job.source).distinct().all()
    return {"sources": [s[0] for s in sources]}


@router.get("/stats/summary")
async def job_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get job statistics for the user."""
    # Get user preferences
    prefs = db.query(UserPrefs).filter(UserPrefs.user_id == current_user.id).first()

    # Total matching jobs
    query = db.query(Job).filter(
        Job.scraped_at >= datetime.utcnow() - timedelta(days=7)
    )

    if prefs and prefs.job_titles:
        title_filters = [Job.title.ilike(f"%{t}%") for t in prefs.job_titles]
        query = query.filter(or_(*title_filters))

    total_matching = query.count()

    # Jobs scraped today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = db.query(Job).filter(Job.scraped_at >= today_start).count()

    # Applied jobs
    applied_ids = db.query(Application.job_id).filter(
        Application.user_id == current_user.id
    ).scalar_subquery()

    unapplied_matching = query.filter(Job.id.notin_(applied_ids)).count()

    return {
        "total_matching_jobs": total_matching,
        "new_jobs_today": new_today,
        "unapplied_matching": unapplied_matching,
    }
