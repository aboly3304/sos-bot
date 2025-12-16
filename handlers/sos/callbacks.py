import logging
from typing import Dict, Any, Optional

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from utils.keyboards import sos_main_keyboard
from storage.sheet_writer import SheetWriter
from handlers.sos.send_medical import send_responder_medical_message

logger = logging.getLogger(__name__)


# ---------- /sos command ----------


async def handle_sos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /sos – must be used in a group/supergroup.
    Creates a new SOS "session" where the group message is the SSOT.
    """
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await chat.send_message("دستور /sos فقط در گروه/سوپرگروه قابل استفاده است.")
        return

    text = (
        f"🚨 *درخواست کمک اضطراری*\n\n"
        f"درخواست‌کننده: [{user.full_name}](tg://user?id={user.id})\n"
        f"اگر می‌توانید کمک کنید، روی «کمک می‌کنم» بزنید.\n"
        f"و در صورت نیاز نوع کمک (آب / دارو / نیرو) را انتخاب کنید."
    )

    msg = await chat.send_message(
        text=text,
        reply_markup=sos_main_keyboard(event_id=0),  # event_id بعد از ارسال تنظیم می‌شود
        parse_mode=ParseMode.MARKDOWN,
    )

    event_id = msg.message_id

    # به‌روز کردن کیبورد با event_id واقعی
    try:
        await msg.edit_reply_markup(reply_markup=sos_main_keyboard(event_id=event_id))
    except Exception:
        logger.exception("Failed to update SOS keyboard with real event_id=%s", event_id)

    # نگهداری در bot_data
    session = {
        "event_id": event_id,
        "chat_id": chat.id,
        "requester_user_id": user.id,
        "is_active": True,
        "helpers": set(),
    }

    active_sos: Dict[int, Dict[str, Any]] = context.application.bot_data.setdefault(
        "active_sos_sessions", {}
    )
    active_sos[event_id] = session

    writer: Optional[SheetWriter] = context.application.bot_data.get("sheet_writer")
    if writer:
        try:
            writer.log_new_sos_session(
                event_id=event_id,
                chat_id=chat.id,
                requester_user_id=user.id,
            )
        except Exception:
            logger.exception("Failed to log new SOS session to sheet")

    logger.info("New SOS started: event_id=%s by user_id=%s", event_id, user.id)


# ---------- Callback router ----------


async def sos_button_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Single entry for all sos:* callback_data.
    """
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    if not data.startswith("sos:"):
        # Not ours
        return

    await query.answer()  # small feedback

    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else None

    if action == "req":
        # sos:req:<resource>:<event_id>
        await _handle_resource_request(update, context, parts)
    elif action == "optin":
        # sos:optin:<event_id>
        await _handle_optin(update, context, parts)
    elif action == "view_helpers":
        # sos:view_helpers:<event_id>
        await _handle_view_helpers(update, context, parts)
    elif action == "resolved":
        # sos:resolved:<event_id>
        await _handle_resolved(update, context, parts)
    elif action == "back":
        # sos:back:<event_id>  (reserved – فعلاً نادیده می‌گیریم)
        return
    else:
        logger.warning("Unknown SOS callback action: %s", data)


def _get_session(context: ContextTypes.DEFAULT_TYPE, event_id: int) -> Optional[Dict[str, Any]]:
    sessions: Dict[int, Dict[str, Any]] = context.application.bot_data.get(
        "active_sos_sessions", {}
    )
    return sessions.get(event_id)


# ---------- Resource request (آب/دارو/نیرو) ----------


async def _handle_resource_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
) -> None:
    query = update.callback_query
    user = update.effective_user

    if len(parts) != 4:
        logger.warning("Invalid resource request callback_data=%s", query.data)
        return

    resource_type = parts[2]
    try:
        event_id = int(parts[3])
    except ValueError:
        logger.warning("Invalid event_id in callback_data=%s", query.data)
        return

    session = _get_session(context, event_id)
    if not session or not session.get("is_active", False):
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("این SOS دیگر فعال نیست.")
        return

    # Log to sheet
    writer: Optional[SheetWriter] = context.application.bot_data.get("sheet_writer")
    if writer:
        try:
            writer.log_resource_request(
                event_id=event_id,
                user_id=user.id,
                resource_type=resource_type,
            )
        except Exception:
            logger.exception("Failed to log resource request")

    # Reply in group (not flooding)
    await query.message.reply_text(
        f"✅ درخواست *{_resource_label(resource_type)}* ثبت شد.",
        parse_mode=ParseMode.MARKDOWN,
    )


def _resource_label(resource_type: str) -> str:
    if resource_type == "water":
        return "آب"
    if resource_type == "medicine":
        return "دارو"
    if resource_type == "power":
        return "نیروی فیزیکی"
    return resource_type


# ---------- Opt-in (کمک می‌کنم) ----------


async def _handle_optin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
) -> None:
    query = update.callback_query
    user = update.effective_user
    chat = update.effective_chat

    if len(parts) != 3:
        logger.warning("Invalid optin callback_data=%s", query.data)
        return

    try:
        event_id = int(parts[2])
    except ValueError:
        logger.warning("Invalid event_id in optin callback_data=%s", query.data)
        return

    session = _get_session(context, event_id)
    if not session or not session.get("is_active", False):
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("این SOS دیگر فعال نیست.")
        return

    helpers: set[int] = session.setdefault("helpers", set())
    if user.id not in helpers:
        helpers.add(user.id)

    writer: Optional[SheetWriter] = context.application.bot_data.get("sheet_writer")
    if writer:
        try:
            writer.log_helper_optin(
                event_id=event_id,
                helper_user_id=user.id,
            )
        except Exception:
            logger.exception("Failed to log helper opt-in")

    await query.answer("ثبت شد، لطفاً منتظر هماهنگی بمانید.", show_alert=False)

    # پیام کوتاه برای گروه
    await query.message.reply_text(
        f"🙋‍♂️ [{user.full_name}](tg://user?id={user.id}) اعلام کرد که کمک می‌کند.",
        parse_mode=ParseMode.MARKDOWN,
    )

    # ارسال اطلاعات پزشکی درخواست‌کننده به PV یاری‌دهنده (در صورت وجود)
    await send_responder_medical_message(
        update=update,
        context=context,
        requester_user_id=session["requester_user_id"],
        responder_chat_id=user.id,
    )


# ---------- View helpers ----------


async def _handle_view_helpers(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
) -> None:
    query = update.callback_query

    if len(parts) != 3:
        logger.warning("Invalid view_helpers callback_data=%s", query.data)
        return

    try:
        event_id = int(parts[2])
    except ValueError:
        logger.warning("Invalid event_id in view_helpers callback_data=%s", query.data)
        return

    session = _get_session(context, event_id)
    if not session:
        await query.answer("این SOS دیگر فعال نیست.", show_alert=True)
        return

    helpers: set[int] = session.get("helpers", set())

    if not helpers:
        await query.answer("هنوز کسی اعلام کمک نکرده.", show_alert=True)
        return

    mention_list = [f"[کاربر](tg://user?id={hid})" for hid in helpers]
    text = "👥 یاری‌دهندگان تا این لحظه:\n" + "\n".join(f"• {m}" for m in mention_list)

    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ---------- Resolved (خطر رفع شد) ----------


async def _handle_resolved(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
) -> None:
    query = update.callback_query
    user = update.effective_user

    if len(parts) != 3:
        logger.warning("Invalid resolved callback_data=%s", query.data)
        return

    try:
        event_id = int(parts[2])
    except ValueError:
        logger.warning("Invalid event_id in resolved callback_data=%s", query.data)
        return

    session = _get_session(context, event_id)
    if not session:
        await query.answer("این SOS پیدا نشد.", show_alert=True)
        return

    if not session.get("is_active", False):
        await query.answer("این SOS قبلاً بسته شده.", show_alert=True)
        return

    requester_id = session["requester_user_id"]

    # فقط درخواست‌کننده (یا بعداً ادمین) اجازه بستن دارد
    if user.id != requester_id:
        await query.answer("فقط درخواست‌کننده می‌تواند خطر را رفع‌شده اعلام کند.", show_alert=True)
        return

    session["is_active"] = False

    # حذف از لیست فعال
    active_sos: Dict[int, Dict[str, Any]] = context.application.bot_data.get(
        "active_sos_sessions", {}
    )
    active_sos.pop(event_id, None)

    writer: Optional[SheetWriter] = context.application.bot_data.get("sheet_writer")
    if writer:
        try:
            writer.close_sos_session(event_id=event_id, closed_by_user_id=user.id)
        except Exception:
            logger.exception("Failed to close SOS session in sheet")

    # بروزرسانی پیام گروهی
    try:
        await query.message.edit_text(
            text="✅ این SOS به‌صورت موفقیت‌آمیز بسته شد.\n"
            "از همه یاری‌دهندگان سپاسگزاریم.",
        )
    except Exception:
        logger.exception("Failed to edit SOS message to resolved state")

    await query.answer("SOS بسته شد.", show_alert=False)
    logger.info("SOS resolved: event_id=%s by user_id=%s", event_id, user.id)
