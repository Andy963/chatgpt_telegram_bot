# ChatGPT Telegram Bot: **Fast. No daily limits. Special chat modes**

<div align="center">
<img src="https://raw.githubusercontent.com/karfly/chatgpt_telegram_bot/main/static/header.png" align="center" style="width: 100%" />
</div>

<p align="center">
<a href="https://t.me/chatgpt_karfly_bot" alt="Run Telegram Bot shield"><img src="https://img.shields.io/badge/RUN-Telegram%20Bot-blue" /></a>
</p>

We all love [chat.openai.com](https://chat.openai.com), but... It's TERRIBLY laggy, has daily limits, and is only
accessible through an archaic web interface.

This repo is ChatGPT re-created with GPT-3.5 LLM as Telegram Bot. **And it works great.**

You can deploy your own bot, or use mine: [@chatgpt_karfly_bot](https://t.me/chatgpt_karfly_bot)

~~if you want to use 'text-davinci-003' set the `use_chatgpt_api: false` in config.yml~~

## Features

- Low latency replies (it usually takes about 3-5 seconds)
- No request limits
- Code highlighting
- Special chat modes: 👩🏼‍🎓 Assistant, 👩🏼‍💻 Code Assistant, 🎬 Movie Expert. More soon
- List of allowed Telegram users
- user `chatgpt-3.5-turbo` default
- reply with voice message (use azure text to speech)
- multi language voice message support (azure TTS)
- picture ocr and translate, summary, tell story joke etc.
- if you are not satisfied with gpt-3.5 answer, you can use ask new bing.

## Bot commands

- `/retry` – Regenerate last bot answer
- `/new` – Start new dialog
- `/mode` – Select chat mode
- `/help` – Show help
- `/balance` – Check your OpenAI balance (session key required)
- `/lp` – List prompts (np, lp, dp: add new prompt, list prompt, del prompt with id)

## Setup

1. Get your [OpenAI API](https://openai.com/api/) key

2. Get your Telegram bot token from [@BotFather](https://t.me/BotFather)

3. Get your azure free trial account and get your azure key(text,speech,computer vision)

4. Get your bing chat cookies

5. Docker

for docker user:

```shell

docker run -d  --name chatgpt -v /etc/gpt:/etc/gpt andy963/telegram_chatgpt_bot:latest
```

TODO:

- [x] support voice message.
- [x] voice reply (use azure text to speech)
- [x] code block
- [x] typing effect
- [x] reply with multiple language voice (contains En & Zh, need azure)
- [x] picture ocr and translate, summary, tell story joke etc.
- [x] bing chat (gpt4) ( cookies required)
- [x] balance check from openai 
- [ ] ~~voice story~~
- [x] prompt list
- [ ] pdf && article analysis (rate limit to 3/min, it's hard maybe later)
- [ ] ~~bard~~ (no api, and it's weak, maybe claude is better).
- [x] export history(only text for now).
  if you are using ubuntu 22.04, you need to install the latest libssl1.1 either as a binary package, or by compiling it
  from sources.

```shell

## References
1. [*Build ChatGPT from GPT-3*](https://learnprompting.org/docs/applied_prompting/build_chatgpt)
2. [install libssl1.1](https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/quickstarts/setup-platform?pivots=programming-language-python&tabs=linux%2Cubuntu%2Cdotnet%2Cjre%2Cmaven%2Cnodejs%2Cmac%2Cpypi)
3. [bing chat](https://github.com/acheong08/EdgeGPT)