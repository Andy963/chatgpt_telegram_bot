#!/usr/bin/python
# coding:utf-8

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from bot import config
from bot.bot import start_handle, help_handle, message_handle, retry_handle, new_dialog_handle, show_chat_modes_handle, \
    set_chat_mode_handle, error_handle, voice_message_handle, photo_handle, dispatch_callback_handle, balance_handle


def run_bot() -> None:
    application = (
        ApplicationBuilder()
        .token(config.telegram_token)
        .build()
    )

    # add handlers
    if len(config.allowed_telegram_usernames) == 0:
        user_filter = filters.ALL
    else:
        user_filter = filters.User(username=config.allowed_telegram_usernames)

    application.add_handler(CommandHandler("start", start_handle, filters=user_filter))
    application.add_handler(CommandHandler("help", help_handle, filters=user_filter))
    application.add_handler(CommandHandler("balance", balance_handle, filters=user_filter))
    application.add_handler(CommandHandler("retry", retry_handle, filters=user_filter))
    application.add_handler(CommandHandler("new", new_dialog_handle, filters=user_filter))
    application.add_handler(CommandHandler("mode", show_chat_modes_handle, filters=user_filter))
    application.add_handler(CallbackQueryHandler(set_chat_mode_handle, pattern="^set_chat_mode"))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & user_filter, message_handle))
    application.add_handler(MessageHandler(filters.VOICE & user_filter, voice_message_handle))
    application.add_handler(MessageHandler(filters.PHOTO & user_filter, photo_handle))
    application.add_handler(CallbackQueryHandler(dispatch_callback_handle, ))
    application.add_error_handler(error_handle)

    # start the bot
    application.run_polling()


if __name__ == "__main__":
    from bot.log import logger

    logger.info('Starting bot...')
    run_bot()
