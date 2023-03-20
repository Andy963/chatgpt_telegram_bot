#!/usr/bin/python
# coding:utf-8
import asyncio
import random
import re
from datetime import datetime

import azure.cognitiveservices.speech as speechsdk
from telegram.constants import ParseMode


def render_msg_with_code(msg):
    """给bot渲染返回的消息
    <b>text</b>：加粗文本
    <i>text</i>：斜体文本
    <u>text</u>：下划线文本
    <s>text</s>：删除线文本
    <a href="URL">text</a>：超链接文本
    <code>text</code>：等宽文本
    <pre>text</pre>：预格式化文本
    message = '''
    <pre>
    <code>
    def greet(name):
        print(f"Hello, {name}!")

    greet("World")
    </code>
    </pre>
    '''
    """
    if '`' not in msg:
        return msg
    import re
    p2 = re.compile(r'```.*?```', re.S)
    r2 = re.findall(p2, msg)
    for r in r2:
        lang = r.split('\n')[0].split('```')[1]
        msg = re.sub(f'```{lang}(.*?)```', rf'<pre><code>\1</code></pre>', msg, flags=re.S)
    return msg


async def send_like_tying(update, context, text):
    """
    send msg like typing
    :param update: bot update object
    :param context: bot context
    :param text:  msg text to send
    """
    msg = await context.bot.send_message(chat_id=update.effective_chat.id, text='God:  ', parse_mode=ParseMode.HTML)
    code_index = [(m.start(), m.end()) for m in re.finditer(r'<pre><code>(.+?)</code></pre>', text, re.S)]
    i = 0
    length = len(text)
    while i < length:
        num_chars = random.randint(1, 20) if length < 50 else random.randint(1, 50)

        if not code_index:
            current_text = text[:i + num_chars]
            full_text = msg.text + current_text
            await context.bot.edit_message_text(chat_id=msg.chat_id, message_id=msg.message_id, text=full_text,
                                                parse_mode=ParseMode.HTML)
            i += num_chars
        else:
            start, end = code_index[0]
            # expand to end of code block
            if i + num_chars > start:
                full_text = msg.text + text[:end + 1]
                await context.bot.edit_message_text(chat_id=msg.chat_id, message_id=msg.message_id, text=full_text,
                                                    parse_mode=ParseMode.HTML)
                i = end + 1
                code_index.pop(0)
            else:
                current_text = text[:i + num_chars]
                full_text = msg.text + current_text
                await context.bot.edit_message_text(chat_id=msg.chat_id, message_id=msg.message_id, text=full_text,
                                                    parse_mode=ParseMode.HTML)
                i += num_chars
        await asyncio.sleep(random.uniform(0.1, 0.25))


def text_to_speech(key: str, region: str, speech_lang: str, speech_voice: str, msg_id: int, text: str):
    """
    translate text to speech
    :param key: azure_speech_key
    :param region:  azure_speech_region
    :param speech_lang: language of the voice that speaks
    :param speech_voice:  voice name eg: zh-CN-XiaoxiaoNeural
    :param msg_id:  telegram message id
    :param text : text to speech
    """
    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    file_name = f"./{datetime.now().strftime('%Y%m%d%H%M%S')}.wav"
    audio_config = speechsdk.audio.AudioOutputConfig(filename=file_name)

    # The language of the voice that speaks.
    speech_config.speech_synthesis_language = speech_lang
    speech_config.speech_synthesis_voice_name = speech_voice
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    try:
        speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()
        print(speech_synthesis_result)
        if speech_synthesis_result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted or \
                speech_synthesis_result.audio_length >= 1:
            return file_name
        else:
            return None
    except Exception as ex:
        print(f"text to speech except: {ex}")
        return
