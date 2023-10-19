#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: __init__.py.py
# Author: Zhou
# Date: 2023/5/18
# Copyright: 2023 Zhou
# License:
# Description:  Database init
import os

from sqlalchemy import create_engine, Table, Column, Boolean, MetaData, text, \
    select, insert

from database.model_view import RoleServices, ModelServices, UserServices
from database.models import Base

base_dir = '/etc/aibot'
db_file = os.path.join(base_dir, 'db.sqlite')
db_url = f'sqlite:///{os.path.join(base_dir, db_file)}'
if not os.path.exists(db_file):
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)

    models_service = ModelServices(engine)
    models_service.init_models()

    role_service = RoleServices(engine)
    role_service.init_roles()

    user_service = UserServices(engine)
    user_service.init_root_user()
else:
    engine = create_engine(db_url, echo=False)
    # 2023.10.17
    # add a new column to model user
    # metadata = MetaData()
    # metadata.bind = engine
    # user_table = Table('user', metadata, autoload_with=engine)
    # if 'use_stream' not in user_table.columns:
    #     with engine.begin() as conn:
    #         conn.execute(text(
    #             'ALTER TABLE user ADD COLUMN use_stream BOOLEAN DEFAULT FALSE'))

    # 2023.10.19
    # metadata = MetaData()
    # metadata.bind = engine
    # user_table = Table('ai_model', metadata, autoload_with=engine)
    # # 开始数据库会话
    # with engine.begin() as conn:
    #     # 查询是否存在名为 "cloudflare" 的记录
    #     query = select(user_table).where(user_table.c.name == 'cloudflare')
    #     result = conn.execute(query)
    #     record = result.fetchone()
    #
    #     # 如果不存在名为 "cloudflare" 的记录，则插入一条新记录
    #     if record is None:
    #         new_record = {'name': 'cloudflare', 'is_default': False,
    #                       'is_available': True}
    #         conn.execute(insert(user_table), new_record)
