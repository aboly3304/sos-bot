import json
import logging
from typing import Dict, Any, List, Optional

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)


class SheetStorage:
    """
    Thin wrapper around Google Sheets.
    - registrations
    - sos_sessions
    - resource_requests
    - helpers
    - medical_info (optional)
    """

    def __init__(
        self,
        sheet_id: str,
        credentials_json: str,
        registrations_sheet_name: str = "registrations",
        sos_sessions_sheet_name: str = "sos_sessions",
        resource_requests_sheet_name: str = "resource_requests",
        helpers_sheet_name: str = "helpers",
        medical_sheet_name: str = "medical",
    ) -> None:
        self.sheet_id = sheet_id

        creds_info = json.loads(credentials_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)

        self._file = client.open_by_key(sheet_id)

        self._registrations = self._file.worksheet(registrations_sheet_name)
        self._sos_sessions = self._file.worksheet(sos_sessions_sheet_name)
        self._resource_requests = self._file.worksheet(resource_requests_sheet_name)
        self._helpers = self._file.worksheet(helpers_sheet_name)
        self._medical = self._file.worksheet(medical_sheet_name)

        logger.info("SheetStorage initialized with sheet_id=%s", sheet_id)

    # -------- Registrations --------

    def append_registration(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
        chat_id: int,
    ) -> None:
        row = [
            str(user_id),
            username or "",
            first_name or "",
            last_name or "",
            str(chat_id),
        ]
        self._registrations.append_row(row, value_input_option="USER_ENTERED")

    # -------- SOS sessions --------

    def log_new_sos_session(self, event_id: int, chat_id: int, requester_user_id: int) -> None:
        row = [
            str(event_id),
            str(chat_id),
            str(requester_user_id),
            "ACTIVE",
        ]
        self._sos_sessions.append_row(row, value_input_option="USER_ENTERED")

    def close_sos_session(self, event_id: int, closed_by_user_id: int) -> None:
        """
        Mark session as CLOSED in the sheet.
        """
        values = self._sos_sessions.get_all_values()
        if not values:
            return

        header = values[0]
        rows = values[1:]

        # Assume columns: event_id | chat_id | requester_user_id | status | closed_by
        for idx, row in enumerate(rows, start=2):
            if not row or len(row) < 1:
                continue
            if row[0] == str(event_id):
                # status
                if len(row) < 4:
                    row += [""] * (4 - len(row))
                row[3] = "CLOSED"

                if len(row) < 5:
                    row.append(str(closed_by_user_id))
                else:
                    row[4] = str(closed_by_user_id)

                self._sos_sessions.update(
                    f"A{idx}:E{idx}",
                    [row],
                    value_input_option="USER_ENTERED",
                )
                break

    def get_active_sos_sessions(self) -> List[Dict[str, Any]]:
        """
        Read active sessions for rehydration. Minimal implementation.
        """
        values = self._sos_sessions.get_all_values()
        if not values:
            return []

        header = values[0]
        rows = values[1:]

        res: List[Dict[str, Any]] = []
        for row in rows:
            if len(row) < 4:
                continue
            status = row[3]
            if status != "ACTIVE":
                continue
            try:
                event_id = int(row[0])
                chat_id = int(row[1])
                requester_user_id = int(row[2])
            except ValueError:
                continue

            res.append(
                {
                    "event_id": event_id,
                    "chat_id": chat_id,
                    "requester_user_id": requester_user_id,
                    "is_active": True,
                }
            )
        return res

    # -------- Resource requests --------

    def log_resource_request(self, event_id: int, user_id: int, resource_type: str) -> None:
        row = [
            str(event_id),
            str(user_id),
            resource_type,
        ]
        self._resource_requests.append_row(row, value_input_option="USER_ENTERED")

    # -------- Helpers --------

    def log_helper_optin(self, event_id: int, helper_user_id: int) -> None:
        row = [
            str(event_id),
            str(helper_user_id),
        ]
        self._helpers.append_row(row, value_input_option="USER_ENTERED")

    # -------- Medical info --------

    def get_user_medical_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Reads medical info row by user_id.
        Assumed structure:
        user_id | field | value
        or
        user_id | field1 | field2 | ...
        اینجا ساده: user_id | label | value
        """
        values = self._medical.get_all_values()
        if not values:
            return None

        res: Dict[str, Any] = {}
        for row in values[1:]:
            if len(row) < 3:
                continue
            if row[0] != str(user_id):
                continue
            label = row[1] or "field"
            value = row[2] or ""
            res[label] = value

        return res or None
