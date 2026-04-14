"""Main Playwright bot engine for job applications."""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from sqlalchemy.orm import Session

from config import settings
from database import (
    Job, Application, User, UserPrefs, Resume, Metric,
    ApplicationStatus, get_db_context,
)
from bot.captcha import CaptchaSolver, detect_captcha_type, inject_captcha_solution
from bot.autofill import (
    AutoFiller, UserProfile, extract_form_fields, fill_form_fields,
)
from bot.gmail import wait_for_verification_code

logger = logging.getLogger(__name__)


@dataclass
class ApplicationResult:
    """Result of a job application attempt."""
    success: bool
    status: ApplicationStatus
    error: Optional[str] = None
    tokens_used: int = 0
    captcha_cost: float = 0.0
    duration_seconds: float = 0.0
    answers_json: dict = field(default_factory=dict)


class ApplicationBot:
    """Main bot for automating job applications."""

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 50,
    ):
        """
        Initialize the application bot.

        Args:
            headless: Run browser in headless mode.
            slow_mo: Slow down operations by this many ms.
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.captcha_solver = CaptchaSolver()
        self.autofiller = AutoFiller()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self) -> None:
        """Start the browser."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self.page = await self.context.new_page()

    async def close(self) -> None:
        """Close the browser."""
        if self.browser:
            await self.browser.close()
        await self.captcha_solver.close()

    async def load_cookies(self, cookies_path: Path) -> bool:
        """Load cookies from file."""
        try:
            if cookies_path.exists():
                with open(cookies_path) as f:
                    cookies = json.load(f)
                await self.context.add_cookies(cookies)
                logger.info(f"Loaded cookies from {cookies_path}")
                return True
        except Exception as e:
            logger.warning(f"Failed to load cookies: {e}")
        return False

    async def save_cookies(self, cookies_path: Path) -> None:
        """Save current cookies to file."""
        cookies = await self.context.cookies()
        with open(cookies_path, "w") as f:
            json.dump(cookies, f)
        logger.info(f"Saved cookies to {cookies_path}")

    def build_user_profile(
        self,
        user: User,
        prefs: UserPrefs,
        resume: Optional[Resume],
    ) -> UserProfile:
        """Build UserProfile from database models."""
        # Parse name from email if not available
        email_name = user.email.split("@")[0]
        name_parts = email_name.replace(".", " ").replace("_", " ").split()

        return UserProfile(
            first_name=name_parts[0].title() if name_parts else "User",
            last_name=name_parts[-1].title() if len(name_parts) > 1 else "",
            email=user.email,
            work_authorization=prefs.work_auth if prefs else None,
            remote_preference=prefs.remote_pref.value if prefs else "any",
            resume_text=resume.parsed_content if resume else None,
            salary_expectation=str(prefs.salary_min) if prefs and prefs.salary_min else None,
        )

    async def apply_to_job(
        self,
        job: Job,
        user_profile: UserProfile,
        resume_path: Optional[Path] = None,
        cover_letter: Optional[str] = None,
    ) -> ApplicationResult:
        """
        Apply to a single job.

        Args:
            job: Job to apply to.
            user_profile: User profile for form filling.
            resume_path: Path to resume file for upload.
            cover_letter: Pre-generated cover letter text.

        Returns:
            ApplicationResult with status and metrics.
        """
        start_time = time.time()
        total_tokens = 0
        total_captcha_cost = 0.0
        answers_json = {}

        try:
            logger.info(f"Applying to: {job.title} at {job.company}")

            # Navigate to job URL
            await self.page.goto(job.url, wait_until="networkidle")
            await asyncio.sleep(2)

            # Check for and handle CAPTCHA
            captcha_result = await self._handle_captcha()
            if captcha_result:
                total_captcha_cost += captcha_result

            # Look for apply button
            apply_clicked = await self._click_apply_button()
            if not apply_clicked:
                return ApplicationResult(
                    success=False,
                    status=ApplicationStatus.SKIPPED,
                    error="Could not find apply button",
                    duration_seconds=time.time() - start_time,
                )

            await asyncio.sleep(2)

            # Handle multi-step application
            max_steps = 10
            for step in range(max_steps):
                logger.info(f"Processing application step {step + 1}")

                # Check for CAPTCHA again
                captcha_result = await self._handle_captcha()
                if captcha_result:
                    total_captcha_cost += captcha_result

                # Check for verification code request
                if await self._needs_verification_code():
                    code = await wait_for_verification_code(timeout_seconds=120)
                    if code:
                        await self._enter_verification_code(code)
                    else:
                        return ApplicationResult(
                            success=False,
                            status=ApplicationStatus.FAILED,
                            error="Failed to get verification code",
                            duration_seconds=time.time() - start_time,
                        )

                # Extract and fill form fields
                fields = await extract_form_fields(self.page)

                if fields:
                    result = self.autofiller.generate_field_mappings(
                        fields=fields,
                        user_profile=user_profile,
                        job_description=job.description,
                    )

                    if result.success:
                        total_tokens += result.tokens_used
                        answers_json.update(result.field_mappings)
                        await fill_form_fields(self.page, result.field_mappings)

                # Handle resume upload
                if resume_path:
                    await self._upload_resume(resume_path)

                # Handle cover letter
                if cover_letter:
                    await self._fill_cover_letter(cover_letter)

                # Look for next/submit button
                button_clicked, is_submit = await self._click_next_or_submit()

                if not button_clicked:
                    # Check if we're done (confirmation page)
                    if await self._is_confirmation_page():
                        return ApplicationResult(
                            success=True,
                            status=ApplicationStatus.SUBMITTED,
                            tokens_used=total_tokens,
                            captcha_cost=total_captcha_cost,
                            duration_seconds=time.time() - start_time,
                            answers_json=answers_json,
                        )
                    break

                if is_submit:
                    await asyncio.sleep(3)
                    if await self._is_confirmation_page():
                        return ApplicationResult(
                            success=True,
                            status=ApplicationStatus.SUBMITTED,
                            tokens_used=total_tokens,
                            captcha_cost=total_captcha_cost,
                            duration_seconds=time.time() - start_time,
                            answers_json=answers_json,
                        )

                await asyncio.sleep(1)

            return ApplicationResult(
                success=False,
                status=ApplicationStatus.FAILED,
                error="Max steps reached without completion",
                tokens_used=total_tokens,
                captcha_cost=total_captcha_cost,
                duration_seconds=time.time() - start_time,
                answers_json=answers_json,
            )

        except Exception as e:
            logger.error(f"Application failed: {e}")
            return ApplicationResult(
                success=False,
                status=ApplicationStatus.FAILED,
                error=str(e),
                tokens_used=total_tokens,
                captcha_cost=total_captcha_cost,
                duration_seconds=time.time() - start_time,
                answers_json=answers_json,
            )

    async def _handle_captcha(self) -> Optional[float]:
        """Handle CAPTCHA if present. Returns cost if solved."""
        captcha = await detect_captcha_type(self.page)
        if not captcha:
            return None

        captcha_type, params = captcha
        page_url = self.page.url

        logger.info(f"Detected {captcha_type.value} CAPTCHA")

        if captcha_type.value.startswith("recaptcha"):
            if "v3" in captcha_type.value:
                result = await self.captcha_solver.solve_recaptcha_v3(
                    site_key=params["site_key"],
                    page_url=page_url,
                    action=params.get("action", "verify"),
                )
            else:
                result = await self.captcha_solver.solve_recaptcha_v2(
                    site_key=params["site_key"],
                    page_url=page_url,
                    invisible=params.get("invisible", False),
                )
        elif captcha_type.value == "hcaptcha":
            result = await self.captcha_solver.solve_hcaptcha(
                site_key=params["site_key"],
                page_url=page_url,
            )
        else:
            logger.warning(f"Unsupported CAPTCHA type: {captcha_type}")
            return None

        if result.success:
            await inject_captcha_solution(self.page, captcha_type, result.solution)
            return result.cost

        logger.warning(f"CAPTCHA solve failed: {result.error}")
        return None

    async def _click_apply_button(self) -> bool:
        """Find and click the apply button."""
        selectors = [
            'button:has-text("Easy Apply")',
            'button:has-text("Apply")',
            'a:has-text("Apply")',
            '[data-control-name="jobdetails_topcard_inapply"]',
            '.jobs-apply-button',
            '#apply-button',
        ]

        for selector in selectors:
            button = await self.page.query_selector(selector)
            if button:
                await button.click()
                logger.info(f"Clicked apply button: {selector}")
                return True

        return False

    async def _click_next_or_submit(self) -> tuple[bool, bool]:
        """
        Click next or submit button.

        Returns:
            Tuple of (button_clicked, is_submit_button).
        """
        # Submit buttons
        submit_selectors = [
            'button:has-text("Submit")',
            'button:has-text("Submit application")',
            'button[type="submit"]:has-text("Submit")',
            'button:has-text("Apply")',
        ]

        for selector in submit_selectors:
            button = await self.page.query_selector(selector)
            if button and await button.is_visible():
                await button.click()
                logger.info(f"Clicked submit: {selector}")
                return True, True

        # Next buttons
        next_selectors = [
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'button:has-text("Review")',
            'button[aria-label="Continue to next step"]',
        ]

        for selector in next_selectors:
            button = await self.page.query_selector(selector)
            if button and await button.is_visible():
                await button.click()
                logger.info(f"Clicked next: {selector}")
                return True, False

        return False, False

    async def _is_confirmation_page(self) -> bool:
        """Check if we're on a confirmation/success page."""
        indicators = [
            'text="Application submitted"',
            'text="Thank you for applying"',
            'text="Application sent"',
            'text="Successfully applied"',
            ".artdeco-inline-feedback--success",
            '[data-test="application-submitted"]',
        ]

        for indicator in indicators:
            element = await self.page.query_selector(indicator)
            if element:
                logger.info("Detected confirmation page")
                return True

        return False

    async def _needs_verification_code(self) -> bool:
        """Check if page is requesting a verification code."""
        indicators = [
            'text="Enter verification code"',
            'text="Enter the code"',
            'text="Verify your email"',
            'input[name*="verification"]',
            'input[name*="code"]',
        ]

        for indicator in indicators:
            element = await self.page.query_selector(indicator)
            if element:
                return True

        return False

    async def _enter_verification_code(self, code: str) -> None:
        """Enter verification code into the form."""
        selectors = [
            'input[name*="verification"]',
            'input[name*="code"]',
            'input[type="text"][maxlength="6"]',
            'input[aria-label*="code"]',
        ]

        for selector in selectors:
            input_el = await self.page.query_selector(selector)
            if input_el:
                await input_el.fill(code)
                logger.info("Entered verification code")

                # Look for verify button
                verify_btn = await self.page.query_selector(
                    'button:has-text("Verify"), button:has-text("Submit")'
                )
                if verify_btn:
                    await verify_btn.click()
                return

    async def _upload_resume(self, resume_path: Path) -> bool:
        """Upload resume file."""
        file_inputs = await self.page.query_selector_all('input[type="file"]')

        for file_input in file_inputs:
            accept = await file_input.get_attribute("accept") or ""
            name = await file_input.get_attribute("name") or ""

            # Check if this is likely a resume upload
            if any(x in accept.lower() for x in ["pdf", "doc", "application"]):
                await file_input.set_input_files(str(resume_path))
                logger.info(f"Uploaded resume: {resume_path}")
                return True

            if any(x in name.lower() for x in ["resume", "cv"]):
                await file_input.set_input_files(str(resume_path))
                logger.info(f"Uploaded resume: {resume_path}")
                return True

        return False

    async def _fill_cover_letter(self, cover_letter: str) -> bool:
        """Fill cover letter field."""
        selectors = [
            'textarea[name*="cover"]',
            'textarea[name*="letter"]',
            '#cover-letter',
            '[aria-label*="cover letter"]',
        ]

        for selector in selectors:
            textarea = await self.page.query_selector(selector)
            if textarea:
                await textarea.fill(cover_letter)
                logger.info("Filled cover letter")
                return True

        return False


async def run_application_batch(
    user_id: int,
    job_ids: list[int],
    headless: bool = True,
) -> dict:
    """
    Run a batch of job applications for a user.

    Args:
        user_id: User ID.
        job_ids: List of job IDs to apply to.
        headless: Run browser in headless mode.

    Returns:
        Dict with results summary.
    """
    results = {
        "total": len(job_ids),
        "submitted": 0,
        "failed": 0,
        "skipped": 0,
    }

    with get_db_context() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return results

        prefs = db.query(UserPrefs).filter(UserPrefs.user_id == user_id).first()
        resume = db.query(Resume).filter(
            Resume.user_id == user_id,
            Resume.is_primary == True
        ).first()

        async with ApplicationBot(headless=headless) as bot:
            user_profile = bot.build_user_profile(user, prefs, resume)
            resume_path = Path(resume.file_path) if resume else None

            for job_id in job_ids:
                job = db.query(Job).filter(Job.id == job_id).first()
                if not job:
                    continue

                # Create application record
                application = Application(
                    user_id=user_id,
                    job_id=job_id,
                    status=ApplicationStatus.IN_PROGRESS,
                    resume_id=resume.id if resume else None,
                    started_at=datetime.utcnow(),
                )
                db.add(application)
                db.commit()

                # Apply
                result = await bot.apply_to_job(
                    job=job,
                    user_profile=user_profile,
                    resume_path=resume_path,
                )

                # Update application
                application.status = result.status
                application.answers_json = result.answers_json
                application.error_log = result.error
                if result.success:
                    application.submitted_at = datetime.utcnow()

                # Create metrics
                metric = Metric(
                    user_id=user_id,
                    application_id=application.id,
                    tokens_input=result.tokens_used // 2,
                    tokens_output=result.tokens_used // 2,
                    captcha_cost=result.captcha_cost,
                    duration_sec=result.duration_seconds,
                    job_site=job.source,
                    success=result.success,
                )
                db.add(metric)
                db.commit()

                # Update results
                if result.status == ApplicationStatus.SUBMITTED:
                    results["submitted"] += 1
                elif result.status == ApplicationStatus.FAILED:
                    results["failed"] += 1
                else:
                    results["skipped"] += 1

                # Brief pause between applications
                await asyncio.sleep(5)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--user-id", type=int, required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    results = asyncio.run(run_application_batch(
        user_id=args.user_id,
        job_ids=[args.job_id],
        headless=False,
    ))
    print(f"Results: {results}")
