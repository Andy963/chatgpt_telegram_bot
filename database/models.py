#!/usr/bin/python
# coding:utf-8
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, unique=True)
    chat_id = Column(Integer, nullable=False, unique=True)
    username = Column(String(64), nullable=True)
    first_name = Column(String(64), nullable=True)
    last_name = Column(String(64), nullable=True)
    last_interaction = Column(DateTime, nullable=False, default=datetime.now)
    first_seen = Column(DateTime, nullable=False, default=datetime.now)
    current_dialog_id = Column(Integer, nullable=True, default=None)
    current_chat_mode = Column(String(64), nullable=True, default='assistant')


class Dialog(Base):
    __tablename__ = 'dialog'
    id = Column(Integer, primary_key=True, autoincrement=True)
    dialog_id = Column(String(32), nullable=False, unique=True)
    user_id = Column(Integer, nullable=False)
    chat_mode = Column(String(64), nullable=False, default='assistant')
    start_time = Column(DateTime, nullable=False, default=datetime.now)
    messages = Column(JSON(), nullable=False)
    ai_model_id = Column(Integer, ForeignKey('ai_model.id'))
    ai_model = relationship("AiModel", backref="dialogs")


class AiModel(Base):
    __tablename__ = 'ai_model'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, unique=True)
    is_default = Column(Integer, nullable=False, default=0, comment='1: default, 0: not default')
    is_available = Column(Integer, nullable=False, default=1, comment='1: available, 0: not available')


class Prompt(Base):
    __tablename__ = 'prompt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    short_desc = Column(String(64), nullable=False)
    description = Column(Text, nullable=False)
