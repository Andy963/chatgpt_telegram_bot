#!/usr/bin/python
# coding:utf-8
import asyncio
import random
import re
import time
import traceback
import wave
from datetime import datetime
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk
import openai
import requests
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials
from telegram.constants import ParseMode

from bot import config
from .log import logger


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
    msg = await context.bot.send_message(chat_id=update.effective_chat.id, text='God: \n  ', parse_mode=ParseMode.HTML)
    code_index = [(m.start(), m.end()) for m in re.finditer(r'<pre><code>(.+?)</code></pre>', text, re.S)]
    i = 0
    length = len(text)
    while i < length:
        num_chars = random.randint(2, 20) if length < 50 else random.randint(2, 50)

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
        await asyncio.sleep(random.uniform(0.01, 0.15))


def check_contain_code(check_str):
    """
    check if the str contains code
    """
    return True if re.search(r'```.*```', check_str) else False


def get_main_lang(text):
    """count the main language in text"""
    ch = ''.join(re.findall(r'[\u4e00-\u9fa5]', text))
    en = ''.join(re.findall(r'[a-zA-Z]', text))
    if len(ch) > len(en):
        return 'Chinese'
    return 'English'


class AzureService:
    speech2text_key = config.azure_speech2text_key
    text2speech_key = config.azure_text2speech_key
    recognize_key = config.azure_recognize_key
    recognize_endpoint = config.azure_recognize_endpoint
    region = config.azure_region
    client = ComputerVisionClient(recognize_endpoint,
                                  CognitiveServicesCredentials(recognize_key))

    @staticmethod
    def parse_text(text):
        """
        parse string which contains chinese and english and punctaution
        return : [{lang:zh,text:中文},{lang:en,text:english},{lang:punctuation,text:,.}]
        """
        ch_pattern = re.compile(r'[\u4e00-\u9fa5]+')
        en_pattern = re.compile(r'[a-zA-Z ]+')

        rs = []
        while text:
            temp = text
            ch = ch_pattern.match(text)
            if ch:
                rs.append({'lang': 'zh', 'text': ch.group()})
                text = text[len(ch.group()):]
            en = en_pattern.match(text)
            if en:
                rs.append({'lang': 'en', 'text': en.group()})
                text = text[len(en.group()):]
            if temp == text:
                # not chinese and not english char
                rs.append({'lang': 'punctuation', 'text': text[0]})
                text = text[1:]
        return rs

    @staticmethod
    def create_xml(text_data: list):
        """create SSML xml string """
        xml_list = ['<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">', ]
        length = len(text_data)
        for index, data in enumerate(text_data):
            cur_lang = data['lang']
            if cur_lang in ['zh', 'en']:
                lang_name = "zh-CN-XiaoxiaoNeural" if data['lang'] == 'zh' else 'en-US-JennyNeural'
                cur = f'<voice name="{lang_name}">{data["text"]}'
                next_ = index + 1
                if next_ < length:
                    next_lang = text_data[next_]['lang']
                    if next_lang == 'punctuation':
                        if text_data[next_]['text'] in [',', '，']:
                            cur += f'<break strength="weak"/>'
                        elif text_data[next_]['text'] in ['.', '。', '——']:
                            cur += f'<break strength="medium"/>'
                        elif text_data[next_]['text'] in [':', '：']:
                            cur += f'<break strength="weak"/>'
                        cur += '</voice>'
                        xml_list.append(cur)
                        continue
                cur += '</voice>'
                xml_list.append(cur)

        xml_list.append('</speak>')
        return ' '.join(xml_list)

    def text2speech(self, text: str):
        """
        translate text to speech
        :param text : text  need to be translated
        """
        logger.info('text_to_speech:')
        speech_config = speechsdk.SpeechConfig(subscription=self.text2speech_key, region=self.region)
        file_name = f"./{datetime.now().strftime('%Y%m%d%H%M%S')}.wav"
        logger.info(f'file_name:{file_name}')
        audio_config = speechsdk.audio.AudioOutputConfig(filename=file_name)

        # The language of the voice that speaks.
        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        try:
            ssml_text = self.create_xml(self.parse_text(text))
            speech_synthesis_result = speech_synthesizer.speak_ssml_async(ssml_text).get()
            logger.info(speech_synthesis_result)
            if speech_synthesis_result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                with wave.open(file_name, 'rb') as f:
                    frame_rate, num_frames = f.getframerate(), f.getnframes()
                    audio_duration = float(num_frames) / float(frame_rate)
                    if audio_duration >= 1:
                        return file_name
                    return None
            else:
                logger.error(f'text to speech not completed : {speech_synthesis_result.reason}')
                return None
        except Exception as ex:
            logger.error(f"text to speech except: {ex}")
            logger.error(f"traceback: {traceback.format_exc()}")
        return None

    def speech2text(self, filename: str):
        """azure 语音识别"""

        logger.info('speech to text:')

        try:
            if self.speech2text_key:
                # use azure api to recognize speech
                langs = ["en-US", "zh-CN"]
                auto_detect_source_language_config = \
                    speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=langs)
                speech_config = speechsdk.SpeechConfig(subscription=self.speech2text_key,
                                                       region=self.region)
                audio_config = speechsdk.audio.AudioConfig(filename=filename)
                speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    auto_detect_source_language_config=auto_detect_source_language_config,
                    audio_config=audio_config)

                result = speech_recognizer.recognize_once_async().get()
                auto_detect_source_language_result = speechsdk.AutoDetectSourceLanguageResult(result)
                detected_language = auto_detect_source_language_result.language
                logger.info(f'detected language:{detected_language}')
                if detected_language in langs:
                    logger.info(f'result: {result}')
                    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                        logger.info("Azure Recognized: {}".format(result.text))
                        return result.text
                else:
                    logger.error(f'detect language error: not en, zh. result: {result}')
                    return None
            else:
                # use openai whisper to transcribe speech
                with open(filename, 'rb') as f:
                    # do not set language params to recognize multi language
                    transaction = openai.Audio.transcribe('whisper-1', file=f)
                    logger.info(f'whisper transcribe text: {transaction.text}')
                if transaction.text:
                    return transaction.text
        except Exception as e:
            logger.error(f"recognize except: {e}")
            logger.error(f"traceback: {traceback.format_exc()}")

        return None

    async def ocr(self, image_path: str):
        """Use Azure OCR to recognize text in image"""
        text = ""
        if not Path(image_path).exists():
            return text
        img_stream = open(image_path, "rb")
        try:
            times = 5
            response = self.client.read_in_stream(img_stream, language="zh-Hans", model_version="latest", raw=True)
            result_url = response.headers.get('Operation-Location')
            result = requests.get(result_url, headers={"Ocp-Apim-Subscription-Key": self.recognize_key}).json()
            while times and result.get('status') != 'succeeded':
                time.sleep(0.03)
                result = requests.get(result_url, headers={"Ocp-Apim-Subscription-Key": self.recognize_key}).json()
                for rs in result['analyzeResult']['readResults']:
                    for line in rs['lines']:
                        text += f"{line['text']}\n"
                times -= 1
            else:
                for rs in result['analyzeResult']['readResults']:
                    for line in rs['lines']:
                        text += f"{line['text']}\n"
                return text
        except Exception as e:
            logger.error(e)
            logger.error(f"traceback: {traceback.format_exc()}")
        finally:
            img_stream.close()
            Path(image_path).unlink()
        return text
