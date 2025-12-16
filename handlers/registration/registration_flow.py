import logging
from telegram import Update
from telegram.ext import ContextTypes

from storage.sheet_writer import SheetWriter

logger = logging.getLogger(__name__)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start – simple registration: store user basic profile to Google Sheet.
    Silent registration, no multi-step state.
    """
    user = update.effective_user
    chat = update.effective_chat

    writer: SheetWriter = context.application.bot_data.get("sheet_writer")
    if writer is None:
        logger.error("SheetWriter not found in bot_data; registration skipped")
    else:
        try:
            writer.append_registration_row(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                chat_id=chat.id,
            )
            logger.info("Registered user_id=%s to sheet", user.id)
        except Exception:
            logger.exception("Failed to append registration row for user_id=%s", user.id)

    text = (
        "سلام 👋\n"
        "ثبت‌نام اولیه شما انجام شد.\n"
        "هر زمان در برنامه به کمک نیاز داشتی، دستور /sos رو بفرست."
    )
    await update.effective_chat.send_message(text=text)

