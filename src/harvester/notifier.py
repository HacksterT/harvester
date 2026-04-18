import logging
import os

logger = logging.getLogger(__name__)

# Stub — upgraded to real Telegram in F02-S06.
# All call sites use send() with a plain string message.
# The scheduler and writer import this module directly.


async def send(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.info("[Telegram stub] %s", message)
        return
    # Real implementation wired in F02-S06.
    logger.info("[Telegram not yet wired] %s", message)
