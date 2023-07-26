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
import tiktoken
from azure.ai.translation.text import TextTranslationClient, TranslatorCredential
from azure.ai.translation.text.models import InputTextItem
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.core.exceptions import HttpResponseError
from msrest.authentication import CognitiveServicesCredentials
from telegram.constants import ParseMode

from config import config
from logs.log import logger


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
    if "<" in msg:
        msg = msg.replace("<", "&lt;")
    if ">" in msg:
        msg = msg.replace(">", "&gt;")
    p2 = re.compile(r"```.*?```", re.S)
    r2 = re.findall(p2, msg)
    for r in r2:
        lang = r.split("\n")[0].split("```")[1]
        msg = re.sub(f"```{lang}(.*?)```", r"<code>\1</code>", msg, flags=re.S)
    # resolve <img > tag
    msg = re.sub(r'<img src="(.*?)".*>', r"![](\1)", msg, flags=re.S)
    # resolve `` code
    msg = re.sub(r"`(\w+)`", r"<pre>\1</pre>", msg, flags=re.S)
    return msg


async def send_like_tying(update, context, text):
    """
    send msg like typing
    :param update: bot update object
    :param context: bot context
    :param text:  msg text to send
    """
    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id, text="🗣", parse_mode=ParseMode.HTML
    )
    code_index = [
        (m.start(), m.end())
        for m in re.finditer(r"<pre><code>(.+?)</code></pre>", text, re.S)
    ]
    i = 0
    length = len(text)
    while i < length:
        num_chars = random.randint(2, 20) if length < 50 else random.randint(10, 50)

        if not code_index:
            current_text = text[: i + num_chars]
            full_text = msg.text + f"\n\t{current_text}\n"
            await context.bot.edit_message_text(
                chat_id=msg.chat_id,
                message_id=msg.message_id,
                text=full_text,
                parse_mode=ParseMode.HTML,
            )
            i += num_chars
        else:
            start, end = code_index[0]
            # expand to end of code block
            if i + num_chars > start:
                full_text = msg.text + f"\n\t{current_text}\n"
                await context.bot.edit_message_text(
                    chat_id=msg.chat_id,
                    message_id=msg.message_id,
                    text=full_text,
                    parse_mode=ParseMode.HTML,
                )
                i = end + 1
                code_index.pop(0)
            else:
                current_text = text[: i + num_chars]
                full_text = msg.text + f"\n\t{current_text}\n"
                await context.bot.edit_message_text(
                    chat_id=msg.chat_id,
                    message_id=msg.message_id,
                    text=full_text,
                    parse_mode=ParseMode.HTML,
                )
                i += num_chars
        await asyncio.sleep(random.uniform(0.01, 0.15))


def check_contain_code(check_str):
    """
    check if the str contains code
    """
    return True if re.search("`.*`", check_str) else False


def get_main_lang(text):
    """count the main language in text"""
    ch = "".join(re.findall(r"[\u4e00-\u9fa5]", text))
    en = "".join(re.findall(r"[a-zA-Z]", text))
    if len(ch) > len(en):
        return "Chinese"
    return "English"


class AzureService:
    region = config.azure_region

    def __init__(self):
        self.speech2text_key = config.azure_speech2text_key
        self.speech2text_service_available = True if self.speech2text_key else False

        self.text2speech_key = config.azure_text2speech_key
        self.text2speech_service_available = True if self.text2speech_key else False

        self.recognize_key = config.azure_recognize_key
        self.recognize_endpoint = config.azure_recognize_endpoint
        if self.recognize_key and self.recognize_endpoint:
            self.ocr_service_available = True
            self.client = ComputerVisionClient(
                self.recognize_endpoint,
                CognitiveServicesCredentials(self.recognize_key)
            )

        self.translate_key = config.azure_translate_key
        self.translate_endpoint = config.azure_translate_endpoint
        if self.translate_key and self.translate_endpoint:
            self.translate_service_available = True
            self.credential = TranslatorCredential(self.translate_key, self.region)
            self.text_translator = TextTranslationClient(
                endpoint=self.translate_endpoint, credential=self.credential
            )

    def translate(
            self, text: str, src_lang: str = "zh-Hans", target_lang: str = "en-us"
    ):
        """use azure translate api to translate text"""
        if not self.translate_service_available:
            return
        try:
            target_languages = [target_lang]
            input_text_elements = [InputTextItem(text=text)]

            response = self.text_translator.translate(
                content=input_text_elements, to=target_languages
            )
            translation = response[0] if response else None
            rs = ""
            for translated_text in translation.translations:
                rs += translated_text.text
            return rs
        except HttpResponseError as exception:
            logger.error(f"translate error: {exception}")
            logger.error(f"translate error Message: {exception.error.message}")
        return ""

    @staticmethod
    def parse_text(text):
        """
        parse string which contains chinese and english and punctaution
        return : [{lang:zh,text:中文},{lang:en,text:english},{lang:punctuation,text:,.}]
        """
        ch_pattern = re.compile(r"[\u4e00-\u9fa5]+")
        en_pattern = re.compile(r"[a-zA-Z ]+")

        rs = []
        while text:
            temp = text
            ch = ch_pattern.match(text)
            if ch:
                rs.append({"lang": "zh", "text": ch.group()})
                text = text[len(ch.group()):]
            en = en_pattern.match(text)
            if en:
                rs.append({"lang": "en", "text": en.group()})
                text = text[len(en.group()):]
            if temp == text:
                # not chinese and not english char
                rs.append({"lang": "punctuation", "text": text[0]})
                text = text[1:]
        return rs

    @staticmethod
    def create_xml(text_data: list, rate: float = 1.0):
        """create SSML xml string"""
        xml_list = [
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">',
        ]
        length = len(text_data)
        for index, data in enumerate(text_data):
            cur_lang = data["lang"]
            if cur_lang in ["zh", "en"]:
                lang_name = (
                    "zh-CN-XiaoxiaoNeural"
                    if data["lang"] == "zh"
                    else "en-US-JennyNeural"
                )
                cur = f'<voice name="{lang_name}" rate="{rate}">{data["text"]}'
                next_ = index + 1
                if next_ < length:
                    next_lang = text_data[next_]["lang"]
                    if next_lang == "punctuation":
                        if text_data[next_]["text"] in [",", "，"]:
                            cur += f'<break strength="weak"/>'
                        elif text_data[next_]["text"] in [
                            ".",
                            "。",
                            "——",
                        ] and not re.search(r"\d\.?\d*", data["text"]):
                            cur += f'<break strength="medium"/>'
                        elif text_data[next_]["text"] in [":", "："]:
                            cur += f'<break strength="weak"/>'
                        cur += "</voice>"
                        xml_list.append(cur)
                        continue
                cur += "</voice>"
                xml_list.append(cur)

        xml_list.append("</speak>")
        return " ".join(xml_list)

    def text2speech(self, text: str):
        """
        translate text to speech
        :param text : text  need to be translated
        """
        if not self.text2speech_service_available:
            return
        logger.info("text_to_speech:")
        speech_config = speechsdk.SpeechConfig(
            subscription=self.text2speech_key, region=self.region
        )
        file_name = f"./{datetime.now().strftime('%Y%m%d%H%M%S')}.wav"
        logger.info(f"file_name:{file_name}")
        audio_config = speechsdk.audio.AudioOutputConfig(filename=file_name)

        # The language of the voice that speaks.
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )
        try:
            ssml_text = self.create_xml(self.parse_text(text))
            speech_synthesis_result = speech_synthesizer.speak_ssml_async(
                ssml_text
            ).get()
            logger.info(speech_synthesis_result)
            if (
                    speech_synthesis_result.reason
                    == speechsdk.ResultReason.SynthesizingAudioCompleted
            ):
                with wave.open(file_name, "rb") as f:
                    frame_rate, num_frames = f.getframerate(), f.getnframes()
                    audio_duration = float(num_frames) / float(frame_rate)
                    if audio_duration >= 1:
                        return file_name
                    return None
            else:
                logger.error(
                    f"text to speech not completed : {speech_synthesis_result.reason}"
                )
                return None
        except Exception as ex:
            logger.error(f"text to speech except: {ex}")
            logger.error(f"traceback: {traceback.format_exc()}")
        return None

    def speech2text(self, filename: str):
        """azure 语音识别"""
        if not self.speech2text_service_available:
            return
        logger.info("speech to text:")

        try:
            # use azure api to recognize speech
            langs = ["en-US", "zh-CN"]
            auto_detect_source_language_config = (
                speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                    languages=langs
                )
            )
            speech_config = speechsdk.SpeechConfig(
                subscription=self.speech2text_key, region=self.region
            )
            audio_config = speechsdk.audio.AudioConfig(filename=filename)
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config,
                auto_detect_source_language_config=auto_detect_source_language_config,
                audio_config=audio_config,
            )

            result = speech_recognizer.recognize_once_async().get()
            auto_detect_source_language_result = (
                speechsdk.AutoDetectSourceLanguageResult(result)
            )
            detected_language = auto_detect_source_language_result.language
            logger.info(f"detected language:{detected_language}")
            logger.info(f"result: {result}")
            if detected_language in langs:
                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    logger.info("Azure Recognized: {}".format(result.text))
                    return result.text
            else:
                logger.error(f"detect language error: not en, zh. result: {result}")
                return None
        except Exception as e:
            logger.error(f"recognize except: {e}")
            logger.error(f"traceback: {traceback.format_exc()}")

        return None

    async def ocr(self, image_path: str):
        """Use Azure OCR to recognize text in image"""
        if not self.ocr_service_available:
            return
        text = ""
        if not Path(image_path).exists():
            return text
        img_stream = open(image_path, "rb")
        try:
            times = 5
            response = self.client.read_in_stream(
                img_stream, language="zh-Hans", model_version="latest", raw=True
            )
            result_url = response.headers.get("Operation-Location")
            result = requests.get(
                result_url, headers={"Ocp-Apim-Subscription-Key": self.recognize_key}
            ).json()
            while times and result.get("status") != "succeeded":
                time.sleep(0.03)
                result = requests.get(
                    result_url,
                    headers={"Ocp-Apim-Subscription-Key": self.recognize_key},
                ).json()
                for rs in result["analyzeResult"]["readResults"]:
                    for line in rs["lines"]:
                        text += f"{line['text']}\n"
                times -= 1
            else:
                for rs in result["analyzeResult"]["readResults"]:
                    for line in rs["lines"]:
                        text += f"{line['text']}\n"
                return text
        except Exception as e:
            logger.error(e)
            logger.error(f"traceback: {traceback.format_exc()}")
        finally:
            img_stream.close()
            Path(image_path).unlink()
        return text


def num_tokens_from_string(string: str, encoding_name: str = "gpt2") -> tuple:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    tokens = encoding.encode(string)
    return len(tokens), tokens, encoding
