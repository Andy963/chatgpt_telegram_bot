#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: anthropic_utils.py
# Author: Zhou
# Date: 2023/6/14
# Copyright: 2023 Zhou
# License:
# Description: anthropic ai claude
import traceback

import anthropic

from logs.log import logger


class AnthropicAIService:
    def __init__(self, api_key: str, model_name: str = 'claude-2', **kwargs):
        self.model_name = model_name
        self.claude = anthropic.AsyncAnthropic(api_key=api_key)

    @staticmethod
    def _generate_msg(message, dialog_messages, prompt):
        """
        Generate messages for claude
        :param message:
        :param dialog_messages:
        :param chat_mode:
        """

        messages = ""
        # tell system the role you want it to play
        if not dialog_messages:
            messages = f"{anthropic.HUMAN_PROMPT} {prompt} {anthropic.AI_PROMPT}"
        # take the message from the user  shorten the dialog messages to
        # `prevent exceed the max token limit (100k) bz claude don't provide
        #  to calculate token , just set to 100 dialog messages
        if len(dialog_messages) > 100:
            dialog_messages = dialog_messages[-100:]
        for msg in dialog_messages:
            messages += f"{anthropic.HUMAN_PROMPT} " \
                        f"{msg['user']} {anthropic.AI_PROMPT} {msg['assistant']}"

        messages += f"{anthropic.HUMAN_PROMPT} {message} {anthropic.AI_PROMPT}"
        return messages

    async def send_message(self, message, dialog_messages=None, prompt=None):
        """
        Send message to claude without stream response
        """
        if dialog_messages is None:
            dialog_messages = []

        try:
            messages = self._generate_msg(message, dialog_messages, prompt)
            resp = await self.claude.completions.create(
                prompt=messages,
                model=self.model_name,
                max_tokens_to_sample=1000,
            )
            answer = resp.completion
        except Exception as e:
            logger.error(f"error:\n\n ask: {message} \n with error {e}")
            answer = f"sth wrong with claude, please try again later."

        return answer

    @staticmethod
    def _generate_stream_msg(message, dialog_messages, prompt):
        """
        Generate messages claude
        :param message:
        :param dialog_messages:
        :param prompt:
        """

        messages = ""
        # tell system the role you want it to play
        if not dialog_messages:
            messages = f"{anthropic.HUMAN_PROMPT} {prompt} {anthropic.AI_PROMPT}"
        for msg in dialog_messages:
            messages += f"{anthropic.HUMAN_PROMPT} " \
                        f"{msg['user']} {anthropic.AI_PROMPT} {msg['assistant']}"

        messages += f"{anthropic.HUMAN_PROMPT} {message} {anthropic.AI_PROMPT}"
        return messages

    async def send_message_stream(self, message, dialog_messages=None,
                                  prompt=None):
        """
        Send message with stream response
        """
        if dialog_messages is None:
            dialog_messages = []

        try:
            messages = self._generate_stream_msg(message, dialog_messages,
                                                 prompt)
            answer = await self.claude.completions.create(
                prompt=messages,
                model=self.model_name,
                max_tokens_to_sample=500,
                stream=True
            )
        except Exception as e:
            logger.error(f"error:\n\n ask: {message} \n with error {e}")

            # 创建一个空的异步生成器
            async def empty_generator():
                if False:  # 这将永远不会执行
                    yield
            answer = empty_generator()
        return answer
