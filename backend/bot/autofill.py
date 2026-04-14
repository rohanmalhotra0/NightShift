"""Claude auto-fill logic for job application forms."""

import json
import logging
import re
from typing import Optional
from dataclasses import dataclass, field

import anthropic

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class FormField:
    """Represents a form field on the page."""
    selector: str
    field_type: str  # text, select, checkbox, radio, textarea, file
    name: Optional[str] = None
    label: Optional[str] = None
    placeholder: Optional[str] = None
    options: list[str] = field(default_factory=list)  # For select/radio
    required: bool = False
    current_value: Optional[str] = None


@dataclass
class UserProfile:
    """User profile data for auto-filling."""
    # Personal info
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

    # Address
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "United States"

    # Work authorization
    work_authorization: Optional[str] = None
    requires_sponsorship: bool = False

    # Preferences
    salary_expectation: Optional[str] = None
    available_start_date: Optional[str] = None
    willing_to_relocate: bool = True
    remote_preference: str = "any"

    # Resume content (parsed text)
    resume_text: Optional[str] = None

    # Custom answers (for specific questions)
    custom_answers: dict = field(default_factory=dict)


@dataclass
class AutoFillResult:
    """Result from auto-fill operation."""
    success: bool
    field_mappings: dict[str, str]  # selector -> value
    tokens_used: int = 0
    error: Optional[str] = None


class AutoFiller:
    """Uses Claude to intelligently fill job application forms."""

    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate_field_mappings(
        self,
        fields: list[FormField],
        user_profile: UserProfile,
        job_description: Optional[str] = None,
    ) -> AutoFillResult:
        """
        Generate field mappings using Claude.

        Args:
            fields: List of form fields to fill.
            user_profile: User's profile data.
            job_description: Optional job description for context.

        Returns:
            AutoFillResult with field mappings.
        """
        # Build prompt
        prompt = self._build_prompt(fields, user_profile, job_description)

        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            content = response.content[0].text
            mappings = self._parse_response(content)

            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            return AutoFillResult(
                success=True,
                field_mappings=mappings,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error(f"Auto-fill generation failed: {e}")
            return AutoFillResult(
                success=False,
                field_mappings={},
                error=str(e),
            )

    def generate_cover_letter(
        self,
        user_profile: UserProfile,
        job_title: str,
        company: str,
        job_description: str,
        max_words: int = 300,
    ) -> tuple[Optional[str], int]:
        """
        Generate a cover letter using Claude.

        Args:
            user_profile: User's profile data.
            job_title: Job title applying for.
            company: Company name.
            job_description: Full job description.
            max_words: Maximum word count.

        Returns:
            Tuple of (cover letter text, tokens used).
        """
        prompt = f"""Write a professional cover letter for the following job application.

APPLICANT PROFILE:
Name: {user_profile.first_name} {user_profile.last_name}
Email: {user_profile.email}

RESUME:
{user_profile.resume_text or "Not provided"}

JOB DETAILS:
Position: {job_title}
Company: {company}

JOB DESCRIPTION:
{job_description}

REQUIREMENTS:
- Maximum {max_words} words
- Professional but personable tone
- Highlight relevant experience from resume
- Show genuine interest in the company
- Do NOT include any salutation or signature (just the body)
- Do NOT make up experience not in the resume

Write the cover letter body now:"""

        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            cover_letter = response.content[0].text.strip()
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            return cover_letter, tokens_used

        except Exception as e:
            logger.error(f"Cover letter generation failed: {e}")
            return None, 0

    def answer_question(
        self,
        question: str,
        user_profile: UserProfile,
        job_context: Optional[str] = None,
        options: Optional[list[str]] = None,
        max_length: Optional[int] = None,
    ) -> tuple[str, int]:
        """
        Answer a specific application question using Claude.

        Args:
            question: The question text.
            user_profile: User's profile data.
            job_context: Optional job description or context.
            options: Optional list of multiple choice options.
            max_length: Optional max character length for answer.

        Returns:
            Tuple of (answer text, tokens used).
        """
        prompt = f"""Answer the following job application question based on the provided profile.

APPLICANT PROFILE:
Name: {user_profile.first_name} {user_profile.last_name}
Work Authorization: {user_profile.work_authorization or "Not specified"}
Requires Sponsorship: {"Yes" if user_profile.requires_sponsorship else "No"}
Willing to Relocate: {"Yes" if user_profile.willing_to_relocate else "No"}

RESUME:
{user_profile.resume_text or "Not provided"}

{f"JOB CONTEXT: {job_context}" if job_context else ""}

QUESTION: {question}

{f"OPTIONS: {', '.join(options)}" if options else ""}
{f"MAX LENGTH: {max_length} characters" if max_length else ""}

INSTRUCTIONS:
- Answer concisely and professionally
- If multiple choice, respond with ONLY the option text
- If unknown, provide a reasonable professional response
- Never lie or make up information not in the profile

ANSWER:"""

        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )

            answer = response.content[0].text.strip()
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            # Truncate if needed
            if max_length and len(answer) > max_length:
                answer = answer[:max_length - 3] + "..."

            return answer, tokens_used

        except Exception as e:
            logger.error(f"Question answering failed: {e}")
            return "", 0

    def _build_prompt(
        self,
        fields: list[FormField],
        user_profile: UserProfile,
        job_description: Optional[str],
    ) -> str:
        """Build the prompt for field mapping."""
        fields_json = []
        for f in fields:
            fields_json.append({
                "selector": f.selector,
                "type": f.field_type,
                "name": f.name,
                "label": f.label,
                "placeholder": f.placeholder,
                "options": f.options,
                "required": f.required,
            })

        profile_data = {
            "first_name": user_profile.first_name,
            "last_name": user_profile.last_name,
            "full_name": f"{user_profile.first_name} {user_profile.last_name}",
            "email": user_profile.email,
            "phone": user_profile.phone,
            "linkedin": user_profile.linkedin_url,
            "github": user_profile.github_url,
            "portfolio": user_profile.portfolio_url,
            "address": user_profile.address,
            "city": user_profile.city,
            "state": user_profile.state,
            "zip": user_profile.zip_code,
            "country": user_profile.country,
            "work_auth": user_profile.work_authorization,
            "needs_sponsorship": user_profile.requires_sponsorship,
            "salary": user_profile.salary_expectation,
            "start_date": user_profile.available_start_date,
            "relocate": user_profile.willing_to_relocate,
            "remote_pref": user_profile.remote_preference,
        }

        prompt = f"""You are filling out a job application form. Map the user's profile data to the form fields.

USER PROFILE:
{json.dumps(profile_data, indent=2)}

RESUME CONTENT:
{user_profile.resume_text or "Not provided"}

{f"JOB DESCRIPTION: {job_description}" if job_description else ""}

FORM FIELDS:
{json.dumps(fields_json, indent=2)}

INSTRUCTIONS:
1. For each form field, determine the best value from the user's profile
2. For select/radio fields, choose from the available options
3. For checkbox fields, use "true" or "false"
4. For text fields about experience, extract from the resume
5. Skip file upload fields (type: "file")
6. For fields you cannot fill, use empty string ""

Return a JSON object mapping each field's selector to its value:
{{"selector1": "value1", "selector2": "value2", ...}}

Only return the JSON, no other text."""

        return prompt

    def _parse_response(self, response: str) -> dict[str, str]:
        """Parse Claude's response to extract field mappings."""
        # Try to extract JSON from response
        try:
            # Handle markdown code blocks
            if "```" in response:
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
                if match:
                    response = match.group(1)

            return json.loads(response.strip())
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON response")
            return {}


async def extract_form_fields(page) -> list[FormField]:
    """
    Extract form fields from a Playwright page.

    Args:
        page: Playwright page object.

    Returns:
        List of FormField objects.
    """
    fields = []

    # Extract all form inputs
    form_elements = await page.query_selector_all(
        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), '
        'select, textarea'
    )

    for element in form_elements:
        try:
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            field_type = "text"

            if tag_name == "select":
                field_type = "select"
            elif tag_name == "textarea":
                field_type = "textarea"
            else:
                input_type = await element.get_attribute("type") or "text"
                field_type = input_type

            # Get selectors
            element_id = await element.get_attribute("id")
            element_name = await element.get_attribute("name")
            element_class = await element.get_attribute("class")

            if element_id:
                selector = f"#{element_id}"
            elif element_name:
                selector = f'[name="{element_name}"]'
            else:
                # Generate unique selector
                selector = await element.evaluate('''el => {
                    const path = [];
                    while (el && el.nodeType === Node.ELEMENT_NODE) {
                        let selector = el.tagName.toLowerCase();
                        if (el.id) {
                            selector += '#' + el.id;
                            path.unshift(selector);
                            break;
                        }
                        const siblings = Array.from(el.parentNode?.children || []);
                        const index = siblings.indexOf(el) + 1;
                        if (siblings.length > 1) selector += ':nth-child(' + index + ')';
                        path.unshift(selector);
                        el = el.parentNode;
                    }
                    return path.join(' > ');
                }''')

            # Get label
            label = None
            if element_id:
                label_el = await page.query_selector(f'label[for="{element_id}"]')
                if label_el:
                    label = await label_el.inner_text()

            # Get options for select
            options = []
            if field_type == "select":
                option_els = await element.query_selector_all("option")
                for opt in option_els:
                    text = await opt.inner_text()
                    if text.strip():
                        options.append(text.strip())

            fields.append(FormField(
                selector=selector,
                field_type=field_type,
                name=element_name,
                label=label,
                placeholder=await element.get_attribute("placeholder"),
                options=options,
                required=await element.get_attribute("required") is not None,
                current_value=await element.input_value() if field_type != "file" else None,
            ))

        except Exception as e:
            logger.debug(f"Failed to extract field: {e}")
            continue

    return fields


async def fill_form_fields(page, mappings: dict[str, str]) -> int:
    """
    Fill form fields on a Playwright page.

    Args:
        page: Playwright page object.
        mappings: Dict mapping selectors to values.

    Returns:
        Number of fields successfully filled.
    """
    filled = 0

    for selector, value in mappings.items():
        if not value:
            continue

        try:
            element = await page.query_selector(selector)
            if not element:
                logger.debug(f"Selector not found: {selector}")
                continue

            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            input_type = await element.get_attribute("type") if tag_name == "input" else None

            if tag_name == "select":
                await element.select_option(label=value)
            elif tag_name == "textarea":
                await element.fill(value)
            elif input_type == "checkbox":
                is_checked = await element.is_checked()
                should_check = value.lower() in ("true", "yes", "1")
                if is_checked != should_check:
                    await element.click()
            elif input_type == "radio":
                # Find the radio with matching value
                radio = await page.query_selector(f'{selector}[value="{value}"]')
                if radio:
                    await radio.click()
            elif input_type == "file":
                # Skip file inputs
                continue
            else:
                await element.fill(value)

            filled += 1

        except Exception as e:
            logger.warning(f"Failed to fill {selector}: {e}")
            continue

    logger.info(f"Filled {filled}/{len(mappings)} fields")
    return filled
