"""Metrics tracking for token usage and costs."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from sqlalchemy import func, cast, Integer
from sqlalchemy.orm import Session

from database import Metric, Application, User, get_db_context

logger = logging.getLogger(__name__)

# Claude pricing (approximate per 1K tokens, for cost estimation)
CLAUDE_COST_PER_1K_TOKENS = 0.009


@dataclass
class UsageStats:
    """Usage statistics for a time period."""
    total_applications: int
    successful_applications: int
    failed_applications: int
    total_tokens_used: int
    total_captcha_cost: float
    total_cost: float
    avg_duration_seconds: float
    success_rate: float


@dataclass
class DailyStats:
    """Daily statistics."""
    date: str
    applications: int
    successful: int
    cost: float


class MetricsTracker:
    """Tracks and aggregates application metrics."""

    def __init__(self, db: Optional[Session] = None):
        self._db = db

    def record_application(
        self,
        user_id: str,
        application_id: str,
        tokens_used: int = 0,
        captcha_cost: float = 0.0,
        duration_seconds: int = 0,
        job_site: str = "",
        success: bool = False,
    ) -> Metric:
        """Record metrics for a single application."""
        with get_db_context() as db:
            metric = Metric(
                user_id=user_id,
                application_id=application_id,
                tokens_used=tokens_used,
                captcha_cost=captcha_cost,
                duration_seconds=duration_seconds,
                job_site=job_site,
                success=success,
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)
            return metric

    def get_user_stats(self, user_id: str, days: int = 30) -> UsageStats:
        """Get usage statistics for a user over a time period."""
        since = datetime.utcnow() - timedelta(days=days)

        with get_db_context() as db:
            metrics = db.query(Metric).filter(
                Metric.user_id == user_id,
                Metric.created_at >= since,
            ).all()

            if not metrics:
                return UsageStats(
                    total_applications=0,
                    successful_applications=0,
                    failed_applications=0,
                    total_tokens_used=0,
                    total_captcha_cost=0.0,
                    total_cost=0.0,
                    avg_duration_seconds=0.0,
                    success_rate=0.0,
                )

            total = len(metrics)
            successful = sum(1 for m in metrics if m.success)
            tokens = sum(m.tokens_used for m in metrics)
            captcha = sum(m.captcha_cost for m in metrics)
            claude_cost = tokens / 1000 * CLAUDE_COST_PER_1K_TOKENS
            durations = [m.duration_seconds for m in metrics if m.duration_seconds > 0]

            return UsageStats(
                total_applications=total,
                successful_applications=successful,
                failed_applications=total - successful,
                total_tokens_used=tokens,
                total_captcha_cost=captcha,
                total_cost=captcha + claude_cost,
                avg_duration_seconds=sum(durations) / len(durations) if durations else 0.0,
                success_rate=successful / total if total > 0 else 0.0,
            )

    def get_daily_stats(self, user_id: str, days: int = 7) -> list[DailyStats]:
        """Get daily statistics for a user."""
        since = datetime.utcnow() - timedelta(days=days)

        with get_db_context() as db:
            results = db.query(
                func.date(Metric.created_at).label("date"),
                func.count(Metric.id).label("total"),
                func.sum(cast(Metric.success, Integer)).label("successful"),
                func.sum(Metric.captcha_cost).label("cost"),
            ).filter(
                Metric.user_id == user_id,
                Metric.created_at >= since,
            ).group_by(
                func.date(Metric.created_at)
            ).order_by(
                func.date(Metric.created_at)
            ).all()

            return [
                DailyStats(
                    date=str(row.date),
                    applications=row.total,
                    successful=int(row.successful or 0),
                    cost=float(row.cost or 0.0),
                )
                for row in results
            ]

    def get_site_breakdown(self, user_id: str, days: int = 30) -> dict[str, dict]:
        """Get application breakdown by job site."""
        since = datetime.utcnow() - timedelta(days=days)

        with get_db_context() as db:
            metrics = db.query(Metric).filter(
                Metric.user_id == user_id,
                Metric.created_at >= since,
            ).all()

            sites: dict[str, dict] = {}
            for m in metrics:
                site = m.job_site or "unknown"
                if site not in sites:
                    sites[site] = {"total": 0, "successful": 0, "cost": 0.0}
                sites[site]["total"] += 1
                if m.success:
                    sites[site]["successful"] += 1
                sites[site]["cost"] += m.captcha_cost

            return sites

    def estimate_monthly_cost(self, user_id: str) -> float:
        """Estimate monthly cost based on recent 7-day usage."""
        stats = self.get_user_stats(user_id, days=7)
        daily_cost = stats.total_cost / 7 if stats.total_cost > 0 else 0
        return daily_cost * 30

    def get_global_stats(self, days: int = 30) -> dict:
        """Get global platform statistics (admin only)."""
        since = datetime.utcnow() - timedelta(days=days)

        with get_db_context() as db:
            metrics = db.query(Metric).filter(Metric.created_at >= since).all()
            user_count = db.query(func.count(func.distinct(Metric.user_id))).filter(
                Metric.created_at >= since
            ).scalar()

            return {
                "total_applications": len(metrics),
                "successful_applications": sum(1 for m in metrics if m.success),
                "total_users": user_count,
                "total_captcha_cost": sum(m.captcha_cost for m in metrics),
                "avg_applications_per_user": len(metrics) / user_count if user_count else 0,
            }
