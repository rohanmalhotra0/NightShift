"""Job scraper using JobSpy library."""

import logging
from datetime import datetime
from typing import Optional

from jobspy import scrape_jobs
import pandas as pd
from sqlalchemy.orm import Session

from ..database import Job, get_db_context

logger = logging.getLogger(__name__)


class JobScraper:
    """Scrapes job listings using JobSpy from multiple job boards."""

    SUPPORTED_SITES = ["linkedin", "indeed", "zip_recruiter", "glassdoor", "google"]

    def __init__(
        self,
        sites: Optional[list[str]] = None,
        proxies: Optional[list[str]] = None,
    ):
        """
        Initialize the job scraper.

        Args:
            sites: List of job sites to scrape. Defaults to LinkedIn + Indeed.
            proxies: Optional list of proxy URLs for IP rotation.
        """
        self.sites = sites or ["linkedin", "indeed"]
        self.proxies = proxies

    def scrape(
        self,
        search_terms: list[str],
        locations: list[str],
        results_per_search: int = 25,
        hours_old: int = 72,
        remote_only: bool = False,
        easy_apply_only: bool = False,
    ) -> pd.DataFrame:
        """
        Scrape jobs from configured job boards.

        Args:
            search_terms: List of job titles/keywords to search.
            locations: List of locations to search.
            results_per_search: Max results per site per search.
            hours_old: Only return jobs posted within this many hours.
            remote_only: Filter for remote jobs only.
            easy_apply_only: Filter for easy apply jobs (LinkedIn).

        Returns:
            DataFrame with all scraped jobs.
        """
        all_jobs = []

        for search_term in search_terms:
            for location in locations:
                logger.info(f"Scraping '{search_term}' in '{location}'")

                try:
                    jobs_df = scrape_jobs(
                        site_name=self.sites,
                        search_term=search_term,
                        location=location,
                        results_wanted=results_per_search,
                        hours_old=hours_old,
                        is_remote=remote_only,
                        linkedin_fetch_description=True,
                        proxies=self.proxies,
                    )

                    if not jobs_df.empty:
                        # Filter easy apply if requested
                        if easy_apply_only and "is_easy_apply" in jobs_df.columns:
                            jobs_df = jobs_df[jobs_df["is_easy_apply"] == True]

                        all_jobs.append(jobs_df)
                        logger.info(f"Found {len(jobs_df)} jobs")

                except Exception as e:
                    logger.error(f"Scraping failed for '{search_term}' in '{location}': {e}")
                    continue

        if not all_jobs:
            return pd.DataFrame()

        # Combine and deduplicate
        combined = pd.concat(all_jobs, ignore_index=True)
        combined = combined.drop_duplicates(subset=["job_url"], keep="first")

        logger.info(f"Total unique jobs scraped: {len(combined)}")
        return combined


def df_to_job_models(df: pd.DataFrame) -> list[dict]:
    """Convert JobSpy DataFrame to Job model dictionaries."""
    jobs = []

    for _, row in df.iterrows():
        # Extract job ID from URL if possible
        job_url = str(row.get("job_url", ""))
        external_id = None

        if "linkedin.com" in job_url:
            parts = job_url.split("/view/")
            if len(parts) > 1:
                external_id = parts[1].split("/")[0].split("?")[0]
        elif "indeed.com" in job_url:
            if "jk=" in job_url:
                external_id = job_url.split("jk=")[1].split("&")[0]

        if not external_id:
            # Use hash of URL as fallback ID
            external_id = str(hash(job_url))[-12:]

        job_data = {
            "source": str(row.get("site", "unknown")).lower(),
            "external_id": external_id,
            "title": str(row.get("title", ""))[:255],
            "company": str(row.get("company", ""))[:255],
            "location": str(row.get("location", ""))[:255] if pd.notna(row.get("location")) else None,
            "url": job_url[:1000],
            "description": str(row.get("description", "")) if pd.notna(row.get("description")) else None,
            "salary_range": None,
            "job_type": str(row.get("job_type", "")) if pd.notna(row.get("job_type")) else None,
            "is_easy_apply": bool(row.get("is_easy_apply", False)),
            "scraped_at": datetime.utcnow(),
        }

        # Handle salary
        min_salary = row.get("min_amount")
        max_salary = row.get("max_amount")
        if pd.notna(min_salary) or pd.notna(max_salary):
            if pd.notna(min_salary) and pd.notna(max_salary):
                job_data["salary_range"] = f"${int(min_salary):,} - ${int(max_salary):,}"
            elif pd.notna(min_salary):
                job_data["salary_range"] = f"${int(min_salary):,}+"
            else:
                job_data["salary_range"] = f"Up to ${int(max_salary):,}"

        jobs.append(job_data)

    return jobs


def save_jobs_to_db(jobs: list[dict], db: Session) -> int:
    """Save scraped jobs to database with deduplication."""
    saved_count = 0

    for job_data in jobs:
        # Check for existing job
        existing = db.query(Job).filter(
            Job.source == job_data["source"],
            Job.external_id == job_data["external_id"],
        ).first()

        if existing:
            continue

        job = Job(**job_data)
        db.add(job)
        saved_count += 1

    db.commit()
    logger.info(f"Saved {saved_count} new jobs to database")
    return saved_count


def run_scraper(
    job_titles: list[str],
    locations: list[str],
    sites: Optional[list[str]] = None,
    results_per_search: int = 25,
    hours_old: int = 72,
    easy_apply_only: bool = False,
    proxies: Optional[list[str]] = None,
) -> int:
    """
    Run the job scraper and save results to database.

    Args:
        job_titles: List of job titles/keywords to search.
        locations: List of locations to search.
        sites: Job sites to scrape. Defaults to LinkedIn + Indeed.
        results_per_search: Max results per site per search.
        hours_old: Only return jobs posted within this many hours.
        easy_apply_only: Filter for easy apply jobs.
        proxies: Optional list of proxy URLs.

    Returns:
        Number of new jobs saved to database.
    """
    scraper = JobScraper(sites=sites, proxies=proxies)

    jobs_df = scraper.scrape(
        search_terms=job_titles,
        locations=locations,
        results_per_search=results_per_search,
        hours_old=hours_old,
        easy_apply_only=easy_apply_only,
    )

    if jobs_df.empty:
        logger.warning("No jobs scraped")
        return 0

    job_models = df_to_job_models(jobs_df)

    with get_db_context() as db:
        saved_count = save_jobs_to_db(job_models, db)

    return saved_count


async def run_scraper_async(
    job_titles: list[str],
    locations: list[str],
    **kwargs,
) -> int:
    """Async wrapper for run_scraper (JobSpy is synchronous internally)."""
    import asyncio
    return await asyncio.to_thread(
        run_scraper,
        job_titles,
        locations,
        **kwargs,
    )


if __name__ == "__main__":
    # Test scraper
    logging.basicConfig(level=logging.INFO)

    titles = ["Software Engineer", "Backend Developer"]
    locs = ["San Francisco, CA"]

    saved = run_scraper(
        job_titles=titles,
        locations=locs,
        sites=["linkedin", "indeed"],
        results_per_search=10,
    )
    print(f"Total jobs saved: {saved}")
