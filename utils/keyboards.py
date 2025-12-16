from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def sos_main_keyboard(event_id: int) -> InlineKeyboardMarkup:
    """
    Keyboard shown under SOS message in گروه/سوپرگروه.
    """
    kb = [
        [
            InlineKeyboardButton("💧 آب", callback_data=f"sos:req:water:{event_id}"),
            InlineKeyboardButton("💊 دارو", callback_data=f"sos:req:medicine:{event_id}"),
            InlineKeyboardButton("💪 نیرو", callback_data=f"sos:req:power:{event_id}"),
        ],
        [
            InlineKeyboardButton("✅ کمک می‌کنم", callback_data=f"sos:optin:{event_id}"),
            InlineKeyboardButton("👥 یاری‌دهندگان", callback_data=f"sos:view_helpers:{event_id}"),
        ],
        [
            InlineKeyboardButton("🚫 خطر رفع شد", callback_data=f"sos:resolved:{event_id}"),
        ],
    ]
    return InlineKeyboardMarkup(kb)


def back_to_sos_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"sos:back:{event_id}")]]
    )
