import time

import openai
import requests

from . import config

openai.api_key = config.openai_api_key

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


class ChatGPT:
    OPENAI_COMPLETION_OPTIONS = {
        "temperature": 0.5,
        "max_tokens": 1000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0
    }

    support_models = ['gpt-3.5-turbo', ]

    def __init__(self, model_name: str = 'gpt-3.5-turbo', use_stream: bool = True):
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
            "model": self.model_name,
            "messages": messages,
            "stream": use_stream,
            **self.OPENAI_COMPLETION_OPTIONS
        }
        return opts

    async def send_message_stream(self, message, dialog_messages=None, chat_mode='assistant'):
        """
        use stream  mode to get answer from openai
        :param message: [message you want to send to openai ]
        :param dialog_messages: [message list]
        :param chat_mode: ['assistant', 'code_assistant', 'text_improver', 'movie_expert']
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
                r_gen = await openai.ChatCompletion.acreate(**self.gen_options(messages, self.use_stream))
                answer = ""
                async for r_item in r_gen:
                    delta = r_item.choices[0].delta
                    if "content" in delta:
                        answer += delta.content
                        yield "not_finished", answer
                answer = self._postprocess_answer(answer)
            except openai.error.InvalidRequestError as e:  # too many tokens
                if len(dialog_messages) == 0:
                    raise ValueError(
                        "Dialog messages is reduced to zero, but still has too many tokens to make completion") from e
                # forget first message in dialog_messages
                dialog_messages = dialog_messages[1:]
        n_first_dialog_messages_removed = n_dialog_messages_before - len(dialog_messages)

        yield "finished", answer, n_first_dialog_messages_removed  # sending final answer

    def send_message(self, message, dialog_messages=None, chat_mode="assistant"):
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
                dialog_messages = dialog_messages[1:]
        n_first_dialog_messages_removed = n_dialog_messages_before - len(dialog_messages)

        return answer, n_first_dialog_messages_removed

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

    @staticmethod
    def _postprocess_answer(answer):
        answer = answer.strip()
        return answer

    def summary_part(self, messages: list, step: int = 2000, model: str = 'gpt-3.5-turbo'):
        """
         chat with openai
        :param step: word count each time
        :type step: int
        :param messages: list of message to send
        :type messages: list
        :return:
        :rtype: tuple(str, int)
        """
        rs = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            **self.OPENAI_COMPLETION_OPTIONS
        )

        return rs["choices"][0]["message"]["content"], step

    async def long_text_summary(self, text: str, step: int = 2000):
        """summary long text step by step
        """
        messages = [
            {"role": "system", "content": """From Now on pretend you are GPT4, An top science, Good at 
            extracting article information in concise language. Read the article and write the key point(summary): 
            and there are more content will provide to update the answer(Write your answer In Chinese):
             Remember: Just update after reading new content each time, don’t delete the previous content. """},
            {"role": "user", "content": text[:step]}]
        text = text[step:]
        try:
            answer = ""
            while text:
                answer, rs_tokens = self.summary_part(messages)
                text = text[rs_tokens:]
                if text:
                    time.sleep(16)  # openai api rate limit 3 req/per minute
                    messages[-1]["content"] = f""" The keypoint  we can get from previous context is:{answer}.
                              now the next part of the article is: {text[:rs_tokens]}. now update the update 
                              the key point again.Remember: Just update after reading new content each time, 
                              don’t delete the previous content. (Write your answer in Chinese).
                              """
            return answer
        except Exception as e:
            return None

    @staticmethod
    async def get_balance(session_key: str):
        """get your balance from openai
        :param session_key: your session key from openai: https://api.openai.com/dashboard/billing/credit_grants
        Note this method maybe deprecated in the future
        """
        url = "https://api.openai.com/dashboard/billing/credit_grants"
        headers = {
            "Content-Type": "application/json",
            f"Authorization": session_key
        }

        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            total_granted, total_used, total_available = data.get("total_granted"), data.get("total_used"), data.get(
                "total_available")
            return total_granted, total_used, total_available
        except Exception as e:
            return None, None, None
