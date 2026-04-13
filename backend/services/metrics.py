"""Metrics tracking for token usage and costs."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import Metric, Application, User, get_db_context

logger = logging.getLogger(__name__)

# Claude pricing (approximate, per 1K tokens)
CLAUDE_INPUT_COST_PER_1K = 0.003
CLAUDE_OUTPUT_COST_PER_1K = 0.015


@dataclass
class UsageStats:
    """Usage statistics for a time period."""
    total_applications: int
    successful_applications: int
    failed_applications: int
    total_tokens_input: int
    total_tokens_output: int
    total_captcha_cost: float
    total_claude_cost: float
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
        """
        Initialize metrics tracker.

        Args:
            db: Optional database session. If not provided, will create new sessions.
        """
        self._db = db

    def _get_db(self):
        """Get database session."""
        if self._db:
            return self._db
        return get_db_context()

    def record_application(
        self,
        user_id: int,
        application_id: int,
        tokens_input: int = 0,
        tokens_output: int = 0,
        captcha_cost: float = 0.0,
        duration_sec: float = 0.0,
        job_site: str = "",
        success: bool = False,
    ) -> Metric:
        """
        Record metrics for a single application.

        Args:
            user_id: User ID.
            application_id: Application ID.
            tokens_input: Claude input tokens used.
            tokens_output: Claude output tokens used.
            captcha_cost: CAPTCHA solving cost in USD.
            duration_sec: Total duration in seconds.
            job_site: Source job site.
            success: Whether application was successful.

        Returns:
            Created Metric record.
        """
        # Calculate Claude cost
        claude_cost = (
            (tokens_input / 1000 * CLAUDE_INPUT_COST_PER_1K) +
            (tokens_output / 1000 * CLAUDE_OUTPUT_COST_PER_1K)
        )

        with get_db_context() as db:
            metric = Metric(
                user_id=user_id,
                application_id=application_id,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                captcha_cost=captcha_cost,
                claude_cost=claude_cost,
                duration_sec=duration_sec,
                job_site=job_site,
                success=success,
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)
            return metric

    def get_user_stats(
        self,
        user_id: int,
        days: int = 30,
    ) -> UsageStats:
        """
        Get usage statistics for a user over a time period.

        Args:
            user_id: User ID.
            days: Number of days to look back.

        Returns:
            UsageStats for the period.
        """
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
                    total_tokens_input=0,
                    total_tokens_output=0,
                    total_captcha_cost=0.0,
                    total_claude_cost=0.0,
                    total_cost=0.0,
                    avg_duration_seconds=0.0,
                    success_rate=0.0,
                )

            total = len(metrics)
            successful = sum(1 for m in metrics if m.success)
            tokens_in = sum(m.tokens_input for m in metrics)
            tokens_out = sum(m.tokens_output for m in metrics)
            captcha = sum(m.captcha_cost for m in metrics)
            claude = sum(m.claude_cost for m in metrics)
            durations = [m.duration_sec for m in metrics if m.duration_sec > 0]

            return UsageStats(
                total_applications=total,
                successful_applications=successful,
                failed_applications=total - successful,
                total_tokens_input=tokens_in,
                total_tokens_output=tokens_out,
                total_captcha_cost=captcha,
                total_claude_cost=claude,
                total_cost=captcha + claude,
                avg_duration_seconds=sum(durations) / len(durations) if durations else 0.0,
                success_rate=successful / total if total > 0 else 0.0,
            )

    def get_daily_stats(
        self,
        user_id: int,
        days: int = 7,
    ) -> list[DailyStats]:
        """
        Get daily statistics for a user.

        Args:
            user_id: User ID.
            days: Number of days to look back.

        Returns:
            List of DailyStats ordered by date.
        """
        since = datetime.utcnow() - timedelta(days=days)

        with get_db_context() as db:
            # Group metrics by date
            results = db.query(
                func.date(Metric.created_at).label("date"),
                func.count(Metric.id).label("total"),
                func.sum(func.cast(Metric.success, db.bind.dialect.name == "sqlite" and "INTEGER" or "INT")).label("successful"),
                func.sum(Metric.captcha_cost + Metric.claude_cost).label("cost"),
            ).filter(
                Metric.user_id == user_id,
                Metric.created_at >= since,
            ).group_by(
                func.date(Metric.created_at)
            ).order_by(
                func.date(Metric.created_at)
            ).all()

            daily_stats = []
            for row in results:
                daily_stats.append(DailyStats(
                    date=str(row.date),
                    applications=row.total,
                    successful=int(row.successful or 0),
                    cost=float(row.cost or 0.0),
                ))

            return daily_stats

    def get_site_breakdown(
        self,
        user_id: int,
        days: int = 30,
    ) -> dict[str, dict]:
        """
        Get application breakdown by job site.

        Args:
            user_id: User ID.
            days: Number of days to look back.

        Returns:
            Dict mapping site name to stats.
        """
        since = datetime.utcnow() - timedelta(days=days)

        with get_db_context() as db:
            metrics = db.query(Metric).filter(
                Metric.user_id == user_id,
                Metric.created_at >= since,
            ).all()

            sites = {}
            for m in metrics:
                site = m.job_site or "unknown"
                if site not in sites:
                    sites[site] = {
                        "total": 0,
                        "successful": 0,
                        "cost": 0.0,
                    }
                sites[site]["total"] += 1
                if m.success:
                    sites[site]["successful"] += 1
                sites[site]["cost"] += m.captcha_cost + m.claude_cost

            return sites

    def estimate_monthly_cost(self, user_id: int) -> float:
        """
        Estimate monthly cost based on recent usage.

        Args:
            user_id: User ID.

        Returns:
            Estimated monthly cost in USD.
        """
        stats = self.get_user_stats(user_id, days=7)
        daily_cost = stats.total_cost / 7 if stats.total_cost > 0 else 0
        return daily_cost * 30

    def get_global_stats(self, days: int = 30) -> dict:
        """
        Get global platform statistics (admin only).

        Args:
            days: Number of days to look back.

        Returns:
            Global statistics dict.
        """
        since = datetime.utcnow() - timedelta(days=days)

        with get_db_context() as db:
            metrics = db.query(Metric).filter(
                Metric.created_at >= since
            ).all()

            users = db.query(func.count(func.distinct(Metric.user_id))).filter(
                Metric.created_at >= since
            ).scalar()

            return {
                "total_applications": len(metrics),
                "successful_applications": sum(1 for m in metrics if m.success),
                "total_users": users,
                "total_revenue": sum(m.captcha_cost + m.claude_cost for m in metrics),
                "avg_applications_per_user": len(metrics) / users if users else 0,
            }


def calculate_application_cost(
    tokens_input: int,
    tokens_output: int,
    captcha_cost: float = 0.0,
) -> float:
    """
    Calculate total cost for an application.

    Args:
        tokens_input: Claude input tokens.
        tokens_output: Claude output tokens.
        captcha_cost: CAPTCHA solving cost.

    Returns:
        Total cost in USD.
    """
    claude_cost = (
        (tokens_input / 1000 * CLAUDE_INPUT_COST_PER_1K) +
        (tokens_output / 1000 * CLAUDE_OUTPUT_COST_PER_1K)
    )
    return claude_cost + captcha_cost
