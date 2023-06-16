#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: anthropic_utils.py
# Author: Zhou
# Date: 2023/6/14
# Copyright: 2023 Zhou
# License:
# Description: anthropic ai claude
import anthropic

from ai import CHAT_MODES


class AnthropicAIService:
    def __init__(self, api_key: str, model_name: str = 'claude-1-100k', **kwargs):
        self.model_name = model_name
        self.claude = anthropic.Client(api_key)

    @staticmethod
    def _generate_msg(message, dialog_messages, chat_mode):
        """
        Generate messages for openai
        :param message:
        :param dialog_messages:
        :param chat_mode:
        """
        prompt = CHAT_MODES[chat_mode]["prompt_start"]
        messages = ""
        # tell system the role you want it to play
        if not dialog_messages:
            messages = f"{anthropic.HUMAN_PROMPT} {prompt} {anthropic.AI_PROMPT}"
        # take the message from the user
        for msg in dialog_messages:
            messages += f"{anthropic.HUMAN_PROMPT} {msg['user']} {anthropic.AI_PROMPT} {msg['assistant']}"

        messages += f"{anthropic.HUMAN_PROMPT} {message} {anthropic.AI_PROMPT}"
        return messages

    async def send_message(self, message, dialog_messages=None, chat_mode="assistant"):
        """
        Send message to ask openai, same as send_message_stream, but not use stream mode
        """
        if dialog_messages is None:
            dialog_messages = []
        if chat_mode not in CHAT_MODES.keys():
            raise ValueError(f"Chat mode {chat_mode} is not supported")

        answer = None
        while answer is None:
            try:
                messages = self._generate_msg(message, dialog_messages, chat_mode)
                resp = self.claude.completion(
                    prompt=messages,
                    model="claude-1-100k",
                    max_tokens_to_sample=10000,
                )
                answer = resp['completion']
            except Exception as e:
                answer = f"claude error: {e}"

        return answer
