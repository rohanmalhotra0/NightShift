"""APScheduler for nightly job application runs."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from config import settings
from database import (
    User, UserPrefs, Job, Application, UserTier,
    ApplicationStatus, get_db_context,
)
from scrapers import run_scraper_async
from bot.engine import run_application_batch
from services.sheets import GoogleSheetsLogger

logger = logging.getLogger(__name__)

# Application limits by tier
TIER_LIMITS = {
    UserTier.FREE: 0,
    UserTier.STARTER: 3,
    UserTier.PRO: 10,
    UserTier.MAX: 25,
}


class JobScheduler:
    """Manages scheduled job scraping and application runs."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.sheets_logger = GoogleSheetsLogger()

    def start(self) -> None:
        """Start the scheduler."""
        # Default scraping job - runs at 8 PM daily
        self.scheduler.add_job(
            self._run_scraping,
            CronTrigger(hour=20, minute=0),
            id="daily_scrape",
            replace_existing=True,
        )

        # Default application runs - 10 PM and 11 PM
        self.scheduler.add_job(
            self._run_applications_batch,
            CronTrigger(hour=settings.DEFAULT_RUN_HOUR_1, minute=0),
            id="applications_run_1",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self._run_applications_batch,
            CronTrigger(hour=settings.DEFAULT_RUN_HOUR_2, minute=0),
            id="applications_run_2",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    async def _run_scraping(self) -> None:
        """Run job scraping for all active users."""
        logger.info("Starting scheduled scraping run")

        with get_db_context() as db:
            # Get all active users with preferences
            users = db.query(User).filter(
                User.is_active == True,
                User.tier != UserTier.FREE,
            ).all()

            for user in users:
                prefs = db.query(UserPrefs).filter(
                    UserPrefs.user_id == user.id
                ).first()

                if not prefs or not prefs.job_titles or not prefs.locations:
                    continue

                try:
                    saved = await run_scraper_async(
                        job_titles=prefs.job_titles,
                        locations=prefs.locations,
                        results_per_search=15,
                    )
                    logger.info(f"User {user.id}: scraped {saved} jobs")
                except Exception as e:
                    logger.error(f"Scraping failed for user {user.id}: {e}")

        logger.info("Scraping run completed")

    async def _run_applications_batch(self) -> None:
        """Run applications for all eligible users."""
        logger.info("Starting scheduled applications run")

        with get_db_context() as db:
            users = db.query(User).filter(
                User.is_active == True,
                User.tier != UserTier.FREE,
            ).all()

            for user in users:
                await self._process_user_applications(db, user)

        logger.info("Applications run completed")

    async def _process_user_applications(self, db: Session, user: User) -> None:
        """Process applications for a single user."""
        prefs = db.query(UserPrefs).filter(UserPrefs.user_id == user.id).first()
        if not prefs:
            return

        # Check time window
        current_hour = datetime.utcnow().hour
        if current_hour not in (prefs.run_hour_1, prefs.run_hour_2):
            return

        # Get application limit
        limit = TIER_LIMITS.get(user.tier, 0)
        if limit == 0:
            return

        # Count today's applications
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = db.query(Application).filter(
            Application.user_id == user.id,
            Application.queued_at >= today_start,
            Application.status == ApplicationStatus.SUBMITTED,
        ).count()

        remaining = limit - today_count
        if remaining <= 0:
            logger.info(f"User {user.id} has reached daily limit")
            return

        # Get jobs to apply to
        job_ids = await self._get_jobs_for_user(db, user, prefs, remaining)
        if not job_ids:
            logger.info(f"No jobs to apply for user {user.id}")
            return

        logger.info(f"Processing {len(job_ids)} applications for user {user.id}")

        try:
            results = await run_application_batch(
                user_id=user.id,
                job_ids=job_ids,
                headless=True,
            )

            # Log to Google Sheets
            if prefs.sheets_id:
                await self._log_to_sheets(db, user, prefs.sheets_id, job_ids)

            logger.info(f"User {user.id} results: {results}")

        except Exception as e:
            logger.error(f"Application batch failed for user {user.id}: {e}")

    async def _get_jobs_for_user(
        self,
        db: Session,
        user: User,
        prefs: UserPrefs,
        limit: int,
    ) -> list[int]:
        """Get jobs matching user preferences that haven't been applied to."""
        # Get already applied job IDs
        applied_job_ids = db.query(Application.job_id).filter(
            Application.user_id == user.id
        ).all()
        applied_ids = {j[0] for j in applied_job_ids}

        # Find matching jobs
        query = db.query(Job).filter(
            Job.id.notin_(applied_ids),
            Job.scraped_at >= datetime.utcnow() - timedelta(days=7),
        )

        # Filter by job titles if set
        if prefs.job_titles:
            title_filters = []
            for title in prefs.job_titles:
                title_filters.append(Job.title.ilike(f"%{title}%"))
            from sqlalchemy import or_
            query = query.filter(or_(*title_filters))

        # Filter by locations if set
        if prefs.locations:
            location_filters = []
            for loc in prefs.locations:
                location_filters.append(Job.location.ilike(f"%{loc}%"))
            from sqlalchemy import or_
            query = query.filter(or_(*location_filters))

        jobs = query.order_by(Job.scraped_at.desc()).limit(limit).all()
        return [j.id for j in jobs]

    async def _log_to_sheets(
        self,
        db: Session,
        user: User,
        sheets_id: str,
        job_ids: list[int],
    ) -> None:
        """Log applications to Google Sheets."""
        for job_id in job_ids:
            application = db.query(Application).filter(
                Application.user_id == user.id,
                Application.job_id == job_id,
            ).order_by(Application.id.desc()).first()

            if not application:
                continue

            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                continue

            try:
                self.sheets_logger.append_application(
                    sheets_id=sheets_id,
                    date=datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                    job_title=job.title,
                    company=job.company,
                    url=job.url,
                    status=application.status.value,
                    answers=str(application.answers_json or {}),
                )
            except Exception as e:
                logger.warning(f"Failed to log to sheets: {e}")

    async def run_now(self, user_id: Optional[int] = None) -> dict:
        """
        Run applications immediately (for testing/manual trigger).

        Args:
            user_id: Specific user ID, or None for all users.

        Returns:
            Results summary.
        """
        results = {"users_processed": 0, "total_submitted": 0}

        with get_db_context() as db:
            if user_id:
                users = [db.query(User).filter(User.id == user_id).first()]
            else:
                users = db.query(User).filter(
                    User.is_active == True,
                    User.tier != UserTier.FREE,
                ).all()

            for user in users:
                if not user:
                    continue
                await self._process_user_applications(db, user)
                results["users_processed"] += 1

        return results


# Global scheduler instance
_scheduler: Optional[JobScheduler] = None


def get_scheduler() -> JobScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler()
    return _scheduler


def start_scheduler() -> JobScheduler:
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-now", action="store_true")
    parser.add_argument("--user-id", type=int)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.run_now:
        scheduler = JobScheduler()
        results = asyncio.run(scheduler.run_now(user_id=args.user_id))
        print(f"Results: {results}")
    else:
        scheduler = start_scheduler()
        try:
            asyncio.get_event_loop().run_forever()
        except KeyboardInterrupt:
            scheduler.stop()
