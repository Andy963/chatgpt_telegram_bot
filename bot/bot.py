import asyncio
import html
import json
import math
import random
import re
import string
import time
import traceback
import wave
from asyncio import Condition
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pydub import AudioSegment
from telegram import Update, User, InlineKeyboardButton, InlineKeyboardMarkup, \
    Message
from telegram.constants import ParseMode
from telegram.error import BadRequest, RetryAfter
from telegram.ext import CallbackContext, Application

from config import config
from database.models import Permission
from logs.log import logger
from . import (
    user_db,
    azure_service,
    dialog_db,
    gpt_service,
    ai_model_db,
    prompt_db,
    palm_service,
    azure_openai_service,
    anthropic_service,
    role_db, cloudflare_service,
)
from .helper import (
    check_contain_code,
    render_msg_with_code,
    get_main_lang,
    num_tokens_from_string,
)

command_list = [
    ("start", "Starts the bot"),
    ("help", "Shows this help message"),
    ("retry", "Retry the last message"),
    ("new", "Start a new dialog"),
    ("mode", "Show current chat mode"),
    ("prompt", "List all prompts"),
    ("model", "List all models"),
    ("user", "List all users"),
    ("export", "Export all dialogs"),
    ("stream", "Streaming response")
]

HELP_MESSAGE = "\n".join(
    [f"/{command} - {description}" for command, description in command_list]
)


async def init_menu(app: Application) -> None:
    """init menu commands"""
    await app.bot.set_my_commands(command_list)


async def register_user_if_not_exists(
        update: Update, context: CallbackContext, user: User
):
    if not user_db.check_if_user_exists(user.id):
        role_id = role_db.get_default_role().id
        user_db.add_new_user(
            user.id,
            update.message.chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            role_id=role_id,
        )


async def reply_voice(update, context, answer):
    """
    check if it's only single language if it's then reply with voice
    """
    audio_file = azure_service.text2speech(answer)
    if audio_file and Path(audio_file).exists():
        try:
            with wave.open(audio_file, "rb") as f:
                # Get the audio file parameters
                frame_rate = f.getframerate()
                num_frames = f.getnframes()

                # Calculate the audio duration
                audio_duration = float(num_frames) / float(frame_rate)
                logger.info(f"audio duration: {audio_duration}")

                # Split the audio into segments of maximum duration (in seconds)
                # Telegram maximum audio duration is 1 minute
                max_duration = 59.0
                num_segments = int(math.ceil(audio_duration / max_duration))
                logger.info(f"audio segments num: {num_segments}")
                for i in range(num_segments):
                    # Calculate the start and end frames of the segment
                    start_frame = int(i * max_duration * frame_rate)
                    end_frame = int(
                        min((i + 1) * max_duration * frame_rate, num_frames)
                    )

                    # Read the segment data from the audio file
                    f.setpos(start_frame)
                    segment_data = f.readframes(end_frame - start_frame)

                    # Write the segment data to a temporary file
                    random_str = random.sample(
                        string.ascii_letters + string.digits, 6)
                    segment_filename = f"segment_{random_str}.ogg"
                    with wave.open(segment_filename, "wb") as segment_file:
                        segment_file.setparams(f.getparams())
                        segment_file.writeframes(segment_data)

                    # Send the segment as a Telegram audio message
                    with open(segment_filename, "rb") as segment_file:
                        await context.bot.send_chat_action(
                            chat_id=update.effective_chat.id,
                            action="record_audio"
                        )
                        await context.bot.send_voice(
                            chat_id=update.effective_chat.id, voice=segment_file
                        )

                    # Delete the temporary file
                    Path(segment_filename).unlink()
                    logger.info(f"reply multi voice done!")
        except Exception as e:
            logger.error(f"error in reply_multi_voice: {e}")
            logger.error(f"error stack: {traceback.format_exc()}")
        Path(audio_file).unlink()
    else:
        await update.message.reply_text("Text to speech failed")


async def start_handle(update: Update, context: CallbackContext):
    user = update.message.from_user
    await register_user_if_not_exists(update, context, user)
    logger.info(f"user_id: {user.id} start chat")

    user_db.set_user_attribute(user.id, "last_interaction", datetime.now())
    dialog_db.start_new_dialog(user.id)

    reply_text = "Hi! I'm An AI bot implemented with GPT API 🤖\n\n"
    reply_text += HELP_MESSAGE
    reply_text += "\nAnd now... ask me anything!"

    await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)


async def help_handle(update: Update, context: CallbackContext):
    user = update.message.from_user
    await register_user_if_not_exists(update, context, user)
    user_db.set_user_attribute(user.id, "last_interaction", datetime.now())
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML)


async def retry_handle(update: Update, context: CallbackContext):
    user = update.message.from_user
    await register_user_if_not_exists(update, context, user)
    ai_model_name = ai_model_db.get_default_model().name
    dialog_messages = dialog_db.get_dialog_messages(user.id, dialog_id=None,
                                                    ai_model=ai_model_name)
    if len(dialog_messages) == 0:
        await update.message.reply_text("No message to retry 🤷‍♂️")
        return

    last_dialog_message = dialog_messages.pop()
    # last message was removed from the context
    dialog_db.set_dialog_messages(user.id, dialog_messages,
                                  ai_model=ai_model_name)

    await message_handle(
        update,
        context,
        message=last_dialog_message["user"],
        use_new_dialog_timeout=False,
    )


async def stream_message_handle(update: Update, context: CallbackContext,
                                message=None,
                                user_new_dialog_timeout=True):
    user = update.message.from_user
    await register_user_if_not_exists(update, context, user)
    user_obj = user_db.get_user_by_user_id(user.id)
    chat_mode = user_obj.current_chat_mode
    prompt = config.chat_mode[chat_mode].get("prompt_start")
    default_model = ai_model_db.get_default_model()
    context_msg = dialog_db.get_dialog_messages(
        user.id, dialog_id=None, ai_model=default_model.name
    )
    message = update.message.text
    stream = await anthropic_service.send_message_stream(message, context_msg,
                                                         prompt)
    index = 0
    answer = ''
    prev_answer = ''
    answer_msg = update.message
    message_id = update.message.message_id
    text = ''
    threshold = 10  # 每次编辑消息最少要5个字的变化
    async for a in stream:
        text = a.completion
        answer = f"{answer}{text}"
        if len(answer) < 1:
            break
        if index == 0:
            answer_msg = await context.bot.send_message(
                text=f"🗣\n\n{answer}",
                chat_id=update.message.chat_id,
                reply_to_message_id=message_id,
                parse_mode=ParseMode.HTML,
                disable_notification=True,
            )
        else:
            if answer == prev_answer:
                break
            if len(answer) < threshold + len(prev_answer):
                continue
            prev_answer = answer
            try:
                answer_msg = await context.bot.edit_message_text(
                    answer, answer_msg.chat_id, answer_msg.message_id)
            except (BadRequest,RetryAfter):
                await asyncio.sleep(0.1)

        index = index + 1
    else:
        # 循环结束后检查是否有未发送的文本
        if 0 < len(text) <= threshold:
            answer = f"{answer}{text}"
        try:
            await context.bot.edit_message_text(
                answer, answer_msg.chat_id, answer_msg.message_id)
        except BadRequest:
            await asyncio.sleep(0.1)
    new_dialog_message = {
        "user": message,
        "assistant": answer,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%s"),
    }
    user_db.set_user_attribute(user.id, "last_interaction", datetime.now())
    dialog_db.set_dialog_messages(
        user.id,
        dialog_db.get_dialog_messages(user.id, ai_model=default_model.name)
        + [new_dialog_message],
        ai_model=default_model.name,
    )
    user_db.consume_api_count(user.id)


async def message_handle(
        update: Update, context: CallbackContext, message=None,
        use_new_dialog_timeout=True
):
    user = update.message.from_user
    await register_user_if_not_exists(update, context, user)
    user_obj = user_db.get_user_by_user_id(user.id)
    default_model = ai_model_db.get_default_model()
    # use stream by message_stream_handle (only for claude model)
    if user_obj and user_obj.use_stream and default_model.name.lower() == 'claude':
        await stream_message_handle(update, context, message)
        return
    # check if message is edited
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    if not user_obj or not user_obj.has_api_count():
        await update.message.reply_text(
            "You have no API count left, please contact the admin to get more 🤷‍♂️"
        )
        return

    # new dialog timeout
    if use_new_dialog_timeout:
        last_time = user_db.get_user_attribute(user.id, "last_interaction")
        if (datetime.now() - last_time).seconds > config.new_dialog_timeout:
            dialog_db.start_new_dialog(user_id=str(user.id))
            await update.message.reply_text(
                "Starting new dialog due to timeout ⌛️")
    answer = None
    condition = asyncio.Condition()

    async def keep_editing(
            condition: Condition, context: CallbackContext, msg: Message,
            text: str
    ):
        """keep editing the tip message until get answer from the ai"""
        if msg is not None and not condition.locked():
            text = text[:-1] + "." + text[-1]
            await context.bot.edit_message_text(text, msg.chat_id,
                                                msg.message_id)
            await asyncio.sleep(1)
            await keep_editing(condition, context, msg, text)

    try:

        if default_model is None:
            await update.message.reply_text("Please set default model first")
            return
        message = update.message.text
        tip_message = await context.bot.send_message(
            text="I'm working on it, please wait🤔",
            disable_notification=True,
            chat_id=update.message.chat_id,
            parse_mode=ParseMode.HTML,
        )
        context_msg = dialog_db.get_dialog_messages(
            user.id, dialog_id=None, ai_model=default_model.name
        )
        edit_task = asyncio.create_task(
            keep_editing(condition, context, tip_message, tip_message.text)
        )
        answer = await get_answer_from_ai(
            default_model.name,
            message,
            chat_mode=user_obj.current_chat_mode,
            context=context_msg,
        )
        message_id = update.message.message_id
        if not answer:
            await context.bot.send_message(
                text="AI returns Noting",
                chat_id=update.message.chat_id,
                reply_to_message_id=message_id,
                parse_mode=ParseMode.HTML,
                disable_notification=True,
            )
            return
        # stop the editing
        # cancel the task
        await condition.acquire()
        condition.notify()
        edit_task.cancel()
        condition.release()
        condition = None
        await tip_message.delete()

        if check_contain_code(answer):
            answer = render_msg_with_code(answer)
        answer_msg = await context.bot.send_message(
            text=f"🗣\n\n{answer}",
            chat_id=update.message.chat_id,
            reply_to_message_id=message_id,
            parse_mode=ParseMode.HTML,
            disable_notification=True,
        )
        user_db.set_user_attribute(user.id, "last_interaction", datetime.now())
        # if answer is not in chinese give translate options
        if azure_service.translate_service_available and not re.search(
                r"[\u4e00-\u9fff]+", answer
        ):
            translate_choice = [
                InlineKeyboardButton("请帮我翻译成中文󠁧󠁢󠁥󠁮󠁧󠁿",
                                     callback_data=f"translate|zh"),
                InlineKeyboardButton("🗣 Read Aloud", callback_data=f"Read|en"),
            ]
            await context.bot.send_message(
                text="🆘 英文太难？懒得看？",
                reply_markup=InlineKeyboardMarkup([translate_choice]),
                chat_id=update.message.chat_id,
                reply_to_message_id=answer_msg.message_id,
                parse_mode=ParseMode.HTML,
            )
        new_dialog_message = {
            "user": message,
            "assistant": answer,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%s"),
        }
        dialog_db.set_dialog_messages(
            user.id,
            dialog_db.get_dialog_messages(user.id, ai_model=default_model.name)
            + [new_dialog_message],
            ai_model=default_model.name,
        )

        user_db.consume_api_count(user.id)
    except BadRequest as e:
        # Can't parse entities: unsupported start tag "=" at byte offset 1267
        if "unsupported start tag" in str(e.message):
            logger.info(f"when exception occur the answer is:\n {answer}")
            index = int(re.findall(r"at byte offset (\d+)", e.message)[0])
            logger.error(f"Near error is : {answer[index - 10:index + 10]}")
    except Exception as e:
        error_text = f"Sth went wrong: {e}"
        logger.error(f" error stack: {traceback.format_exc()}")
        if answer is not None:
            logger.info(f"when exception occur the answer is:\n {answer}")
        # if error reply all the message rapidly
        await update.message.reply_text(error_text)
        return


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
            await context.bot.send_message(
                text=f"can't get text from this url",
                chat_id=query.message.chat_id
            )
        response = requests.get(url)
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text()
        text = re.sub(r"\s", "", text)
        if not text:
            await context.bot.send_message(
                text=f"can't get text from this url",
                chat_id=query.message.chat_id
            )
        if total_tokens := num_tokens_from_string(text)[0] > 10000:
            await context.bot.send_message(
                text=f"This message is more than 10000 tokens(Total:{total_tokens}), "
                     f"watch your credit",
                chat_id=query.message.chat_id,
            )

        tip_message = await context.bot.send_message(
            text="I'm working on it, please wait...",
            chat_id=query.message.chat_id,
            parse_mode=ParseMode.HTML,
        )
        answer = await gpt_service.long_text_summary(text)
        await tip_message.delete()
        if answer:
            await context.bot.send_message(
                text=answer, chat_id=query.message.chat_id,
                parse_mode=ParseMode.HTML
            )
            new_dialog_message = {
                "user": text,
                "assistant": answer,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%s"),
            }
            dialog_db.set_dialog_messages(
                user_id,
                dialog_db.get_dialog_messages(user_id, dialog_id=None)
                + [new_dialog_message],
            )
    except Exception as e:
        logger.error(f"sth wrong with :{e}")
        logger.error(f"traceback {traceback.format_exc()}")
        await context.bot.send_message(
            text="sth wrong while solving the html",
            chat_id=query.message.chat_id,
            parse_mode=ParseMode.HTML,
        )


async def get_answer_from_ai(ai_name: str, message: str, chat_mode: str,
                             context: list):
    """Get answer from ai model. no matter chatgpt or azure openai,
    or palm2 etc."""
    answer = None
    prompt = config.chat_mode[chat_mode].get("prompt_start")
    ai_name = ai_name.lower()
    if "chatgpt" in ai_name:
        answer = await gpt_service.send_message(message, context, prompt)
    elif "azure_openai" in ai_name:
        answer = await azure_openai_service.send_message(message, context,
                                                         prompt)
    elif "palm2" in ai_name:
        answer = await palm_service.send_message(message, context,
                                                 prompt=prompt)
    elif "claude" in ai_name:
        answer = await anthropic_service.send_message(message, context, prompt)
    elif 'cloudflare' in ai_name:
        answer = cloudflare_service.send_message(message, context, prompt)
    else:
        answer = "Ai model not found."
    return answer


async def voice_message_handle(update: Update, context: CallbackContext):
    logger.info("voice message handler:")
    await register_user_if_not_exists(update, context, update.message.from_user)
    default_model = ai_model_db.get_default_model()
    if default_model is None:
        await update.message.reply_text("Please set default model first")
        return
    if not azure_service.speech2text_service_available:
        await update.message.reply_text(
            "No azure speech to text service available,Can not handle voice message.",
            parse_mode=ParseMode.HTML,
        )
        return
    user_id = str(update.message.from_user.id)
    user_obj = user_db.get_user_by_user_id(user_id)
    name = f"{update.message.chat_id}{int(time.time())}"
    logger.info(f"filename:{name}")
    try:
        # get voice message and use whisper api translate it to text
        if update.message.voice:
            new_file = await context.bot.get_file(update.message.voice.file_id)
            a_file = f"{name}.mp3"
            await new_file.download_to_drive(f"{name}.ogg")
            audio = AudioSegment.from_file(f"{name}.ogg")
            audio.export(a_file, format="wav")
            await update.message.chat.send_action(action="record_audio")
            recognized_text = azure_service.speech2text(a_file) or ""
            # send the recognised text
            text = "You said: " + recognized_text
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            answer = await get_answer_from_ai(
                default_model.name,
                recognized_text,
                chat_mode=user_obj.current_chat_mode,
                context=dialog_db.get_dialog_messages(user_id, dialog_id=None),
            )
            user_db.set_user_attribute(user_id, "last_interaction",
                                       datetime.now())
            logger.info(f"chatgpt answered: {answer}")
            if check_contain_code(answer):
                answer = render_msg_with_code(answer)
                await update.message.reply_text(answer,
                                                parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(answer,
                                                parse_mode=ParseMode.HTML)
                # check if a text_to_speech key is provided
                if azure_service.text2speech_service_available:
                    await reply_voice(update, context, answer)
            new_dialog_message = {
                "user": recognized_text,
                "assistant": answer,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%s"),
            }
            dialog_db.set_dialog_messages(
                user_id,
                dialog_db.get_dialog_messages(user_id, dialog_id=None)
                + [new_dialog_message],
            )

    except Exception as e:
        error_text = f"Sth went wrong: {e}"
        logger.error(f" error stack: {traceback.format_exc()}")
        # if error reply all the message rapidly
        await update.message.reply_text(error_text)
    finally:
        for ext in ["mp3", "ogg"]:
            if Path(file_name := f"{name}.{ext}").exists():
                Path(file_name).unlink()


async def new_dialog_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = str(update.message.from_user.id)
    user_db.set_user_attribute(user_id, "last_interaction", datetime.now())

    dialog_db.start_new_dialog(user_id)
    await update.message.reply_text("Starting new dialog ✅")

    chat_mode = user_db.get_user_attribute(user_id, "current_chat_mode")
    await update.message.reply_text(
        f"{config.chat_mode[chat_mode]['welcome_message']}",
        parse_mode=ParseMode.HTML
    )


async def show_chat_modes_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = str(update.message.from_user.id)
    user_db.set_user_attribute(user_id, "last_interaction", datetime.now())

    keyboard = []
    for chat_mode, chat_mode_dict in config.chat_mode.items():
        keyboard.append(
            [
                InlineKeyboardButton(
                    chat_mode_dict["name"],
                    callback_data=f"set_chat_mode|{chat_mode}"
                )
            ]
        )
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Select chat mode:",
                                    reply_markup=reply_markup)


async def set_chat_mode_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context,
                                      update.callback_query.from_user)
    user_id = str(update.callback_query.from_user.id)

    query = update.callback_query
    await query.answer()

    chat_mode = query.data.split("|")[1]

    user_db.set_user_attribute(user_id, "current_chat_mode", chat_mode)
    dialog_db.start_new_dialog(user_id)

    await query.edit_message_text(
        f"<b>{config.chat_mode[chat_mode]['name']}</b> chat mode is set",
        parse_mode=ParseMode.HTML,
    )

    await query.edit_message_text(
        f"{config.chat_mode[chat_mode]['welcome_message']}",
        parse_mode=ParseMode.HTML
    )


async def edited_message_handle(update: Update, context: CallbackContext):
    text = "🥲 Unfortunately, message <b>editing</b> is not supported"
    await update.edited_message.reply_text(text, parse_mode=ParseMode.HTML)


async def photo_handle(update: Update, context: CallbackContext):
    logger.info("picture message handler:")
    await register_user_if_not_exists(update, context, update.message.from_user)

    name = f"{update.message.chat_id}_{int(time.time())}.jpg"
    logger.info(f"filename:{name}")
    try:
        # give choice to ocr or ocr and translate to chinese
        # or ocr and translate to english
        if update.message.photo:
            choice = [
                InlineKeyboardButton("OCR", callback_data=f"ocr|{name}|None"),
                InlineKeyboardButton("ZH", callback_data=f"ocr|{name}|zh"),
                InlineKeyboardButton("EN", callback_data=f"ocr|{name}|en"),
                InlineKeyboardButton("Summary",
                                     callback_data=f"ocr|{name}|summary"),
            ]
            await update.message.reply_text(
                "What do you want to do with the picture?",
                reply_to_message_id=update.message.message_id,
                reply_markup=InlineKeyboardMarkup([choice]),
            )

    except Exception as e:
        logger.error(f"photo handle: {traceback.format_exc()}")
        await update.message.reply_text(f"Sth went wrong: {e}")
        logger.error(f"photo handle error stack: {traceback.format_exc()}")


async def ocr_handle(update: Update, context: CallbackContext):
    """Handle ocr callback query"""
    query = update.callback_query
    if not azure_service.ocr_service_available:
        await query.message.reply_text("OCR service not available")
        return
    user_id = str(update.callback_query.from_user.id)
    tip_message = await context.bot.send_message(
        text="I'm working on it, please wait...",
        chat_id=query.message.chat_id,
        parse_mode=ParseMode.HTML,
    )
    _, img_name, action_type = query.data.split("|")
    file_id = query.message.reply_to_message.photo[-1].file_id
    img_file = await context.bot.get_file(file_id)
    await img_file.download_to_drive(img_name)
    text = await azure_service.ocr(img_name)
    logger.info(f"ocr text:{text}")
    if text:
        await query.message.chat.send_action(action="typing")
        text_main_lang = get_main_lang(text)
        if action_type == "None":  # only ocr
            await query.message.reply_text(text, parse_mode=ParseMode.HTML)
            await tip_message.delete()
            return
        elif action_type == "zh" or action_type == "en":  # need translate
            lang = "Chinese" if action_type == "zh" else "English"
            text = f"Translate the following text to {lang}:\n {text}"
        elif action_type == "summary":
            text = f"Summary the main point of the following text in {text_main_lang}:\n {text}"
        default_model = ai_model_db.get_default_model()
        if default_model is None:
            await update.message.reply_text("Please set default model first")
            return
        user_obj = user_db.get_user_by_user_id(user_id)
        answer = await get_answer_from_ai(
            ai_name=default_model.name,
            message=text,
            chat_mode=user_obj.current_chat_mode,
            context=[],
        )
        user_db.set_user_attribute(user_id, "last_interaction", datetime.now())
        await tip_message.delete()
        await query.message.reply_text(answer, parse_mode=ParseMode.HTML)
    else:
        await query.message.reply_text(
            "No text found in the picture", parse_mode=ParseMode.HTML
        )


async def read_handle(update, context):
    """将答案读出来，azure text2speech"""
    query = update.callback_query
    chat_id = query.message.chat_id
    message_id = query.message.reply_to_message.message_id
    if not azure_service.text2speech_service_available:
        await context.bot.send_message(
            text="⚠️ Please set azure text2speech key first",
            chat_id=chat_id,
            replay_to_message_id=message_id,
            parse_mode=ParseMode.HTML,
        )
        return
    message = query.message.reply_to_message.text
    await reply_voice(update, context, message)


async def translate_handle(update, context, lang):
    """对于需要翻译的消息，调用此函数使用azure 的翻译功能"""
    query = update.callback_query
    if not azure_service.translate_service_available:
        await context.bot.send_message(
            text="Translate service not available",
            chat_id=query.message.chat_id,
            replay_to_message_id=query.message.reply_to_message.message_id,
            parse_mode=ParseMode.HTML,
        )
        return
    target_lang = "zh-Hans" if lang == "zh" else "en-us"
    text = query.message.reply_to_message.text.replace("🗣:", "", 1)
    translated_text = azure_service.translate(text=text,
                                              target_lang=target_lang)
    await context.bot.send_message(
        text=f"{translated_text}",
        chat_id=query.message.chat_id,
        reply_to_message_id=query.message.reply_to_message.message_id,
        parse_mode=ParseMode.HTML,
    )


async def dispatch_callback_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context,
                                      update.callback_query.from_user)
    query = update.callback_query
    if query.data.startswith("translate"):
        _, lang = query.data.split("|")
        await translate_handle(update, context, lang)
    elif query.data.startswith("Read"):
        await read_handle(update, context)
    elif query.data.startswith("ocr"):
        await ocr_handle(update, context)
    elif query.data.startswith("url"):
        await url_link_handle(update, context)
    elif query.data.startswith("prompt"):
        await prompt_handle(update, context)
    elif query.data.startswith("setModel"):
        await set_default_ai_model_handle(update, context)
    elif query.data.startswith("toggleModel"):
        await toggle_ai_model_handle(update, context)
    elif query.data.startswith("set_chat_mode"):
        await set_chat_mode_handle(update, context)
    elif query.data.startswith("m_user"):
        await manage_user_handle(update, context)
    elif query.data.startswith("add_api_count"):
        await add_api_count_handle(update, context)
    elif query.data.startswith("admin_user"):
        await set_admin_handle(update, context)
    elif query.data.startswith('stream'):
        await set_stream_handle(update, context)


async def error_handle(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:",
                 exc_info=context.error)

    try:
        # collect error message
        tb_list = traceback.format_exception(
            None, context.error, context.error.__traceback__
        )
        tb_string = "".join(tb_list)[:2000]
        update_str = update.to_dict() if isinstance(update, Update) else str(
            update)
        message = (
            f"An exception was raised while handling an update\n"
            f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
            "</pre>\n\n"
            f"<pre>{html.escape(tb_string)}</pre>"
        )

        # split text into multiple messages due to 4096 character limit
        message_chunk_size = 4000
        message_chunks = [
            message[i: i + message_chunk_size]
            for i in range(0, len(message), message_chunk_size)
        ]
        for message_chunk in message_chunks:
            await context.bot.send_message(
                update.effective_chat.id, message_chunk,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        await context.bot.send_message(
            update.effective_chat.id, "Some error in error handler"
        )


async def list_user_handle(update: Update, context: CallbackContext):
    # for admin to manage user
    user = update.message.from_user
    await register_user_if_not_exists(update, context, user)
    user_obj = user_db.get_user_by_user_id(user.id)
    if not user_obj or not user_db.is_admin(user.id):
        await update.message.reply_text("You don't have permission to do this")
        return
    users = user_db.list_all_user()
    text = "List All Users \nHere are the available users:\n"
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{user.username if user.username else 'Nobody'}({user.user_id})",
                    callback_data=f"m_user|{user.user_id}",
                )
            ]
            for user in users
        ]
    )
    await update.message.reply_text(text, reply_markup=btns,
                                    parse_mode=ParseMode.HTML)


async def manage_user_handle(update: Update, context: CallbackContext):
    user = update.callback_query.from_user
    user_obj = user_db.get_user_by_user_id(user.id)
    if not user_obj or not user_db.is_admin(user.id):
        await update.message.reply_text("You don't have permission to do this")
        return
    _, user_id = update.callback_query.data.split("|")
    cur_user = user_db.get_user_by_user_id(user_id)
    is_admin = user_db.is_admin(user_id)
    text = f"{'👑' if is_admin else '👤'}{cur_user.username if cur_user.username else 'Nobody'} \
    id:{cur_user.user_id} (API COUNT:{cur_user.api_count}  TOTAL:{cur_user.total_api_count})"
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "ADD API 50",
                    callback_data=f"add_api_count|{cur_user.user_id}|{50}"
                ),
                InlineKeyboardButton(
                    "ADD API 100",
                    callback_data=f"add_api_count|{cur_user.user_id}|{100}",
                ),
                InlineKeyboardButton(
                    "ADD API 500",
                    callback_data=f"add_api_count|{cur_user.user_id}|{500}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "BLOCK CURRENT USER",
                    callback_data=f"add_api_count|{cur_user.user_id}|{0}",
                ),
                InlineKeyboardButton(
                    "SET AS ADMIN",
                    callback_data=f"admin_user|{cur_user.user_id}"
                ),
            ],
        ]
    )
    await context.bot.send_message(
        chat_id=update.callback_query.message.chat_id,
        text=text,
        reply_markup=btns,
        parse_mode=ParseMode.HTML,
    )


async def stream_handle(update: Update, context: CallbackContext):
    user = update.message.from_user
    await register_user_if_not_exists(update, context, user)
    user_obj = user_db.get_user_by_user_id(user.id)
    if user_obj:
        btns = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"enable stream {'✔️' if user_obj.use_stream else '✓'}",
                        callback_data=f"stream|{user_obj.user_id}|1"
                    ),
                    InlineKeyboardButton(
                        "disable stream",
                        callback_data=f"stream|{user_obj.user_id}|0",
                    )
                ]])
        text = f"current stream response is: <b>{'enabled' if user_obj.use_stream else 'disabled'}</b>"
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=text,
            reply_markup=btns,
            parse_mode=ParseMode.HTML
        )


async def set_stream_handle(update: Update, context: CallbackContext):
    user = update.callback_query.from_user
    user_obj = user_db.get_user_by_user_id(user.id)
    _, user_id, flag = update.callback_query.data.split("|")
    flag_enabled = True if flag == '1' else False
    if user_obj and user_id and user_obj.user_id != user_id:
        await update.message.reply_text("You don't have permission to do this")
        return
    if user_obj.use_stream == flag_enabled:
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=f"current stream response is <b>{'enabled' if user_obj.use_stream else 'disabled>'}</b> no need to change!",
            parse_mode=ParseMode.HTML
        )
    else:
        user_db.set_user_attribute(user_id, "use_stream", flag_enabled)
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=f"stream response has been <b>{'enabled' if flag_enabled else 'disabled'}</b> successfully!",
            parse_mode=ParseMode.HTML
        )


async def add_api_count_handle(update: Update, context: CallbackContext):
    user = update.callback_query.from_user
    user_obj = user_db.get_user_by_user_id(user.id)
    if not user_obj or not user_db.is_admin(user.id):
        await update.message.reply_text("You don't have permission to do this")
        return
    _, user_id, count = update.callback_query.data.split("|")
    if count == "0":
        user_db.set_user_attribute(user_id, "api_count", int(count))
    else:
        user_db.add_user_api_count(user_id, int(count))
    await context.bot.send_message(
        chat_id=update.callback_query.message.chat_id,
        text=f"Add {count} to {user_id} successfully.Current api count:\
        {user_db.get_user_by_user_id(user_id).api_count}",
    )


async def set_admin_handle(update: Update, context: CallbackContext):
    user = update.callback_query.from_user
    user_obj = user_db.get_user_by_user_id(user.id)
    if not user_obj or not user_db.is_admin(user.id):
        await update.message.reply_text("You don't have permission to do this")
        return
    _, user_id = update.callback_query.data.split("|")
    role_id = role_db.get_role_by_name("admin").role_id
    if not user_db.is_admin(user_id):
        user_db.set_user_attribute(user_id, "role_id", role_id)
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=f"Set {user_id} as admin successfully.",
        )


async def list_ai_model_handle(update: Update, context: CallbackContext):
    """list the ai model"""
    user = update.message.from_user
    await register_user_if_not_exists(update, context, user)
    user_obj = user_db.get_user_by_user_id(user.id)
    if not user_obj or not user_obj.has_permission(Permission.ADMIN):
        await update.message.reply_text("You don't have permission to do this")
        return

    models = ai_model_db.list_all_model()
    if len(models) == 0:
        await update.message.reply_text("No models yet, please add one first.")
        return
    text = "List All AI models \nHere are the available models (Click to change default model):\n"

    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{md.name} {'(default)' if md.is_default else ''}",
                    callback_data=f"setModel|{md.name}",
                ),
                InlineKeyboardButton(
                    "DISABLE" if md.is_available else "ENABLE",
                    callback_data=f"toggleModel|{md.name}|{md.is_available}",
                ),
            ]
            for md in models
        ]
    )
    await update.message.reply_text(
        text,
        reply_to_message_id=update.message.message_id,
        reply_markup=btns,
        parse_mode=ParseMode.HTML,
    )


async def toggle_ai_model_handle(update: Update, context: CallbackContext):
    """toggle ai model available"""
    user = update.callback_query.from_user
    await register_user_if_not_exists(update, context, user)
    user_obj = user_db.get_user_by_user_id(user.id)
    if not user_obj or not user_obj.has_permission(Permission.ADMIN):
        await update.message.reply_text("You don't have permission to do this")
        return
    ai_name, is_available = update.callback_query.data.split("|")[1:]
    if is_available == "True":
        # disable
        ai_model_db.update_model(ai_name, is_available=False)
        await context.bot.send_message(
            update.callback_query.message.chat_id,
            f"Disable <b>{ai_name}</b> success.",
            parse_mode=ParseMode.HTML,
        )
    else:
        ai_model_db.update_model(ai_name, is_available=True)
        await context.bot.send_message(
            update.callback_query.message.chat_id,
            f"Enable <b>{ai_name}</b> success.",
            parse_mode=ParseMode.HTML,
        )


async def set_default_ai_model_handle(update: Update, context: CallbackContext):
    """set the default ai model"""
    await register_user_if_not_exists(update, context,
                                      update.callback_query.from_user)
    # remove the default flag from the old default model
    df_model = ai_model_db.get_default_model()
    if df_model:
        ai_model_db.update_model(df_model.name, is_default=False)
    ai_name = update.callback_query.data.split("|")[1]
    ai_model_db.update_model(ai_name, is_default=True)

    await context.bot.send_message(
        update.callback_query.message.chat_id,
        f"Set <b>{ai_name}</b> as default model success.",
        parse_mode=ParseMode.HTML,
    )


async def list_prompt_handle(update: Update, context: CallbackContext) -> None:
    """list the prompt already exist"""
    prompts = prompt_db.get_prompts()
    if len(prompts) == 0:
        await update.message.reply_text("No prompt yet, please add one first.")
        return
    text = "Here are the prompts:\n"

    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{prompt.id} {prompt.short_desc}",
                    callback_data=f"prompt|{prompt.id}",
                )
            ]
            for prompt in prompts
        ]
    )
    await update.message.reply_text(
        text,
        reply_to_message_id=update.message.message_id,
        reply_markup=btns,
        parse_mode=ParseMode.HTML,
    )


async def new_prompt_handle(update: Update, context: CallbackContext):
    """add a new prompt"""
    try:
        _, data = update.message.text.split(" ", 1)
        short_desc, prompt = data.split("|")
        prompt_db.add_new_prompt(short_desc, prompt)
        await update.message.reply_text(
            f"Prompt ({short_desc}) added successfully.")
    except ValueError as ve:
        logger.error(ve)
        await update.message.reply_text(
            "Prompt format error, please try again.")


async def del_prompt_handle(update: Update, context: CallbackContext):
    """delete a prompt"""
    try:
        prompt_id = update.message.text.split(" ")[1]
        prompt_db.del_prompt(prompt_id)
        await update.message.reply_text(
            f"Prompt ({prompt_id}) deleted successfully.")
    except ValueError as ve:
        logger.error(ve)
        await update.message.reply_text(
            "Prompt format error, please try again.")


async def prompt_handle(update: Update, context: CallbackContext):
    """handle prompt callback query"""
    query = update.callback_query
    prompt_id = query.data.split("|")[1]
    prompt = prompt_db.get_prompt(int(prompt_id))
    if prompt:
        tip_message = await query.message.reply_text("I'm thinking...")
        answer, _ = gpt_service.send_message(
            prompt.description, dialog_messages=[], chat_mode="assistant"
        )
        if not answer:
            await query.message.reply_text("I have no idea about this.")
            return
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
    user_db.set_user_attribute(user_id, "last_interaction", datetime.now())
    dialog_id = None
    if " " in update.message.text:
        _, dialog_id = update.message.text.split(" ", 1)
        dialog_id = dialog_id.strip()
        if "-" in dialog_id:
            dialog_id = dialog_id.split("-")[1]
            if dialog_id.isdigit():
                dialog_id = -int(dialog_id)
        elif dialog_id.isdigit():
            dialog_id = int(dialog_id)
        else:
            await update.message.reply_text("Invalid dialog id.")

    dialog_id = dialog_db.get_real_dialog_id(str(user_id), dialog_id)
    messages = dialog_db.get_dialog_messages(str(user_id), dialog_id)
    if messages:
        with open("messages.txt", "w") as f:
            for msg in messages:
                f.write(f"User: {msg['user']}\n")
                f.write(f"GPT: {msg['assistant']}\n")
        if Path("messages.txt").exists():
            await context.bot.sendDocument(
                chat_id=update.effective_chat.id,
                document=open("messages.txt", "rb")
            )
            Path("messages.txt").unlink()
    else:
        await update.message.reply_text("No message to export.")
