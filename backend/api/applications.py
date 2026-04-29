"""Applications API routes."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import (
    get_db, User, UserPrefs, Job, Application, Metric,
    ApplicationStatus, UserTier,
)
from api.auth import get_current_user, require_paid_user
from services.metrics import MetricsTracker
from bot.engine import run_application_batch

router = APIRouter()


# Tier limits
TIER_LIMITS = {
    UserTier.FREE: 0,
    UserTier.STARTER: 3,
    UserTier.PRO: 10,
    UserTier.MAX: 25,
}


# Response models
class ApplicationResponse(BaseModel):
    id: str
    job_id: Optional[str]
    job_title: str
    company: str
    status: str
    created_at: datetime
    submitted_at: Optional[datetime]
    error_log: Optional[str]

    class Config:
        from_attributes = True


class ApplicationDetailResponse(ApplicationResponse):
    job_url: str
    answers_json: Optional[dict]
    cover_letter_used: Optional[str]
    retry_count: int
    metrics: Optional[dict]


class ApplicationsListResponse(BaseModel):
    applications: list[ApplicationResponse]
    total: int
    page: int
    per_page: int


class StatsResponse(BaseModel):
    total_applications: int
    successful_applications: int
    failed_applications: int
    success_rate: float
    total_cost: float
    avg_duration_seconds: float


class ApplyRequest(BaseModel):
    job_ids: list[int]


# Routes
@router.get("", response_model=ApplicationsListResponse)
async def list_applications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List user's job applications.

    Query parameters:
    - page: Page number
    - per_page: Results per page
    - status_filter: Filter by status (pending, in_progress, submitted, failed, skipped)
    - days: Look back this many days
    """
    since = datetime.utcnow() - timedelta(days=days)

    query = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.created_at >= since,
    )

    if status_filter:
        valid_statuses = {s.value for s in ApplicationStatus}
        if status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )
        query = query.filter(Application.status == status_filter)

    total = query.count()

    offset = (page - 1) * per_page
    applications = query.order_by(
        Application.created_at.desc()
    ).offset(offset).limit(per_page).all()

    # Get job info
    job_ids = [a.job_id for a in applications]
    jobs = {j.id: j for j in db.query(Job).filter(Job.id.in_(job_ids)).all()}

    responses = []
    for app in applications:
        job = jobs.get(app.job_id)
        responses.append(ApplicationResponse(
            id=app.id,
            job_id=app.job_id,
            job_title=job.title if job else "Unknown",
            company=job.company if job else "Unknown",
            status=app.status if isinstance(app.status, str) else app.status.value,
            created_at=app.created_at,
            submitted_at=app.submitted_at,
            error_log=app.error_log,
        ))

    return ApplicationsListResponse(
        applications=responses,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/today")
async def get_today_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get today's applications summary."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    applications = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.created_at >= today_start,
    ).all()

    # Get tier limit
    limit = TIER_LIMITS.get(current_user.tier, 0)

    submitted = sum(1 for a in applications if a.status in ("submitted", ApplicationStatus.SUBMITTED))
    failed = sum(1 for a in applications if a.status in ("failed", ApplicationStatus.FAILED))
    pending = sum(1 for a in applications if a.status in ("pending", ApplicationStatus.PENDING))
    in_progress = sum(1 for a in applications if a.status in ("in_progress", ApplicationStatus.IN_PROGRESS))

    return {
        "submitted": submitted,
        "failed": failed,
        "pending": pending,
        "in_progress": in_progress,
        "total": len(applications),
        "daily_limit": limit,
        "remaining": max(0, limit - submitted),
    }


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get application statistics."""
    tracker = MetricsTracker()
    stats = tracker.get_user_stats(current_user.id, days=days)

    return StatsResponse(
        total_applications=stats.total_applications,
        successful_applications=stats.successful_applications,
        failed_applications=stats.failed_applications,
        success_rate=stats.success_rate,
        total_cost=stats.total_cost,
        avg_duration_seconds=stats.avg_duration_seconds,
    )


@router.get("/daily-stats")
async def get_daily_stats(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
):
    """Get daily application statistics."""
    tracker = MetricsTracker()
    daily = tracker.get_daily_stats(current_user.id, days=days)

    return {
        "stats": [
            {
                "date": d.date,
                "applications": d.applications,
                "successful": d.successful,
                "cost": d.cost,
            }
            for d in daily
        ]
    }


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
async def get_application(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get application details."""
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id,
    ).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    job = db.query(Job).filter(Job.id == application.job_id).first()
    metric = db.query(Metric).filter(
        Metric.application_id == application_id
    ).first()

    metrics_dict = None
    if metric:
        metrics_dict = {
            "tokens_used": metric.tokens_used,
            "captcha_cost": metric.captcha_cost,
            "duration_seconds": metric.duration_seconds,
        }

    return ApplicationDetailResponse(
        id=application.id,
        job_id=application.job_id,
        job_title=job.title if job else "Unknown",
        company=job.company if job else "Unknown",
        job_url=job.url if job else "",
        status=application.status if isinstance(application.status, str) else application.status.value,
        created_at=application.created_at,
        submitted_at=application.submitted_at,
        error_log=application.error_log,
        answers_json=application.answers_json,
        cover_letter_used=application.cover_letter_used,
        retry_count=application.retry_count,
        metrics=metrics_dict,
    )


@router.post("/{application_id}/retry")
async def retry_application(
    application_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_paid_user),
    db: Session = Depends(get_db),
):
    """Retry a failed application."""
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id,
    ).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    if application.status not in (ApplicationStatus.FAILED, ApplicationStatus.SKIPPED, "failed", "skipped"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed or skipped applications can be retried",
        )

    # Reset application status
    application.status = ApplicationStatus.PENDING.value
    application.error_log = None
    application.retry_count += 1
    db.commit()

    # Queue retry in background
    background_tasks.add_task(
        run_application_batch,
        user_id=current_user.id,
        job_ids=[application.job_id],
        headless=True,
    )

    return {"message": "Application queued for retry"}


@router.post("/apply")
async def apply_to_jobs(
    request: ApplyRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_paid_user),
    db: Session = Depends(get_db),
):
    """
    Queue jobs for application.

    This endpoint accepts a list of job IDs and queues them for application.
    """
    job_ids = request.job_ids

    # Tier-derived daily quota. Paid gate is enforced by require_paid_user;
    # admins fall back to the highest tier.
    limit = TIER_LIMITS.get(current_user.tier, TIER_LIMITS[UserTier.MAX])

    # Check today's count
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.created_at >= today_start,
        Application.status == ApplicationStatus.SUBMITTED.value,
    ).count()

    remaining = limit - today_count
    if remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily application limit reached",
        )

    # Limit to remaining quota
    job_ids = job_ids[:remaining]

    # Filter out already applied jobs
    already_applied = db.query(Application.job_id).filter(
        Application.user_id == current_user.id,
        Application.job_id.in_(job_ids),
    ).all()
    already_applied_ids = {a[0] for a in already_applied}

    new_job_ids = [j for j in job_ids if j not in already_applied_ids]

    if not new_job_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All selected jobs have already been applied to",
        )

    # Create pending applications
    for job_id in new_job_ids:
        application = Application(
            user_id=current_user.id,
            job_id=job_id,
            status=ApplicationStatus.PENDING.value,
        )
        db.add(application)

    db.commit()

    # Queue applications in background
    background_tasks.add_task(
        run_application_batch,
        user_id=current_user.id,
        job_ids=new_job_ids,
        headless=True,
    )

    return {
        "message": f"Queued {len(new_job_ids)} applications",
        "queued": len(new_job_ids),
        "skipped": len(job_ids) - len(new_job_ids),
    }
