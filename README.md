## Telegram AI Bot:

This repo a Telegram AI Bot(with chatgpt, palm2 etc.). **And it works great.**

You can deploy your own bot

### Features

- List of allowed Telegram users
- ~~user `chatgpt-3.5-turbo` default~~ depends on your choice
- reply with voice message (use azure text to speech)
- multi language voice message support (azure TTS)
- picture ocr and translate, summary, tell story joke etc.
- parse a url link(only summary the text for now)
- paLM2 support(use azure translate to en and ask palm2, palm2 translate is so weak)
- azure openai support

### Bot commands

- `/retry` – Regenerate last bot answer
- `/new` – Start new dialog
- `/mode` – Select chat mode
- `/help` – Show help
- `/balance` – Check your OpenAI balance (session key required)
- `/lp` – List prompts (np, lp, dp: add new prompt, list prompt, del prompt with id)
- `/lm` - List all ai model (chatgpt, palm2, azure_openai etc.)
- `/sm` -- set default ai model

### Setup

1. Get your [OpenAI API](https://openai.com/api/) or paLM2 key, or azure openai key.

2. Get your Telegram bot token from [@BotFather](https://t.me/BotFather)

3. Get your azure free trial account and get your azure key(text,speech,computer vision)

4. Docker

for docker user:

```shell

docker run -d  --name chatgpt -v /etc/gpt:/etc/gpt andy963/telegram_chatgpt_bot:latest
```

TODO:

- [x] support voice message.
- [x] voice reply (use azure text to speech)
- [x] ~~code block~~ removed
- [x] ~~typing effect~~ hard to read, removed
- [x] reply with multiple language voice (contains En & Zh, need azure)
- [x] picture ocr and translate, summary, tell story joke etc.
- [x] ~~bing chat (gpt4) ( cookies required)~~ cookie expired soon,removed
- [x] balance check from openai
- [ ] ~~voice story~~
- [x] prompt list
- [x] get content from url and summary the content(weak)
- [ ] ~~pdf && article analysis (rate limit to 3/min, it's hard maybe later)~~ give up
- [x] paLM2 support
- [x] export history(only text for now).
- [x] multi model dialog support
  if you are using ubuntu 22.04, you need to install the latest libssl1.1 either as a binary package, or by compiling it
  from sources.
- [x] change default model
- [ ] get the latest new and summarize and send to user on schedule (maybe with voice)
- [x] azure openai support

```shell

## References
1. [*Build ChatGPT from GPT-3*](https://learnprompting.org/docs/applied_prompting/build_chatgpt)
2. [install libssl1.1](https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/quickstarts/setup-platform?pivots=programming-language-python&tabs=linux%2Cubuntu%2Cdotnet%2Cjre%2Cmaven%2Cnodejs%2Cmac%2Cpypi)
3. [bing chat](https://github.com/acheong08/EdgeGPT)