import logging
from typing import Optional

from .sheet_storage import SheetStorage

logger = logging.getLogger(__name__)


class SheetWriter:
    """
    Thin, semantic wrapper over SheetStorage.
    Keeps main.py + handlers decoupled from concrete sheet layout.
    """

    def __init__(self, storage: SheetStorage) -> None:
        self.storage = storage

    # -------- Registration --------

    def append_registration_row(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
        chat_id: int,
    ) -> None:
        logger.debug("Append registration row for user_id=%s", user_id)
        self.storage.append_registration(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            chat_id=chat_id,
        )

    # -------- SOS sessions --------

    def log_new_sos_session(self, event_id: int, chat_id: int, requester_user_id: int) -> None:
        logger.info(
            "Log new SOS session event_id=%s chat_id=%s requester=%s",
            event_id,
            chat_id,
            requester_user_id,
        )
        self.storage.log_new_sos_session(
            event_id=event_id,
            chat_id=chat_id,
            requester_user_id=requester_user_id,
        )

    def close_sos_session(self, event_id: int, closed_by_user_id: int) -> None:
        logger.info("Close SOS session event_id=%s closed_by=%s", event_id, closed_by_user_id)
        self.storage.close_sos_session(event_id=event_id, closed_by_user_id=closed_by_user_id)

    # -------- Resource requests --------

    def log_resource_request(self, event_id: int, user_id: int, resource_type: str) -> None:
        logger.info(
            "Resource request: event_id=%s user_id=%s type=%s",
            event_id,
            user_id,
            resource_type,
        )
        self.storage.log_resource_request(
            event_id=event_id, user_id=user_id, resource_type=resource_type
        )

    # -------- Helpers --------

    def log_helper_optin(self, event_id: int, helper_user_id: int) -> None:
        logger.info("Helper opt-in: event_id=%s helper=%s", event_id, helper_user_id)
        self.storage.log_helper_optin(event_id=event_id, helper_user_id=helper_user_id)
