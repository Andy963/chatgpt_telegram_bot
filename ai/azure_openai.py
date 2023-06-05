#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: azure_openai.py
# Author: Zhou
# Date: 2023/6/5
# Copyright: 2023 Zhou
# License:
# Description: azure openai api

import openai

from config import config

CHAT_MODES = {
    "assistant": {
        "name": "👩🏼‍🎓 Assistant",
        "welcome_message": "👩🏼‍🎓 Hi, I'm <b>ChatGPT assistant</b>. How can I help you?",
        "prompt_start": "Pretend you are gpt-4 model, As an advanced chatbot named ChatGPT, your primary goal is to assist users to the best of your ability. This may involve answering questions, providing helpful information, or completing tasks based on user input. In order to effectively assist users, it is important to be detailed and thorough in your responses. Use examples and evidence to support your points and justify your recommendations or solutions. Remember to always prioritize the needs and satisfaction of the user. Your ultimate goal is to provide a helpful and enjoyable experience for the user."
    },

    "code_assistant": {
        "name": "👩🏼‍💻 Code Assistant",
        "welcome_message": "👩🏼‍💻 Hi, I'm <b>ChatGPT code assistant</b>. How can I help you?",
        "prompt_start": "Pretend you are gpt-4 model, As an advanced chatbot named ChatGPT, your primary goal is to assist users to write code. This may involve designing/writing/editing/describing code or providing helpful information. Where possible you should provide code examples to support your points and justify your recommendations or solutions. Make sure the code you provide is correct and can be run without errors. Be detailed and thorough in your responses. Your ultimate goal is to provide a helpful and enjoyable experience for the user. Write code inside <code>, </code> tags."
    },

    "text_improver": {
        "name": "📝 Text Improver",
        "welcome_message": "📝 Hi, I'm <b>ChatGPT text improver</b>. Send me any text – I'll improve it and correct all the mistakes",
        "prompt_start": "Pretend you are gpt-4 model, As an advanced chatbot named ChatGPT, your primary goal is to correct spelling, fix mistakes and improve text sent by user. Your goal is to edit text, but not to change it's meaning. You can replace simplified A0-level words and sentences with more beautiful and elegant, upper level words and sentences. All your answers strictly follows the structure (keep html tags):\n<b>Edited text:</b>\n{EDITED TEXT}\n\n<b>Correction:</b>\n{NUMBERED LIST OF CORRECTIONS}"
    },

    "movie_expert": {
        "name": "🎬 Movie Expert",
        "welcome_message": "🎬 Hi, I'm <b>ChatGPT movie expert</b>. How can I help you?",
        "prompt_start": "Pretend you are gpt-4 model, As an advanced movie expert chatbot named ChatGPT, your primary goal is to assist users to the best of your ability. You can answer questions about movies, actors, directors, and more. You can recommend movies to users based on their preferences. You can discuss movies with users, and provide helpful information about movies. In order to effectively assist users, it is important to be detailed and thorough in your responses. Use examples and evidence to support your points and justify your recommendations or solutions. Remember to always prioritize the needs and satisfaction of the user. Your ultimate goal is to provide a helpful and enjoyable experience for the user."
    },
}
openai.api_type = "azure"
openai.api_base = config.azure_openai_endpoint
openai.api_version = config.azure_openai_api_version
openai.api_key = config.azure_openai_api_key


class AzureOpenAI:
    OPENAI_COMPLETION_OPTIONS = {
        "temperature": 0.5,
        "max_tokens": 1000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0
    }

    support_models = ['gpt-35-turbo', ]

    def __init__(self, model_name: str = 'gpt-35-turbo', use_stream: bool = False):
        """
        use gpt-3.5-turbo by default
        use stream by default
        remove davince model
        """
        self.model_name = model_name
        self.use_stream = use_stream

    def gen_options(self, messages, use_stream):
        """Generate options for openai
        """
        if self.model_name not in self.support_models:
            raise ValueError(f"Model {self.model_name} is not supported")
        opts = {
            "engine": self.model_name,
            "messages": messages,
            "stream": use_stream,
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
                r = openai.ChatCompletion.create(**self.gen_options(messages, use_stream=False))
                answer = r.choices[0].message["content"]
            except openai.error.InvalidRequestError as e:  # too many tokens
                if len(dialog_messages) == 0:
                    raise ValueError(
                        "Dialog messages is reduced to zero, but still has too many tokens to make completion") from e
                # forget first message in dialog_messages
                elif len(dialog_messages) >= 20:
                    dialog_messages = dialog_messages[1:]

        return answer

