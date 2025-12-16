
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from handlers.registration.registration_flow import handle_start
from handlers.sos.callback_controller import (
    sos_button_router,
    handle_sos_command,
)
from storage.sheet_storage import SheetStorage
from storage.sheet_writer import SheetWriter

# ---------- Logging ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("sos_main")


def load_env() -> None:
    """Load .env if exists."""
    load_dotenv()
    logger.info(".env loaded (if present)")


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        logger.critical("Missing required ENV %s", name)
        raise RuntimeError(f"Missing required ENV: {name}")
    return value


async def on_startup(app) -> None:
    """
    Startup hook: initialize SheetStorage + rehydrate if needed.
    """
    logger.info("Application starting up...")

    sheet_id = get_required_env("GOOGLE_SHEET_ID")
    credentials_json = get_required_env("GOOGLE_SERVICE_ACCOUNT_JSON")

    storage = SheetStorage(sheet_id=sheet_id, credentials_json=credentials_json)
    writer = SheetWriter(storage=storage)

    # attach to application so handlers can use
    app.bot_data["sheet_storage"] = storage
    app.bot_data["sheet_writer"] = writer

    # Rehydrate any active SOS from sheet (stateless model)
    try:
        active_sessions = storage.get_active_sos_sessions()
        logger.info("Rehydrated %d active SOS sessions from sheet", len(active_sessions))
        app.bot_data["active_sos_sessions"] = {s["event_id"]: s for s in active_sessions}
    except Exception:
        logger.exception("Failed to rehydrate SOS sessions from Google Sheet")
        app.bot_data["active_sos_sessions"] = {}

    logger.info("Startup completed")


async def on_shutdown(app) -> None:
    logger.info("Application shutting down...")


def build_application() -> "Application":
    load_env()
    token = get_required_env("BOT_TOKEN")

    logger.info("Building Telegram application...")
    application = (
        ApplicationBuilder()
        .token(token)
        .concurrent_updates(True)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    # /start -> registration flow
    application.add_handler(CommandHandler("start", handle_start))

    # /sos -> create new SOS event
    application.add_handler(CommandHandler("sos", handle_sos_command))

    # /admin (optional, for future extension)
    # application.add_handler(CommandHandler("admin", handle_admin))

    # Callback buttons for all SOS logic
    application.add_handler(CallbackQueryHandler(sos_button_router))

    # Optionally, handle plain text for debugging
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None),
        group=99,
    )

    return application


def main() -> None:
    try:
        app = build_application()
        logger.info("Starting polling...")
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.exception("Fatal error in main: %s", e)
        raise


if __name__ == "__main__":
    main()
