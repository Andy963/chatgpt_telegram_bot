#!/usr/bin/env python
# -*- coding: utf-8 -*-

# File: test_dialog.py
# Author: Zhou
# Date: 2023/5/23
# Copyright: 2023 Zhou
# License:
# Description: TODO

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.model_view import DialogServices
from database.models import Base, User, AiModel

engine = create_engine('sqlite:///./test.sqlite')
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


class TestDialogServices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        session = sessionmaker(bind=engine)
        cls.session = session()
        cls.dialog_svc = DialogServices(engine)

        # create user
        ai_obj1 = AiModel(name='ChatGpt', is_default=1, is_available=1)
        ai_obj2 = AiModel(name='PaLM2', is_default=0, is_available=1)
        cls.session.add_all([ai_obj1, ai_obj2])
        cls.session.commit()
        user_obj = User(user_id='user1', chat_id=123, username='dialog_user', first_name='user1', last_name='user2')
        cls.session.add(user_obj)
        cls.session.commit()

    def test_start_new_dialog(self):
        dialog_id = self.dialog_svc.start_new_dialog('user1')
        self.assertIsNotNone(dialog_id)

    def test_get_dialog_messages(self):
        dialog_id = self.dialog_svc.start_new_dialog('user1')
        msgs = self.dialog_svc.get_dialog_messages('user1', dialog_id)
        self.assertListEqual(msgs, [])

    def test_set_dialog_messages(self):
        dialog_id = self.dialog_svc.start_new_dialog('user1')
        msgs = ['hi', 'hello']
        self.dialog_svc.set_dialog_messages('user1', msgs, dialog_id)
        result = self.dialog_svc.get_dialog_messages('user1', dialog_id)
        self.assertListEqual(result, msgs)


if __name__ == '__main__':
    unittest.main()
