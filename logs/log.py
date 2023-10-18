#!/usr/bin/python
# coding:utf-8
import logging
import os
from logging import handlers

from config import config


class FileSplitLogger:
    """
    按文件大小分割的logger
    logger 默认是单例模式，只要传入的日志文件名一样，得到的都是同一个对象，即使其它参数改变，也不影响
    """

    # 日志级别关系映射
    level_relations = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    def __init__(
        self,
        filename,
        level="info",
        back_count=5,
        max_bytes=10 * 1024 * 1024,
        encoding="utf-8",
        to_stream=False,
        fmt="%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s",
    ):
        # f_dir, f_name = os.path.split(filename)
        # os.makedirs(f_dir, exist_ok=True)  # 当前目录新建log文件夹

        format_str = logging.Formatter(fmt)  # 设置日志格式

        self.logger = logging.getLogger(filename)
        self.logger.setLevel(
            self.level_relations.get(level, logging.INFO)
        )  # 设置日志级别,默认为INFO

        # 按文件大小分割的日志记录
        fs = handlers.RotatingFileHandler(
            filename=filename,
            maxBytes=max_bytes,
            backupCount=back_count,
            encoding=encoding,
        )
        fs.setFormatter(format_str)
        self.logger.addHandler(fs)
        if to_stream:
            sh = logging.StreamHandler()  # 往屏幕上输出
            sh.setFormatter(format_str)  # 设置屏幕上显示的格式
            self.logger.addHandler(sh)  # 把对象加到logger里

    def __call__(self):
        return self.logger


fs = FileSplitLogger(filename=config.log, level="debug", to_stream=True)()
if os.environ.get("is_console"):
    fs.removeHandler(fs.handlers[1])  # 移除流输出handler
else:
    fs.removeHandler(fs.handlers[0])  # 移除文件handler
logger = fs
if __name__ == "__main__":
    logger = FileSplitLogger(
        "./tests.log",
        "debug",
        max_bytes=100,
    )()
