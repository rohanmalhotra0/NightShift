"""Google Sheets integration for logging applications."""

import json
import logging
from typing import Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Default sheet headers
DEFAULT_HEADERS = [
    "Date",
    "Job Title",
    "Company",
    "URL",
    "Status",
    "Resume Used",
    "Answers",
    "Notes",
]


class GoogleSheetsLogger:
    """Logs job applications to Google Sheets."""

    def __init__(self, credentials_json: Optional[str] = None):
        """
        Initialize Google Sheets logger.

        Args:
            credentials_json: Service account credentials as JSON string.
        """
        self.credentials_json = credentials_json or settings.GOOGLE_SHEETS_CREDENTIALS
        self.sheets_service = None
        self.drive_service = None
        self._creds = None

    def authenticate(self) -> bool:
        """Authenticate with Google APIs."""
        try:
            if not self.credentials_json:
                logger.warning("No Google Sheets credentials provided")
                return False

            creds_dict = json.loads(self.credentials_json)
            self._creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

            self.sheets_service = build("sheets", "v4", credentials=self._creds)
            self.drive_service = build("drive", "v3", credentials=self._creds)

            logger.info("Google Sheets authenticated")
            return True

        except Exception as e:
            logger.error(f"Google Sheets authentication failed: {e}")
            return False

    def create_sheet_for_user(self, user_email: str, user_name: str = "User") -> Optional[str]:
        """
        Create a new spreadsheet for a user and share it with them.

        Args:
            user_email: User's email to share the sheet with.
            user_name: User's name for the sheet title.

        Returns:
            Spreadsheet ID if created, None otherwise.
        """
        if not self.sheets_service:
            if not self.authenticate():
                return None

        try:
            # Create spreadsheet
            spreadsheet = {
                "properties": {
                    "title": f"NightShift Applications - {user_name}",
                },
                "sheets": [
                    {
                        "properties": {
                            "title": "Applications",
                            "gridProperties": {
                                "frozenRowCount": 1,
                            },
                        },
                    },
                ],
            }

            result = self.sheets_service.spreadsheets().create(
                body=spreadsheet
            ).execute()

            spreadsheet_id = result["spreadsheetId"]
            logger.info(f"Created spreadsheet: {spreadsheet_id}")

            # Add headers
            self._add_headers(spreadsheet_id)

            # Share with user
            self._share_with_user(spreadsheet_id, user_email)

            return spreadsheet_id

        except Exception as e:
            logger.error(f"Failed to create spreadsheet: {e}")
            return None

    def _add_headers(self, spreadsheet_id: str) -> None:
        """Add header row to spreadsheet."""
        try:
            body = {
                "values": [DEFAULT_HEADERS],
            }

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="Applications!A1",
                valueInputOption="RAW",
                body=body,
            ).execute()

            # Format headers (bold)
            requests = [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                                "backgroundColor": {
                                    "red": 0.9,
                                    "green": 0.9,
                                    "blue": 0.9,
                                },
                            },
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor)",
                    },
                },
            ]

            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            ).execute()

        except Exception as e:
            logger.warning(f"Failed to add headers: {e}")

    def _share_with_user(self, spreadsheet_id: str, email: str) -> None:
        """Share spreadsheet with user."""
        try:
            permission = {
                "type": "user",
                "role": "writer",
                "emailAddress": email,
            }

            self.drive_service.permissions().create(
                fileId=spreadsheet_id,
                body=permission,
                sendNotificationEmail=True,
            ).execute()

            logger.info(f"Shared spreadsheet with {email}")

        except Exception as e:
            logger.warning(f"Failed to share spreadsheet: {e}")

    def append_application(
        self,
        sheets_id: str,
        date: str,
        job_title: str,
        company: str,
        url: str,
        status: str,
        resume_name: str = "",
        answers: str = "",
        notes: str = "",
    ) -> bool:
        """
        Append a new application row to the spreadsheet.

        Args:
            sheets_id: Spreadsheet ID.
            date: Application date/time.
            job_title: Job title.
            company: Company name.
            url: Job URL.
            status: Application status.
            resume_name: Resume filename used.
            answers: JSON string of answers used.
            notes: Additional notes.

        Returns:
            True if successful.
        """
        if not self.sheets_service:
            if not self.authenticate():
                return False

        try:
            row = [
                date,
                job_title,
                company,
                url,
                status,
                resume_name,
                answers[:1000] if len(answers) > 1000 else answers,  # Truncate long answers
                notes,
            ]

            body = {"values": [row]}

            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=sheets_id,
                range="Applications!A:H",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()

            logger.debug(f"Appended row to {sheets_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to append row: {e}")
            return False

    def get_application_count(self, sheets_id: str) -> int:
        """Get total number of applications logged."""
        if not self.sheets_service:
            if not self.authenticate():
                return 0

        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheets_id,
                range="Applications!A:A",
            ).execute()

            values = result.get("values", [])
            return max(0, len(values) - 1)  # Subtract header row

        except Exception as e:
            logger.error(f"Failed to get count: {e}")
            return 0

    def get_recent_applications(
        self,
        sheets_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get recent applications from the sheet.

        Args:
            sheets_id: Spreadsheet ID.
            limit: Maximum number of rows to return.

        Returns:
            List of application dicts.
        """
        if not self.sheets_service:
            if not self.authenticate():
                return []

        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheets_id,
                range="Applications!A:H",
            ).execute()

            values = result.get("values", [])

            if len(values) <= 1:
                return []

            headers = values[0]
            rows = values[1:][-limit:]  # Get last N rows

            applications = []
            for row in reversed(rows):
                app = {}
                for i, header in enumerate(headers):
                    app[header.lower().replace(" ", "_")] = row[i] if i < len(row) else ""
                applications.append(app)

            return applications

        except Exception as e:
            logger.error(f"Failed to get applications: {e}")
            return []

    def update_application_status(
        self,
        sheets_id: str,
        row_number: int,
        new_status: str,
    ) -> bool:
        """Update the status of an application row."""
        if not self.sheets_service:
            if not self.authenticate():
                return False

        try:
            # Status is in column E (index 4)
            cell_range = f"Applications!E{row_number + 1}"

            body = {"values": [[new_status]]}

            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=sheets_id,
                range=cell_range,
                valueInputOption="RAW",
                body=body,
            ).execute()

            return True

        except Exception as e:
            logger.error(f"Failed to update status: {e}")
            return False
