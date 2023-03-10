import html
import json
import logging
import math
import os.path
import time
import traceback
import wave
from datetime import datetime

import openai
import telegram
from pydub import AudioSegment
from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackContext

from . import chatgpt
from . import config
from .database import Database
from .helper import send_like_tying, render_msg_with_code, text_to_speech

# setup

db = Database()
logger = logging.getLogger(__name__)

HELP_MESSAGE = """Commands:
⚪ /retry – Regenerate last bot answer
⚪ /new – Start new dialog
⚪ /mode – Select chat mode
⚪ /balance – Show balance
⚪ /help – Show help
"""


async def register_user_if_not_exists(update: Update, context: CallbackContext, user: User):
    if not db.check_if_user_exists(user.id):
        db.add_new_user(
            user.id,
            update.message.chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )


async def start_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id

    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    db.start_new_dialog(user_id)

    reply_text = "Hi! I'm <b>ChatGPT</b> bot implemented with GPT-3.5 OpenAI API 🤖\n\n"
    reply_text += HELP_MESSAGE

    reply_text += "\nAnd now... ask me anything!"

    await update.message.reply_text(reply_text)


async def help_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML)


async def retry_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    dialog_messages = db.get_dialog_messages(user_id, dialog_id=None)
    if len(dialog_messages) == 0:
        await update.message.reply_text("No message to retry 🤷‍♂️")
        return

    last_dialog_message = dialog_messages.pop()
    db.set_dialog_messages(user_id, dialog_messages, dialog_id=None)  # last message was removed from the context

    await message_handle(update, context, message=last_dialog_message["user"], use_new_dialog_timeout=False)


async def message_handle(update: Update, context: CallbackContext, message=None, use_new_dialog_timeout=True):
    # check if message is edited

    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return

    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id

    # new dialog timeout
    if use_new_dialog_timeout:
        if (datetime.now() - db.get_user_attribute(user_id, "last_interaction")).seconds > config.new_dialog_timeout:
            db.start_new_dialog(user_id)
            await update.message.reply_text("Starting new dialog due to timeout ✅")
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    # send typing action
    await update.message.chat.send_action(action="typing")
    name = f"{update.message.chat_id}{int(time.time())}"
    try:
        # get voice message and use whisper api translate it to text
        if update.message.voice:
            new_file = await context.bot.get_file(update.message.voice.file_id)
            a_file = f"{name}.mp3"
            await new_file.download_to_drive(f'{name}.ogg')
            audio = AudioSegment.from_file(f'{name}.ogg')
            audio.export(a_file, format="mp3")
            with open(a_file, 'rb') as f:
                await update.message.chat.send_action(action='record_audio')
                transaction = openai.Audio.transcribe("whisper-1", f, language=config.default_language)
                if config.reply_with_voice:
                    audio_file = text_to_speech(config.azure_speech_key,
                                                config.azure_speech_region,
                                                config.azure_speech_lang,
                                                config.azure_speech_voice,
                                                update.message.chat_id,
                                                transaction.text)
                    # if text to speech failed - send text
                    await update.message.chat.send_action(action='typing')
                    if audio_file:
                        await reply_multi_voice(update, context, audio_file)
                        os.remove(audio_file)
                    else:
                        # translate text to speech failed - send text
                        tip = "Sorry, I can't work with this audio messages 🙁. so I will send you text"
                        if config.typing_effect:
                            await send_like_tying(update, context, tip + transaction.text)
                        else:
                            await update.message.reply_text(tip + transaction.text)
                else:
                    if config.typing_effect:
                        await send_like_tying(update, context, transaction.text)
                    else:
                        await update.message.reply_text(transaction.text)

            message = transaction.text or "Sorry, I can't work with this audio messages 🙁"
        else:
            message = message or update.message.text
        gpt_obj = chatgpt.ChatGPT(use_chatgpt_api=config.use_chatgpt_api)
        answer, n_used_tokens, n_first_dialog_messages_removed = gpt_obj.send_message(
            message,
            dialog_messages=db.get_dialog_messages(user_id, dialog_id=None),
            chat_mode=db.get_user_attribute(user_id, "current_chat_mode"),
        )

        # update user data
        new_dialog_message = {"user": message, "assistant": answer,
                              "date": datetime.now().strftime("%Y-%m-%d %H:%M:%s")}
        db.set_dialog_messages(
            user_id,
            db.get_dialog_messages(user_id, dialog_id=None) + [new_dialog_message],
            dialog_id=None
        )

        db.set_user_attribute(user_id, "n_used_tokens", n_used_tokens + db.get_user_attribute(user_id, "n_used_tokens"))

    except Exception as e:
        error_text = f"Something went wrong during completion. Reason: {e}"
        logger.error(error_text)
        # if error reply all the message rapidly
        await update.message.reply_text(error_text)
        return
    finally:
        for ext in ['mp3', 'ogg']:
            if os.path.exists(file_name := f'{name}.{ext}'):
                os.remove(file_name)

    # send message if some messages were removed from the context
    if n_first_dialog_messages_removed > 0:
        if n_first_dialog_messages_removed == 1:
            text = "✍️ <i>Note:</i> Your current dialog is too long, so your <b>first message</b> was removed from the context.\n Send /new command to start new dialog"
        else:
            text = f"✍️ <i>Note:</i> Your current dialog is too long, so <b>{n_first_dialog_messages_removed} first messages</b> were removed from the context.\n Send /new command to start new dialog"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    try:
        answer = render_msg_with_code(answer)
        if config.typing_effect:
            await send_like_tying(update, context, answer)
        else:
            await update.message.reply_text(answer, parse_mode=ParseMode.HTML)
    except telegram.error.BadRequest:
        # answer has invalid characters, so we send it without parse_mode
        await update.message.reply_text(answer)


async def new_dialog_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    db.start_new_dialog(user_id)
    await update.message.reply_text("Starting new dialog ✅")

    chat_mode = db.get_user_attribute(user_id, "current_chat_mode")
    await update.message.reply_text(f"{chatgpt.CHAT_MODES[chat_mode]['welcome_message']}", parse_mode=ParseMode.HTML)


async def show_chat_modes_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    keyboard = []
    for chat_mode, chat_mode_dict in chatgpt.CHAT_MODES.items():
        keyboard.append([InlineKeyboardButton(chat_mode_dict["name"], callback_data=f"set_chat_mode|{chat_mode}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Select chat mode:", reply_markup=reply_markup)


async def set_chat_mode_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    user_id = update.callback_query.from_user.id

    query = update.callback_query
    await query.answer()

    chat_mode = query.data.split("|")[1]

    db.set_user_attribute(user_id, "current_chat_mode", chat_mode)
    db.start_new_dialog(user_id)

    await query.edit_message_text(
        f"<b>{chatgpt.CHAT_MODES[chat_mode]['name']}</b> chat mode is set",
        parse_mode=ParseMode.HTML
    )

    await query.edit_message_text(f"{chatgpt.CHAT_MODES[chat_mode]['welcome_message']}", parse_mode=ParseMode.HTML)


async def show_balance_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    n_used_tokens = db.get_user_attribute(user_id, "n_used_tokens")
    n_spent_dollars = n_used_tokens * (0.002 / 1000)

    text = f"You spent <b>{n_spent_dollars:.03f}$</b>\n"
    text += f"You used <b>{n_used_tokens}</b> tokens <i>(price: 0.02$ per 1000 tokens)</i>\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def edited_message_handle(update: Update, context: CallbackContext):
    text = "🥲 Unfortunately, message <b>editing</b> is not supported"
    await update.edited_message.reply_text(text, parse_mode=ParseMode.HTML)


async def error_handle(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    try:
        # collect error message
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)[:2000]
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            f"An exception was raised while handling an update\n"
            f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
            "</pre>\n\n"
            f"<pre>{html.escape(tb_string)}</pre>"
        )

        # split text into multiple messages due to 4096 character limit
        message_chunk_size = 4000
        message_chunks = [message[i:i + message_chunk_size] for i in range(0, len(message), message_chunk_size)]
        for message_chunk in message_chunks:
            await context.bot.send_message(update.effective_chat.id, message_chunk, parse_mode=ParseMode.HTML)
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, "Some error in error handler")


async def reply_multi_voice(update: Update, context: CallbackContext, audio_file: str):
    with wave.open(audio_file, 'rb') as audio_file:
        # Get the audio file parameters
        sample_width = audio_file.getsampwidth()
        frame_rate = audio_file.getframerate()
        num_frames = audio_file.getnframes()

        # Calculate the audio duration
        audio_duration = float(num_frames) / float(frame_rate)

        # Split the audio into segments of maximum duration (in seconds)
        max_duration = 50.0  # Telegram maximum audio duration is 1 minute
        num_segments = int(math.ceil(audio_duration / max_duration))

        for i in range(num_segments):
            # Calculate the start and end frames of the segment
            start_frame = int(i * max_duration * frame_rate)
            end_frame = int(min((i + 1) * max_duration * frame_rate, num_frames))

            # Read the segment data from the audio file
            audio_file.setpos(start_frame)
            segment_data = audio_file.readframes(end_frame - start_frame)

            # Write the segment data to a temporary file
            segment_filename = 'audio_file_segment_{}.wav'.format(i)
            with wave.open(segment_filename, 'wb') as segment_file:
                segment_file.setparams(audio_file.getparams())
                segment_file.writeframes(segment_data)

            # Send the segment as a Telegram audio message
            with open(segment_filename, 'rb') as segment_file:
                await context.bot.send_voice(chat_id=update.effective_chat.id, voice=segment_file)

            # Delete the temporary file
            os.remove(segment_filename)
