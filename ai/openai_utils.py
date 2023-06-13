#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: openai_utils.py
# Author: Zhou
# Date: 2023/6/7
# Copyright: 2023 Zhou
# License:
# Description: use openai to generate text for chatgpt and azure openai

import openai

from ai import CHAT_MODES
from config import config


class OpenAIService:
    OPENAI_COMPLETION_OPTIONS = {
        "temperature": 0.5,
        "max_tokens": 1000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0
    }

    support_models = {'chatgpt': ['gpt-3.5-turbo'],
                      'azure': ['gpt-35-turbo']
                      }

    def __init__(self, model_name: str = 'gpt-3.5-turbo', api_type: str = 'chatgpt', **kwargs):
        """
        use gpt-3.5-turbo by default
        """
        self.model_name = model_name
        self.api_type = api_type

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

    @staticmethod
    def _generate_msg(message, dialog_messages, chat_mode):
        """
        Generate messages for openai
        :param message:
        :param dialog_messages:
        :param chat_mode:
        """
        prompt = CHAT_MODES[chat_mode]["prompt_start"]
        messages = []
        # tell system the role you want it to play
        if not dialog_messages:
            messages.append({"role": "system", "content": prompt})
        # take the message from the user
        for msg in dialog_messages:
            messages.append({"role": "user", "content": msg["user"]})
            messages.append({"role": "assistant", "content": msg["assistant"]})
        messages.append({"role": "user", "content": message})
        return messages

    async def send_message(self, message, dialog_messages=None, chat_mode="assistant"):
        """
        Send message to ask openai, same as send_message_stream, but not use stream mode
        """
        if dialog_messages is None:
            dialog_messages = []
        if chat_mode not in CHAT_MODES.keys():
            raise ValueError(f"Chat mode {chat_mode} is not supported")

        n_dialog_messages_before = len(dialog_messages)
        answer = None
        while answer is None:
            try:
                messages = self._generate_msg(message, dialog_messages, chat_mode)
                r = openai.ChatCompletion.create(**self.gen_options(messages))
                answer = r.choices[0].message["content"]
            except openai.error.InvalidRequestError as e:  # too many tokens
                if len(dialog_messages) == 0:
                    raise ValueError(
                        "Dialog messages is reduced to zero, but still has too many tokens to make completion") from e
                # forget first message in dialog_messages
                elif len(dialog_messages) >= 20:
                    dialog_messages = dialog_messages[1:]

        return answer
