#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: __init__.py.py
# Author: Zhou
# Date: 2023/5/18
# Copyright: 2023 Zhou
# License:
# Description:  Database init
import os

from sqlalchemy import create_engine

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
