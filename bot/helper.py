#!/usr/bin/python
# coding:utf-8
import asyncio
import random
import re

from telegram.constants import ParseMode


def render_msg_with_code(msg):
    """给bot渲染返回的消息
    <b>text</b>：加粗文本
    <i>text</i>：斜体文本
    <u>text</u>：下划线文本
    <s>text</s>：删除线文本
    <a href="URL">text</a>：超链接文本
    <code>text</code>：等宽文本
    <pre>text</pre>：预格式化文本
    message = '''
    <pre>
    <code>
    def greet(name):
        print(f"Hello, {name}!")

    greet("World")
    </code>
    </pre>
    '''
    """
    if '`' not in msg:
        return msg
    import re
    p2 = re.compile(r'```.*?```', re.S)
    r2 = re.findall(p2, msg)
    for r in r2:
        lang = r.split('\n')[0].split('```')[1]
        msg = re.sub(f'```{lang}(.*?)```', rf'<pre><code>\1</code></pre>', msg, flags=re.S)
    p1 = re.compile(r'`.*?`')
    r1 = re.findall(p1, msg)
    for r in r1:
        msg = msg.replace(r, f"<code>{r.replace('`', '')}</code>")
    return msg


async def send_like_tying(update, context, text):
    """
    send msg like typing
    :param update: bot update object
    :param context: bot context
    :param text:  msg text to send
    """
    msg = await context.bot.send_message(chat_id=update.effective_chat.id, text='>>>\n', parse_mode=ParseMode.HTML)
    code_index = [(m.start(), m.end()) for m in re.finditer(r'<pre><code>(.+?)</code></pre>', text, re.S)]
    i = 0
    length = len(text)
    while i < length:
        num_chars = random.randint(1, 20) if length <= 50 else random.randint(1, 50)

        if not code_index:
            current_text = text[:i + num_chars]
            full_text = msg.text + current_text
            await context.bot.edit_message_text(chat_id=msg.chat_id, message_id=msg.message_id, text=full_text,
                                                parse_mode=ParseMode.HTML)
            i += num_chars
        else:
            start, end = code_index[0]
            # expand to end of code block
            if i + num_chars > start:
                full_text = msg.text + text[:end + 1]
                await context.bot.edit_message_text(chat_id=msg.chat_id, message_id=msg.message_id, text=full_text,
                                                    parse_mode=ParseMode.HTML)
                i = end + 1
                code_index.pop(0)
            else:
                current_text = text[:i + num_chars]
                full_text = msg.text + current_text
                await context.bot.edit_message_text(chat_id=msg.chat_id, message_id=msg.message_id, text=full_text,
                                                    parse_mode=ParseMode.HTML)
                i += num_chars
        await asyncio.sleep(random.uniform(0.1, 0.3))
