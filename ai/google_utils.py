#!/usr/bin/env python
# -*- coding: utf-8 -*-
from typing import Optional

# File: google_utils.py
# Author: Zhou
# Date: 2023/5/16
# Copyright: 2023 Zhou
# License:
# Description:  google paLM2 service
import google.generativeai as palm
from google.ai.generativelanguage_v1beta2 import DiscussServiceAsyncClient
from google.generativeai import count_message_tokens
from google.generativeai.discuss import DEFAULT_DISCUSS_MODEL
from google.generativeai.types import MessagePromptOptions, discuss_types

from logs.log import logger


class GoogleAIService:

    def __init__(self, api_key: str, model_name='models/chat-bison-001',
                 max_token: int = 4096):
        self.model = model_name
        palm.configure(api_key=api_key)
        self.max_token = max_token

    async def en2zh(self, message):
        """translate english to chinese
        it's weak for now
        """
        prompt = f"Please translate the following sentence into Chinese(return the translated sentence only): {message}"
        rsp = palm.generate_text(prompt=prompt)
        return rsp.result

    async def zh2en(self, message):
        """translate chinese to english
        it's weak for now
        """
        prompt = f"Please translate the following sentence into english(return the translated sentence only): '{message}'"
        rsp = palm.generate_text(prompt=prompt)
        return rsp.result

    async def send_message(self, message, dialog_messages=None,
                           examples=None, prompt=None):
        """send message to palm
        :examples: example tuple
        examples = [
            ("What's up?", # A hypothetical user input
             "What isn't up?? The sun rose another day, the world is bright, anything is possible! ☀️" # A hypothetical model response
             ),
             ("I'm kind of bored",
              "How can you be bored when there are so many fun, exciting, beautiful experiences to be had in the world? 🌈")
        ]
        """
        if dialog_messages is None:
            dialog_messages = []

        context, rs_max_token = self.gen_context(message, dialog_messages,
                                                 prompt)
        if rs_max_token < 10:
            return "Token exceed limit, please short your message"
        try:
            response = palm.chat(model=self.model, messages=message,
                                 context=context, examples=examples,
                                 candidate_count=1)
            answer = response.last

        except Exception as e:
            logger.error(f"error:\n\n ask: {message} \n with error {e}")
            answer = f"sth went wrong with palm, please try again later."
        return answer

    def gen_context(self, message, dialog_message: list, prompt: str = None):
        """generate context
        calculate context token
        calculate message token
        rsp_max_token = total_token - context_token - message_token
        if message_token > throttle token then return
        if message_token + context_token > total_token then shorter context
        """
        context = []
        rs_max_token = 4096
        if not dialog_message:
            context.append(prompt)
        for msg in dialog_message:
            context.append(f'User said: {msg["user"]}\n')
            context.append(f'Your answer is:  {msg["assistant"]}\n')
        context.append(f'User said: {message}\n')
        ct = ' '.join(context)

        rq_token = self.count_tokens(messages=message, context=ct)
        while rq_token > self.max_token - 200:
            context = context[150:]
            rq_token = self.count_tokens(messages=message,
                                         context=''.join(context))

        return ''.join(context), rs_max_token

    def count_tokens(
            self, *,
            prompt: MessagePromptOptions = None,
            context: Optional[str] = None,
            examples: Optional[discuss_types.ExamplesOptions] = None,
            messages: Optional[discuss_types.MessagesOptions] = None,
            model: str = DEFAULT_DISCUSS_MODEL,
            client: Optional[DiscussServiceAsyncClient] = None):
        """count tokens"""
        model = self.model or model
        d = count_message_tokens(prompt=prompt, context=context,
                                 examples=examples, messages=messages,
                                 model=model, client=client)
        return d.get('token_count')
