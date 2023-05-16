import html
import html
import json
import math
import random
import re
import string
import time
import traceback
import wave
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pydub import AudioSegment
from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackContext

from . import chatgpt, palm
from . import config
from .database import Database
from .helper import send_like_tying, check_contain_code, render_msg_with_code, get_main_lang, AzureService, \
    num_tokens_from_string
from .log import logger

# setup

db = Database()

url_pattern = r'^http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
HELP_MESSAGE = """Commands:
⚪ /retry – Regenerate last bot answer
⚪ /new – Start new dialog
⚪ /mode – Select chat mode
⚪ /help – Show help
"""

azure_service = AzureService()
gpt_service = chatgpt.ChatGPT(model_name=config.openai_engine, use_stream=config.openai_response_streaming)
palm_service = palm.GooglePalm()


async def register_user_if_not_exists(update: Update, context: CallbackContext, user: User):
    if not db.check_if_user_exists(user.id):
        db.add_new_user(
            user.id,
            update.message.chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )


async def reply_voice(update, context, answer):
    """
     check if it's only single language if it's then reply with voice
    """
    audio_file = azure_service.text2speech(answer)
    if audio_file and Path(audio_file).exists():
        try:
            with wave.open(audio_file, 'rb') as f:
                # Get the audio file parameters
                sample_width = f.getsampwidth()
                frame_rate = f.getframerate()
                num_frames = f.getnframes()

                # Calculate the audio duration
                audio_duration = float(num_frames) / float(frame_rate)
                logger.info(f'audio duration: {audio_duration}')

                # Split the audio into segments of maximum duration (in seconds)
                max_duration = 59.0  # Telegram maximum audio duration is 1 minute
                num_segments = int(math.ceil(audio_duration / max_duration))
                logger.info(f'audio segments num: {num_segments}')
                for i in range(num_segments):
                    # Calculate the start and end frames of the segment
                    start_frame = int(i * max_duration * frame_rate)
                    end_frame = int(min((i + 1) * max_duration * frame_rate, num_frames))

                    # Read the segment data from the audio file
                    f.setpos(start_frame)
                    segment_data = f.readframes(end_frame - start_frame)

                    # Write the segment data to a temporary file
                    segment_filename = f'segment_{random.sample(string.ascii_letters + string.digits, 6)}.ogg'
                    with wave.open(segment_filename, 'wb') as segment_file:
                        segment_file.setparams(f.getparams())
                        segment_file.writeframes(segment_data)

                    # Send the segment as a Telegram audio message
                    with open(segment_filename, 'rb') as segment_file:
                        await context.bot.send_chat_action(chat_id=update.effective_chat.id,
                                                           action='record_audio')
                        await context.bot.send_voice(chat_id=update.effective_chat.id, voice=segment_file)

                    # Delete the temporary file
                    Path(segment_filename).unlink()
                    logger.info(f'reply multi voice done!')
        except Exception as e:
            logger.error(f'error in reply_multi_voice: {e}')
            logger.error(f"error stack: {traceback.format_exc()}")
        Path(audio_file).unlink()
    else:
        await update.message.reply_text("Text to speech failed")


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


async def balance_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    if not config.openai_session_key:
        await update.message.reply_text("You have not set session key, can't check balance 🤷‍♂️")
        return
    total_granted, total_used, total_available = await gpt_service.get_balance(config.openai_session_key)
    if total_available is not None:
        await update.message.reply_text(
            f'You have {total_granted} credits, used: {total_used}, available: {total_available}')
        return

    await update.message.reply_text(f'sth wrong with check balance, please check your session key 🤷‍♂️')


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
            await update.message.reply_text("Starting new dialog due to timeout ⌛️")
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    message = message or update.message.text

    # solve the url message
    if re.match(url_pattern, message):
        await update.message.reply_text("This is a url, I will try to get the text from it, what do you want to do?",
                                        reply_to_message_id=update.message.message_id,
                                        reply_markup=InlineKeyboardMarkup([
                                            [InlineKeyboardButton("summary", callback_data='url|summary'),
                                             InlineKeyboardButton("main point", callback_data='url|point')]
                                        ]), parse_mode=ParseMode.HTML
                                        )
        return
    # send typing action
    try:

        message_id = update.message.message_id
        await update.message.reply_text('Which AI do you want to use?',
                                        reply_to_message_id=update.message.message_id,
                                        reply_markup=InlineKeyboardMarkup([
                                            [InlineKeyboardButton("PaLM2", callback_data='model|PaLM2'),
                                             InlineKeyboardButton("ChatGpt", callback_data='model|ChatGpt'),
                                             ]
                                        ]), parse_mode=ParseMode.HTML
                                        )


    except Exception as e:
        error_text = f"Sth went wrong: {e}"
        logger.error(f" error stack: {traceback.format_exc()}")
        # if error reply all the message rapidly
        await update.message.reply_text(error_text)
        return

    # send message if some messages were removed from the context
    # if n_first_dialog_messages_removed > 0:
    #     if n_first_dialog_messages_removed == 1:
    #         text = "✍️ <i>Note:</i> Your current dialog is too long, so your <b>first message</b> was removed from the context.\n Send /new command to start new dialog"
    #     else:
    #         text = f"✍️ <i>Note:</i> Your current dialog is too long, so <b>{n_first_dialog_messages_removed} first messages</b> were removed from the context.\n Send /new command to start new dialog"
    #     await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def url_link_handle(update: Update, context: CallbackContext):
    """
    handle the url message
    """
    try:
        user_id = update.callback_query.from_user.id
        query = update.callback_query
        # action = query.data.split('|')[1]
        url = query.message.reply_to_message.text
        if not url:
            await context.bot.send_message(text=f"can't get text from this url", chat_id=query.message.chat_id)
        response = requests.get(url)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        text = re.sub(r'\s', '', text)
        if not text:
            await context.bot.send_message(text=f"can't get text from this url", chat_id=query.message.chat_id)
        if total_tokens := num_tokens_from_string(text)[0] > 10000:
            await context.bot.send_message(text=f'This message is more than 10000 tokens(Total:{total_tokens}), '
                                                f'watch your credit', chat_id=query.message.chat_id)

        tip_message = await context.bot.send_message(text="I'm working on it, please wait...",
                                                     chat_id=query.message.chat_id,
                                                     parse_mode=ParseMode.HTML)
        answer = await gpt_service.long_text_summary(text)
        await tip_message.delete()
        if answer:
            await context.bot.send_message(text=answer, chat_id=query.message.chat_id, parse_mode=ParseMode.HTML)
            new_dialog_message = {"user": text, "assistant": answer,
                                  "date": datetime.now().strftime("%Y-%m-%d %H:%M:%s")}
            db.set_dialog_messages(
                user_id,
                db.get_dialog_messages(user_id, dialog_id=None) + [new_dialog_message],
                dialog_id=None
            )
    except Exception as e:
        logger.error(f'sth wrong with :{e}')
        logger.error(f"traceback {traceback.format_exc()}")
        await context.bot.send_message(text='sth wrong while solving the html', chat_id=query.message.chat_id,
                                       parse_mode=ParseMode.HTML)


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
            recognized_text = azure_service.speech2text(a_file) or ''
            # send the recognised text
            text = 'You said: ' + recognized_text
            if config.telegram_typing_effect:
                await send_like_tying(update, context, text)
            else:
                await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            answer, _ = gpt_service.send_message(
                recognized_text, dialog_messages=db.get_dialog_messages(user_id, dialog_id=None),
                chat_mode=db.get_user_attribute(user_id, "current_chat_mode")
            )
            logger.info(f'chatgpt answered: {answer}')
            if check_contain_code(answer):
                answer = render_msg_with_code(answer)
                await update.message.reply_text(answer, parse_mode=ParseMode.HTML)
            else:
                if config.telegram_typing_effect:
                    await send_like_tying(update, context, answer)
                else:
                    await update.message.reply_text(answer, parse_mode=ParseMode.HTML)
                # check if a text_to_speech key is provided
                if config.azure_text2speech_key:
                    await reply_voice(update, context, answer)
                else:
                    await update.message.reply_text('No azure text to speech key provided, No voice answer.',
                                                    parse_mode=ParseMode.HTML)
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
            choice = [InlineKeyboardButton("OCR", callback_data=f"ocr|{name}|None"),
                      InlineKeyboardButton("ZH", callback_data=f"ocr|{name}|zh"),
                      InlineKeyboardButton("EN", callback_data=f"ocr|{name}|en"),
                      InlineKeyboardButton("Summary", callback_data=f"ocr|{name}|summary"),
                      InlineKeyboardButton("Story", callback_data=f"ocr|{name}|story"),
                      InlineKeyboardButton("Joke", callback_data=f"ocr|{name}|joke")]
            await update.message.reply_text("What do you want to do with the picture?",
                                            reply_to_message_id=update.message.message_id,
                                            reply_markup=InlineKeyboardMarkup([choice]))

    except Exception as e:
        logger.error(f"photo handle: {traceback.format_exc()}")
        await update.message.reply_text(f"Sth went wrong: {e}")
        logger.error(f"photo handle error stack: {traceback.format_exc()}")



async def ocr_handle(update: Update, context: CallbackContext):
    """Handle ocr callback query"""
    user_id = update.callback_query.from_user.id
    query = update.callback_query
    tip_message = await context.bot.send_message(
        text="I'm working on it, please wait...", chat_id=query.message.chat_id,
        parse_mode=ParseMode.HTML)
    _, img_name, action_type = query.data.split("|")
    file_id = query.message.reply_to_message.photo[-1].file_id
    img_file = await context.bot.get_file(file_id)
    await img_file.download_to_drive(img_name)
    text = await azure_service.ocr(img_name)
    logger.info(f'ocr text:{text}')
    if text:
        await query.message.chat.send_action(action="typing")
        text_main_lang = get_main_lang(text)
        if action_type == 'None':  # only ocr
            if config.telegram_typing_effect:
                await send_like_tying(update, context, text)
            else:
                await query.message.reply_text(text, parse_mode=ParseMode.HTML)
            await tip_message.delete()
            return
        elif action_type == 'zh' or action_type == 'en':  # need translate
            lang = 'Chinese' if action_type == 'zh' else 'English'
            text = f"{text} Translate to {lang}"
        elif action_type == 'summary':
            text = f"{text} Summary the main point of this text in {text_main_lang}."
        elif action_type == 'story':
            text = f"{text} Tell me a story according to the text in {text_main_lang}."
        elif action_type == 'joke':
            text = f"{text} Tell me a joke according to the text in {text_main_lang}."

        answer, _ = gpt_service.send_message(text, dialog_messages=[],
                                             chat_mode=db.get_user_attribute(user_id, "current_chat_mode")
                                             )
        await tip_message.delete()
        if config.telegram_typing_effect:
            await send_like_tying(update, context, answer)
        else:
            await query.message.reply_text(answer, parse_mode=ParseMode.HTML)
    else:
        await query.message.reply_text("No text found in the picture", parse_mode=ParseMode.HTML)


async def palm_handle(update, context):
    query = update.callback_query
    message = query.message.reply_to_message.text
    tip_message = await context.bot.send_message(text="I'm working on it, please wait...",
                                                 chat_id=query.message.chat_id,
                                                 parse_mode=ParseMode.HTML)
    answer, tr_message= await palm_service.send_message(message, dialog_messages=None)
    message_id = query.message.reply_to_message.message_id
    await tip_message.delete()
    await context.bot.send_message(text=f"🗣:\n\n{tr_message}\n\n<pre>{answer}</pre>",
                                   chat_id=query.message.chat_id,
                                   reply_to_message_id=message_id, parse_mode=ParseMode.HTML)


async def chatgpt_handle(update, context):
    user_id = update.callback_query.from_user.id
    query = update.callback_query
    message = query.message.reply_to_message.text
    tip_message = await context.bot.send_message(text="I'm working on it, please wait...",
                                                 chat_id=query.message.chat_id,
                                                 parse_mode=ParseMode.HTML)
    answer, _ = gpt_service.send_message(message, dialog_messages=db.get_dialog_messages(user_id, dialog_id=None),
                                         chat_mode=db.get_user_attribute(user_id, "current_chat_mode"), )
    message_id = query.message.reply_to_message.message_id
    await tip_message.delete()
    await context.bot.send_message(text=f"🗣\n\n<pre>{answer}</pre>", chat_id=query.message.chat_id,
                                   reply_to_message_id=message_id, parse_mode=ParseMode.HTML)
    new_dialog_message = {"user": message, "assistant": answer,
                          "date": datetime.now().strftime("%Y-%m-%d %H:%M:%s")}
    db.set_dialog_messages(
        user_id,
        db.get_dialog_messages(user_id, dialog_id=None) + [new_dialog_message],
        dialog_id=None
    )


async def dispatch_callback_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    if query.data.startswith("model"):
        _, model = query.data.split('|')
        if model == 'ChatGpt':
            await chatgpt_handle(update, context)
        elif model == 'PaLM2':
            await palm_handle(update, context)
    elif query.data.startswith("ocr"):
        await ocr_handle(update, context)
    elif query.data.startswith('url'):
        await url_link_handle(update, context)
    elif query.data.startswith('prompt'):
        await prompt_handle(update, context)


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


async def list_prompt_handle(update: Update, context: CallbackContext) -> None:
    """ list the prompt already exist"""
    prompts = db.get_prompts()
    if len(prompts) == 0:
        await update.message.reply_text("No prompt yet, please add one first.")
        return
    text = "Here are the prompts:\n"

    btns = InlineKeyboardMarkup([[InlineKeyboardButton(
        f"{prompt.id} {prompt.short_desc}", callback_data=f'prompt|{prompt.id}')] for prompt in prompts])
    await update.message.reply_text(text, reply_to_message_id=update.message.message_id,
                                    reply_markup=btns, parse_mode=ParseMode.HTML)


async def new_prompt_handle(update: Update, context: CallbackContext):
    """add a new prompt"""
    try:
        _, data = update.message.text.split(" ", 1)
        short_desc, prompt = data.split('|')
        db.add_new_prompt(short_desc, prompt)
        await update.message.reply_text(f"Prompt ({short_desc}) added successfully.")
    except ValueError as ve:
        logger.error(ve)
        await update.message.reply_text("Prompt format error, please try again.")


async def del_prompt_handle(update: Update, context: CallbackContext):
    """delete a prompt"""
    try:
        prompt_id = update.message.text.split(" ")[1]
        db.del_prompt(prompt_id)
        await update.message.reply_text(f"Prompt ({prompt_id}) deleted successfully.")
    except ValueError as ve:
        logger.error(ve)
        await update.message.reply_text("Prompt format error, please try again.")


async def prompt_handle(update: Update, context: CallbackContext):
    """handle prompt callback query"""
    query = update.callback_query
    prompt_id = query.data.split("|")[1]
    prompt = db.get_prompt(int(prompt_id))
    if prompt:
        tip_message = await query.message.reply_text("I'm thinking...")
        answer, _ = gpt_service.send_message(prompt.description, dialog_messages=[], chat_mode='assistant')
        if not answer:
            await query.message.reply_text("I have no idea about this.")
            return
        elif config.telegram_typing_effect:
            await send_like_tying(update, context, answer)
        else:
            await query.message.reply_text(answer, parse_mode=ParseMode.HTML)
        await tip_message.delete()
    else:
        await query.message.reply_text("Prompt not found.")


async def export_handle(update: Update, context: CallbackContext):
    """
     export latest dialog as default
    """
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    dialog_id = None
    if ' ' in update.message.text:
        _, dialog_id = update.message.text.split(" ", 1)
        dialog_id = dialog_id.strip()
        if '-' in dialog_id:
            dialog_id = dialog_id.split('-')[1]
            if dialog_id.isdigit():
                dialog_id = -int(dialog_id)
        elif dialog_id.isdigit():
            dialog_id = int(dialog_id)
        else:
            await update.message.reply_text("Invalid dialog id.")

    dialog_id = db.get_real_dialog_id(str(user_id), dialog_id)
    messages = db.get_dialog_messages(str(user_id), dialog_id)
    if messages:
        with open('messages.txt', 'w') as f:
            for msg in messages:
                f.write(f"User: {msg['user']}\n")
                f.write(f"GPT: {msg['assistant']}\n")
        if Path('messages.txt').exists():
            await context.bot.sendDocument(chat_id=update.effective_chat.id, document=open('messages.txt', 'rb'))
            Path('messages.txt').unlink()
    else:
        await update.message.reply_text("No message to export.")
