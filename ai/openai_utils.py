#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: openai_utils.py
# Author: Zhou
# Date: 2023/6/7
# Copyright: 2023 Zhou
# License:
# Description: use openai to generate text for chatgpt and azure openai

import openai
import tiktoken

from config import config
from logs.log import logger


class OpenAIService:
    OPENAI_COMPLETION_OPTIONS = {
        "temperature": 0.5,
        "max_tokens": 1000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0
    }

    support_models = {'chatgpt': ['gpt-3.5-turbo'],
                      'azure': ['gpt-35-turbo', 'gpt-35-turbo-16k']
                      }

    def __init__(self, model_name: str = 'gpt-3.5-turbo',
                 api_type: str = 'chatgpt', max_token: int = 16000, **kwargs):
        """
        use gpt-3.5-turbo by default
        """
        self.model_name = model_name
        self.api_type = api_type
        self.max_token = max_token

    def gen_options(self, messages):
        """Generate options for openai
        """
        if self.model_name not in self.support_models[self.api_type]:
            raise ValueError(f"Model {self.model_name} is not supported")

        if self.api_type == 'chatgpt':
            opts = {
                "model": self.model_name,
                "messages": messages,
                "api_key": config.openai_api_key,
                **self.OPENAI_COMPLETION_OPTIONS
            }
        else:
            opts = {
                "engine": self.model_name,
                "messages": messages,
                "api_type": "azure",
                "api_base": config.azure_openai_endpoint,
                "api_version": config.azure_openai_api_version,
                "api_key": config.azure_openai_api_key,
                **self.OPENAI_COMPLETION_OPTIONS
            }
        return opts

    def _generate_msg(self, message: str, dialog_messages: list, prompt: str):
        """
        Generate messages for openai
        :param message:
        :param dialog_messages:
        :param chat_mode:
        """

        messages = []
        # tell system the role you want it to play
        if not dialog_messages:
            messages.append({"role": "system", "content": prompt})
        # take the message from the user
        ct = ' '.join([msg['content'] for msg in dialog_messages])
        rq_token = self.count_tokens(message + ct)
        while rq_token > self.max_token - 200:
            messages = messages[1:]
            ct = ' '.join([msg['content'] for msg in messages])
            rq_token = self.count_tokens(message + ct)

        for msg in dialog_messages:
            messages.append({"role": "user", "content": msg["user"]})
            messages.append({"role": "assistant", "content": msg["assistant"]})
        messages.append({"role": "user", "content": message})
        return messages

    async def send_message(self, message, dialog_messages=None,
                           prompt=None):
        """
        Send message to ask openai, same as send_message_stream, but not use
        stream mode
        """
        if dialog_messages is None:
            dialog_messages = []
        try:
            messages = self._generate_msg(message, dialog_messages, prompt)
            r = openai.ChatCompletion.create(**self.gen_options(messages))
            answer = r.choices[0].message["content"]
        except Exception as e:
            logger.error(f"error:\n\n ask: {message} \n with error {e}")
            answer = f"sth went wrong"

        return answer

    @staticmethod
    def count_tokens(text: str, encoding_name: str = "cl100k_base"):
        """
        count token
        """
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
