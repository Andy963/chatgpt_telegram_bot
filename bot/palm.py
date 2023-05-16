#!/usr/bin/env python
# -*- coding: utf-8 -*-

# File: palm.py
# Author: Zhou
# Date: 2023/5/16
# Copyright: 2023 Zhou
# License:
# Description: TODO
import google.generativeai as palm

from . import config
from .helper import AzureService

palm.configure(api_key=config.palm_api_key)

azure_service = AzureService()


class GooglePalm:

    def __init__(self, model_name='models/chat-bison-001'):
        self.model = model_name

    async def send_message(self, message, dialog_messages=None, examples=None):
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

        context = self.gen_context(message, dialog_messages)
        tr_message = azure_service.translate(message)
        message = tr_message if tr_message else message
        response = palm.chat(model=self.model, messages=message, context=context, examples=examples, candidate_count=1)
        answer = response.last
        return answer, tr_message

    @staticmethod
    def gen_context(message, dialog_message: list):
        """generate context"""
        context = []
        if not dialog_message:
            context.append('Try your best to help me!\n')
        for msg in dialog_message:
            context.append(f'User said: {msg["user"]}\n')
            context.append(f'Your answer is:  {msg["assistant"]}\n')

        return ''.join(context)
