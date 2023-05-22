#!/usr/bin/python
# coding:utf-8
import os
from datetime import datetime

from sqlalchemy import Column, Integer, String, create_engine, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import text

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
    n_used_tokens = Column(Integer, nullable=False, default=0)


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


class Prompt(Base):
    __tablename__ = 'prompt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    short_desc = Column(String(64), nullable=False)
    description = Column(Text, nullable=False)


base_dir = os.path.abspath(os.path.dirname(__file__))
db_file = os.path.join(base_dir, '../db.sqlite')
db_url = f'sqlite:///{os.path.join(base_dir, db_file)}'
if not os.path.exists(db_file):
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.execute(text("INSERT INTO ai_model (name) VALUES ('ChatGpt')"))
    session.execute(text("INSERT INTO ai_model (name) VALUES ('PaLM2')"))
    session.commit()
    session.close()
else:
    engine = create_engine(db_url, echo=False)

if __name__ == '__main__':
    Base.metadata.create_all(engine)
    # Base.metadata.drop_all(engine)
