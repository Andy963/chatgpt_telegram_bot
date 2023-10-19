#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: cloudflare_utils.py
# Author: Zhou
# Date: 2023/10/18
# Copyright: 2023 Zhou
# License:
# Description: cloudflare worker AI
import requests

from logs.log import logger


class CloudflareAIService:

    def __init__(self, token, account_id,
                 model_name='@cf/meta/llama-2-7b-chat-int8'):
        self.model = model_name
        self.token = token
        self.API_BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/"
        self.headers = {"Authorization": self.token}

    @staticmethod
    def _gen_msg(q_msg, dialog_messages, prompt):
        messages = []
        if not dialog_messages:
            messages.append({"role": "system",
                             "content": "You're an assistant, knows everything! "})
        # llma can't handle context
        # if len(dialog_messages) > 5:
        #     dialog_messages = dialog_messages[-5:]
        # for msg in dialog_messages:
        #     messages.append({"role": "user", "content": msg["user"]})
        #     messages.append({"role": "system", "content": msg["assistant"]})
        messages.append({"role": "user", "content": q_msg})
        return messages

    @staticmethod
    def parse_answer(answer):
        ss = ["[INST:<<SYS>>", "<</SYS>>[/INST", "<</SYS>>[/INST]",
              "INST:<<SYS>>"]
        for s in ss:
            answer = answer.replace(s, "")
        return answer

    def send_message(self, message, dialog_messages=None, prompt=None):
        if dialog_messages is None:
            dialog_messages = []
        try:
            data = {"messages": self._gen_msg(message,[], prompt)}
            response = requests.post(f"{self.API_BASE_URL}{self.model}",
                                     headers=self.headers,
                                     json=data).json()
            """
            {'result': {'response': "I apologize "}, 'success': True, 'errors': [], 'messages': []}
            """
            if response['success']:
                return self.parse_answer(response['result']['response'])
            return response['errors'][0]
        except Exception as e:
            logger.error(f"error:\n\n ask: {message} \n with error {e}")
            answer = f"sth went wrong"
        return answer
