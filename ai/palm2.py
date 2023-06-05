#!/usr/bin/env python
# -*- coding: utf-8 -*-

# File: palm2.py
# Author: Zhou
# Date: 2023/5/16
# Copyright: 2023 Zhou
# License:
# Description:  google paLM2 service
import google.generativeai as palm

from config import config

palm.configure(api_key=config.palm_api_key)


class GooglePalm:

    def __init__(self, model_name='models/chat-bison-001'):
        self.model = model_name

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
        response = palm.chat(model=self.model, messages=message, context=context, examples=examples, candidate_count=1)
        answer = response.last
        return answer

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
