"""2Captcha integration for solving CAPTCHAs."""

import asyncio
import logging
import time
from typing import Optional
from dataclasses import dataclass
from enum import Enum

import httpx

from config import settings

logger = logging.getLogger(__name__)


class CaptchaType(str, Enum):
    """Supported CAPTCHA types."""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    IMAGE = "image"


@dataclass
class CaptchaResult:
    """Result from CAPTCHA solving."""
    success: bool
    solution: Optional[str] = None
    cost: float = 0.0
    error: Optional[str] = None


class CaptchaSolver:
    """2Captcha API client for solving CAPTCHAs."""

    BASE_URL = "http://2captcha.com"
    SOLVE_URL = f"{BASE_URL}/in.php"
    RESULT_URL = f"{BASE_URL}/res.php"

    # Pricing (approximate, in USD)
    PRICING = {
        CaptchaType.RECAPTCHA_V2: 0.00299,
        CaptchaType.RECAPTCHA_V3: 0.00299,
        CaptchaType.HCAPTCHA: 0.00299,
        CaptchaType.IMAGE: 0.001,
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.TWOCAPTCHA_API_KEY
        self.client = httpx.AsyncClient(timeout=120)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        invisible: bool = False,
    ) -> CaptchaResult:
        """
        Solve reCAPTCHA v2.

        Args:
            site_key: The reCAPTCHA site key from the page.
            page_url: The URL where the CAPTCHA appears.
            invisible: Whether it's an invisible reCAPTCHA.

        Returns:
            CaptchaResult with solution token.
        """
        params = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "json": 1,
        }

        if invisible:
            params["invisible"] = 1

        return await self._solve(params, CaptchaType.RECAPTCHA_V2)

    async def solve_recaptcha_v3(
        self,
        site_key: str,
        page_url: str,
        action: str = "verify",
        min_score: float = 0.3,
    ) -> CaptchaResult:
        """
        Solve reCAPTCHA v3.

        Args:
            site_key: The reCAPTCHA site key.
            page_url: The URL where the CAPTCHA appears.
            action: The action parameter from the page.
            min_score: Minimum score required (0.1-0.9).

        Returns:
            CaptchaResult with solution token.
        """
        params = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "version": "v3",
            "action": action,
            "min_score": min_score,
            "json": 1,
        }

        return await self._solve(params, CaptchaType.RECAPTCHA_V3)

    async def solve_hcaptcha(
        self,
        site_key: str,
        page_url: str,
    ) -> CaptchaResult:
        """
        Solve hCaptcha.

        Args:
            site_key: The hCaptcha site key.
            page_url: The URL where the CAPTCHA appears.

        Returns:
            CaptchaResult with solution token.
        """
        params = {
            "key": self.api_key,
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
            "json": 1,
        }

        return await self._solve(params, CaptchaType.HCAPTCHA)

    async def solve_image_captcha(
        self,
        image_base64: str,
        case_sensitive: bool = False,
    ) -> CaptchaResult:
        """
        Solve image-based CAPTCHA.

        Args:
            image_base64: Base64 encoded image.
            case_sensitive: Whether the solution is case-sensitive.

        Returns:
            CaptchaResult with text solution.
        """
        params = {
            "key": self.api_key,
            "method": "base64",
            "body": image_base64,
            "json": 1,
        }

        if case_sensitive:
            params["regsense"] = 1

        return await self._solve(params, CaptchaType.IMAGE)

    async def _solve(self, params: dict, captcha_type: CaptchaType) -> CaptchaResult:
        """Internal method to submit and retrieve CAPTCHA solution."""
        try:
            # Submit CAPTCHA
            response = await self.client.post(self.SOLVE_URL, data=params)
            data = response.json()

            if data.get("status") != 1:
                return CaptchaResult(
                    success=False,
                    error=data.get("request", "Unknown error"),
                )

            request_id = data["request"]
            logger.info(f"CAPTCHA submitted, request ID: {request_id}")

            # Poll for result
            solution = await self._poll_result(request_id)

            if solution:
                return CaptchaResult(
                    success=True,
                    solution=solution,
                    cost=self.PRICING.get(captcha_type, 0.003),
                )
            else:
                return CaptchaResult(
                    success=False,
                    error="Timeout waiting for solution",
                )

        except Exception as e:
            logger.error(f"CAPTCHA solving error: {e}")
            return CaptchaResult(success=False, error=str(e))

    async def _poll_result(
        self,
        request_id: str,
        max_attempts: int = 60,
        poll_interval: int = 5,
    ) -> Optional[str]:
        """Poll 2Captcha for solution result."""
        params = {
            "key": self.api_key,
            "action": "get",
            "id": request_id,
            "json": 1,
        }

        for attempt in range(max_attempts):
            await asyncio.sleep(poll_interval)

            try:
                response = await self.client.get(self.RESULT_URL, params=params)
                data = response.json()

                if data.get("status") == 1:
                    logger.info("CAPTCHA solved successfully")
                    return data["request"]

                if data.get("request") == "CAPCHA_NOT_READY":
                    logger.debug(f"CAPTCHA not ready, attempt {attempt + 1}")
                    continue

                # Error occurred
                logger.error(f"CAPTCHA error: {data.get('request')}")
                return None

            except Exception as e:
                logger.warning(f"Poll error: {e}")
                continue

        logger.error("CAPTCHA solve timeout")
        return None

    async def get_balance(self) -> float:
        """Get 2Captcha account balance."""
        params = {
            "key": self.api_key,
            "action": "getbalance",
            "json": 1,
        }

        try:
            response = await self.client.get(self.RESULT_URL, params=params)
            data = response.json()

            if data.get("status") == 1:
                return float(data["request"])
            return 0.0
        except Exception:
            return 0.0


async def detect_captcha_type(page) -> Optional[tuple[CaptchaType, dict]]:
    """
    Detect CAPTCHA type on a Playwright page.

    Returns:
        Tuple of (CaptchaType, params dict) or None if no CAPTCHA detected.
    """
    # Check for reCAPTCHA
    recaptcha = await page.query_selector('[data-sitekey]')
    if recaptcha:
        site_key = await recaptcha.get_attribute("data-sitekey")
        invisible = await recaptcha.get_attribute("data-size") == "invisible"

        # Check for v3
        recaptcha_v3 = await page.query_selector('[data-action]')
        if recaptcha_v3:
            action = await recaptcha_v3.get_attribute("data-action")
            return CaptchaType.RECAPTCHA_V3, {
                "site_key": site_key,
                "action": action or "verify",
            }

        return CaptchaType.RECAPTCHA_V2, {
            "site_key": site_key,
            "invisible": invisible,
        }

    # Check for hCaptcha
    hcaptcha = await page.query_selector('[data-hcaptcha-sitekey]')
    if not hcaptcha:
        hcaptcha = await page.query_selector('.h-captcha')
    if hcaptcha:
        site_key = await hcaptcha.get_attribute("data-sitekey")
        if not site_key:
            site_key = await hcaptcha.get_attribute("data-hcaptcha-sitekey")
        return CaptchaType.HCAPTCHA, {"site_key": site_key}

    # Check for image CAPTCHA
    captcha_img = await page.query_selector('img[alt*="captcha" i], img[src*="captcha" i]')
    if captcha_img:
        return CaptchaType.IMAGE, {}

    return None


async def inject_captcha_solution(page, captcha_type: CaptchaType, solution: str) -> bool:
    """
    Inject CAPTCHA solution into the page.

    Args:
        page: Playwright page object.
        captcha_type: Type of CAPTCHA.
        solution: The solution token/text.

    Returns:
        True if injection succeeded.
    """
    try:
        if captcha_type in (CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_V3):
            # Set the g-recaptcha-response textarea
            await page.evaluate(f'''
                document.getElementById("g-recaptcha-response").innerHTML = "{solution}";
                if (typeof grecaptcha !== 'undefined') {{
                    grecaptcha.getResponse = function() {{ return "{solution}"; }};
                }}
            ''')

            # Also try callback if exists
            await page.evaluate(f'''
                if (typeof ___grecaptcha_cfg !== 'undefined') {{
                    Object.keys(___grecaptcha_cfg.clients).forEach(function(key) {{
                        var client = ___grecaptcha_cfg.clients[key];
                        if (client && client.callback) {{
                            client.callback("{solution}");
                        }}
                    }});
                }}
            ''')

        elif captcha_type == CaptchaType.HCAPTCHA:
            await page.evaluate(f'''
                document.querySelector('[name="h-captcha-response"]').value = "{solution}";
                document.querySelector('[name="g-recaptcha-response"]').value = "{solution}";
            ''')

        elif captcha_type == CaptchaType.IMAGE:
            # Find the input field near the CAPTCHA image
            captcha_input = await page.query_selector('input[name*="captcha" i], input[type="text"][id*="captcha" i]')
            if captcha_input:
                await captcha_input.fill(solution)

        logger.info(f"Injected {captcha_type.value} solution")
        return True

    except Exception as e:
        logger.error(f"Failed to inject CAPTCHA solution: {e}")
        return False
