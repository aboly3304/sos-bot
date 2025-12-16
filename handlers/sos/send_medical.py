import logging
from telegram import Update
from telegram.ext import ContextTypes

from storage.sheet_storage import SheetStorage

logger = logging.getLogger(__name__)


async def send_responder_medical_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    requester_user_id: int,
    responder_chat_id: int,
) -> None:
    """
    وقتی یاری‌دهنده روی «کمک می‌کنم» می‌زند، اطلاعات پزشکی درخواست‌کننده
    (در صورت ثبت در شیت) در PV برای یاری‌دهنده ارسال می‌شود.

    این تابع هرگز اطلاعات پزشکی را در گروه عمومی نمایش نمی‌دهد.
    """
    storage: SheetStorage = context.application.bot_data.get("sheet_storage")
    if storage is None:
        logger.error("SheetStorage not found in bot_data; cannot send medical info")
        return

    try:
        medical_info = storage.get_user_medical_info(requester_user_id)
    except Exception:
        logger.exception("Failed to read medical info for user_id=%s", requester_user_id)
        medical_info = None

    if not medical_info:
        text = (
            "ℹ️ اطلاعات پزشکی ثبت‌شده‌ای برای این فرد پیدا نشد.\n"
            "در صورت نیاز، حتماً قبل از اقدام با خودش هماهنگ کن."
        )
    else:
        text_lines = [
            "🩺 اطلاعات پزشکی ثبت‌شده برای این فرد:",
            "",
        ]
        for k, v in medical_info.items():
            text_lines.append(f"• {k}: {v}")
        text = "\n".join(text_lines)

    try:
        await context.bot.send_message(chat_id=responder_chat_id, text=text)
        logger.info(
            "Sent medical info of requester_user_id=%s to responder_chat_id=%s",
            requester_user_id,
            responder_chat_id,
        )
    except Exception:
        logger.exception(
            "Failed to send medical info of requester_user_id=%s to responder_chat_id=%s",
            requester_user_id,
            responder_chat_id,
        )
