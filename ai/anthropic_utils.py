#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: anthropic_utils.py
# Author: Zhou
# Date: 2023/6/14
# Copyright: 2023 Zhou
# License:
# Description: anthropic ai claude
import anthropic

from logs.log import logger


class AnthropicAIService:
    def __init__(self, api_key: str, model_name: str = 'claude-2', **kwargs):
        self.model_name = model_name
        self.claude = anthropic.Client(api_key)

    @staticmethod
    def _generate_msg(message, dialog_messages, prompt):
        """
        Generate messages for openai
        :param message:
        :param dialog_messages:
        :param chat_mode:
        """

        messages = ""
        # tell system the role you want it to play
        if not dialog_messages:
            messages = f"{anthropic.HUMAN_PROMPT} {prompt} {anthropic.AI_PROMPT}"
        # take the message from the user
        # shorten the dialog messages to prevent exceed the max token limit (100k)
        # bz claude don't provide function to calculate token , just set to 100 dialog messages
        if len(dialog_messages) > 100:
            dialog_messages = dialog_messages[-100:]
        for msg in dialog_messages:
            messages += f"{anthropic.HUMAN_PROMPT} {msg['user']} {anthropic.AI_PROMPT} {msg['assistant']}"

        messages += f"{anthropic.HUMAN_PROMPT} {message} {anthropic.AI_PROMPT}"
        return messages

    async def send_message(self, message, dialog_messages=None, prompt=None):
        """
        Send message to ask openai, same as send_message_stream, but not use stream mode
        """
        if dialog_messages is None:
            dialog_messages = []

        try:
            messages = self._generate_msg(message, dialog_messages, prompt)
            resp = self.claude.completion(
                prompt=messages,
                model=self.model_name,
                max_tokens_to_sample=10000,
            )
            answer = resp['completion']
        except Exception as e:
            logger.error(f"error:\n\n ask: {message} \n with error {e}")
            answer = f"sth wrong with claude, please try again later."

        return answer
