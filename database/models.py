#!/usr/bin/python
# coding:utf-8
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey, Boolean, CheckConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Permission(Enum):
    USER = 1
    ADMIN = 2
    ROOT = 4


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
    api_count = Column(Integer, nullable=False, default=10)
    role_id = Column(Integer, ForeignKey('role.id'))
    role = relationship("Role", backref="users")

    def has_permission(self, perm: Permission):
        return self.role.permissions & perm.value == perm.value

    def has_api_count(self):
        return self.api_count > 0


class Role(Base):
    __tablename__ = 'role'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True)
    permissions = Column(Integer, nullable=False, default=Permission.USER)

    def has_permission(self, perm: Permission):
        return self.permissions & perm.value == perm.value

    def add_permission(self, perm: Permission):
        if not self.has_permission(perm):
            self.permissions += perm.value

    def remove_permission(self, perm: Permission):
        if self.has_permission(perm):
            self.permissions -= perm.value

    def reset_permission(self):
        self.permissions = 0


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
    is_default = Column(Boolean, nullable=False, default=False)
    is_available = Column(Boolean, nullable=False, default=True)

    table_args = [
        CheckConstraint('(SELECT COUNT(*) FROM ai_model WHERE is_default = 1) <= 1')
    ]


class Prompt(Base):
    __tablename__ = 'prompt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    short_desc = Column(String(64), nullable=False)
    description = Column(Text, nullable=False)
