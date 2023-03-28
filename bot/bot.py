import asyncio
import html
import json
import time
import traceback
from datetime import datetime
from pathlib import Path

import telegram
from pydub import AudioSegment
from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackContext

from . import chatgpt
from . import config
from .database import Database
from .helper import send_like_tying, speech_to_text, reply_voice, check_contain_code, render_msg_with_code, azure_ocr, \
    get_main_lang
from .log import logger

# setup

db = Database()

HELP_MESSAGE = """Commands:
⚪ /retry – Regenerate last bot answer
⚪ /new – Start new dialog
⚪ /mode – Select chat mode
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
    try:
        message = message or update.message.text
        message_id = update.message.message_id
        gpt_obj = chatgpt.ChatGPT(use_chatgpt_api=config.use_chatgpt_api)
        gen_answer = gpt_obj.send_message_stream(message,
                                                 dialog_messages=db.get_dialog_messages(user_id, dialog_id=None),
                                                 chat_mode=db.get_user_attribute(user_id, "current_chat_mode"), )

        prev_answer = ""
        i = -1
        async for gen_item in gen_answer:
            i += 1

            status = gen_item[0]
            if status == "not_finished":
                status, answer = gen_item
            elif status == "finished":
                status, answer, n_first_dialog_messages_removed = gen_item
            else:
                raise ValueError(f"Streaming status {status} is unknown")

            answer = answer[:4096]  # telegram message limit
            if i == 0:  # send first message (then it'll be edited if message streaming is enabled)
                try:
                    sent_message = await update.message.reply_text(answer, reply_to_message_id=message_id,
                                                                   parse_mode=ParseMode.HTML)
                except telegram.error.BadRequest as e:
                    if str(e).startswith("Message must be non-empty"):  # first answer chunk from openai was empty
                        i = -1  # try again to send first message
                        continue
                    else:
                        sent_message = await update.message.reply_text(answer, reply_to_message_id=message_id, )
            else:  # edit sent message
                # update only when 100 new symbols are ready
                if abs(len(answer) - len(prev_answer)) < 100 and status != "finished":
                    continue
                try:
                    await context.bot.edit_message_text(answer, chat_id=sent_message.chat_id,
                                                        message_id=sent_message.message_id, parse_mode=ParseMode.HTML)
                except telegram.error.BadRequest as e:
                    if str(e).startswith("Message is not modified"):
                        continue
                    else:
                        await context.bot.edit_message_text(answer, chat_id=sent_message.chat_id,
                                                            message_id=sent_message.message_id)

                await asyncio.sleep(0.01)  # wait a bit to avoid flooding

            prev_answer = answer
            # update user data
        new_dialog_message = {"user": message, "assistant": answer,
                              "date": datetime.now().strftime("%Y-%m-%d %H:%M:%s")}
        db.set_dialog_messages(
            user_id,
            db.get_dialog_messages(user_id, dialog_id=None) + [new_dialog_message],
            dialog_id=None
        )
    except Exception as e:
        error_text = f"Sth went wrong: {e}"
        logger.error(f" error stack: {traceback.format_exc()}")
        # if error reply all the message rapidly
        await update.message.reply_text(error_text)
        return

    # send message if some messages were removed from the context
    if n_first_dialog_messages_removed > 0:
        if n_first_dialog_messages_removed == 1:
            text = "✍️ <i>Note:</i> Your current dialog is too long, so your <b>first message</b> was removed from the context.\n Send /new command to start new dialog"
        else:
            text = f"✍️ <i>Note:</i> Your current dialog is too long, so <b>{n_first_dialog_messages_removed} first messages</b> were removed from the context.\n Send /new command to start new dialog"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def voice_message_handle(update: Update, context: CallbackContext):
    logger.info('voice message handler:')
    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    name = f"{update.message.chat_id}{int(time.time())}"
    logger.info(f'filename:{name}')
    try:
        # get voice message and use whisper api translate it to text
        if update.message.voice:
            new_file = await context.bot.get_file(update.message.voice.file_id)
            a_file = f"{name}.mp3"
            await new_file.download_to_drive(f'{name}.ogg')
            audio = AudioSegment.from_file(f'{name}.ogg')
            audio.export(a_file, format="wav")
            await update.message.chat.send_action(action='record_audio')
            recognized_text = speech_to_text(a_file) or ''
            # send the recognised text
            text = 'You said: ' + recognized_text
            if config.typing_effect:
                await send_like_tying(update, context, text)
            else:
                await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            gpt_obj = chatgpt.ChatGPT(use_chatgpt_api=config.use_chatgpt_api)
            answer, _ = gpt_obj.send_message(
                recognized_text, dialog_messages=db.get_dialog_messages(user_id, dialog_id=None),
                chat_mode=db.get_user_attribute(user_id, "current_chat_mode")
            )
            logger.info(f'chatgpt answered: {answer}')
            if check_contain_code(answer):
                answer = render_msg_with_code(answer)
                await update.message.reply_text(answer, parse_mode=ParseMode.HTML)
            else:
                if config.typing_effect:
                    await send_like_tying(update, context, answer)
                else:
                    await update.message.reply_text(answer, parse_mode=ParseMode.HTML)
                await reply_voice(update, context, answer)
            new_dialog_message = {"user": recognized_text, "assistant": answer,
                                  "date": datetime.now().strftime("%Y-%m-%d %H:%M:%s")}
            db.set_dialog_messages(
                user_id,
                db.get_dialog_messages(user_id, dialog_id=None) + [new_dialog_message],
                dialog_id=None
            )

    except Exception as e:
        error_text = f"Sth went wrong: {e}"
        logger.error(f" error stack: {traceback.format_exc()}")
        # if error reply all the message rapidly
        await update.message.reply_text(error_text)
    finally:
        for ext in ['mp3', 'ogg']:
            if Path(file_name := f'{name}.{ext}').exists():
                Path(file_name).unlink()


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


async def edited_message_handle(update: Update, context: CallbackContext):
    text = "🥲 Unfortunately, message <b>editing</b> is not supported"
    await update.edited_message.reply_text(text, parse_mode=ParseMode.HTML)


async def photo_handle(update: Update, context: CallbackContext):
    logger.info('picture message handler:')

    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    name = f"{update.message.chat_id}_{int(time.time())}.jpg"
    logger.info(f'filename:{name}')
    try:
        if update.message.photo:
            # give choice to ocr or ocr and translate to chinese or ocr and translate to english
            choice = []
            choice.append(InlineKeyboardButton("OCR", callback_data=f"ocr|{name}|None"))
            choice.append(InlineKeyboardButton("ZH", callback_data=f"ocr|{name}|zh"))
            choice.append(InlineKeyboardButton("EN", callback_data=f"ocr|{name}|en"))
            choice.append(InlineKeyboardButton("Summary", callback_data=f"summary|{name}|None"))
            choice.append(InlineKeyboardButton("Story", callback_data=f"story|{name}|None"))
            choice.append(InlineKeyboardButton("Joke", callback_data=f"joke|{name}|None"))
            await update.message.reply_text("What do you want to do with the picture?",
                                            reply_to_message_id=update.message.message_id,
                                            reply_markup=InlineKeyboardMarkup([choice]))

    except Exception as e:
        logger.error(f"photo handle: {traceback.format_exc()}")
        await update.message.reply_text(f"Sth went wrong: {e}")
        logger.error(f"photo handle error stack: {traceback.format_exc()}")


async def ocr_handle(update: Update, context: CallbackContext):
    """Handle ocr callback query"""
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    user_id = update.callback_query.from_user.id
    query = update.callback_query

    action_type, img_name, lang = query.data.split("|")
    file_id = query.message.reply_to_message.photo[-1].file_id
    img_file = await context.bot.get_file(file_id)
    await img_file.download_to_drive(custom_path := f'{img_name}')
    await query.message.chat.send_action(action="typing")
    text = await azure_ocr(img_name)
    logger.info(f'ocr text:{text}')
    if text:
        text_main_lang = get_main_lang(text)
        gpt_obj = chatgpt.ChatGPT(use_chatgpt_api=config.use_chatgpt_api)
        if action_type == 'summary':
            text = f"{text} Summary the main point of this text in {text_main_lang}."
        elif action_type == 'story':
            text = f"{text} Tell me a story according to the text in {text_main_lang}."
        elif action_type == 'joke':
            text = f"{text} Tell me a joke according to the text in {text_main_lang}."
        else:
            # ocr and translate
            if lang == 'None':
                # only ocr text
                if config.typing_effect:
                    await send_like_tying(update, context, text)
                else:
                    await query.message.reply_text(text, parse_mode=ParseMode.HTML)
                return
            else:
                lang = 'Chinese' if lang == 'zh' else 'English'
                text = f"{text} Translate to {lang}"
        answer, _ = gpt_obj.send_message(text, dialog_messages=[],
                                         chat_mode=db.get_user_attribute(user_id, "current_chat_mode")
                                         )
        await query.message.chat.send_action(action="typing")
        if config.typing_effect:
            await send_like_tying(update, context, answer)
        else:
            await query.message.reply_text(answer, parse_mode=ParseMode.HTML)
    else:
        await query.message.reply_text("No text found in the picture", parse_mode=ParseMode.HTML)


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
