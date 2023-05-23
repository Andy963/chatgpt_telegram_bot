#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: test_user.py
# Author: Zhou
# Date: 2023/5/23
# Copyright: 2023 Zhou
# License:
# Description: Test User model

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.model_view import UserServices
from database.models import Base, User

engine = create_engine('sqlite:///./test.sqlite')
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


class TestUserModel(unittest.TestCase):
    def setUp(self):
        session = sessionmaker(bind=engine)
        self.session = session()
        self.user_service = UserServices(engine)

    def test_add_new_user(self):
        user_id = 'test_user'
        chat_id = 123
        username = 'test_username'
        first_name = 'test_first_name'
        last_name = 'test_last_name'

        self.user_service.add_new_user(user_id, chat_id, username, first_name, last_name)
        user = self.session.query(User).filter_by(user_id=user_id).first()

        self.assertEqual(user.user_id, user_id)
        self.assertEqual(user.chat_id, chat_id)
        self.assertEqual(user.username, username)
        self.assertEqual(user.first_name, first_name)
        self.assertEqual(user.last_name, last_name)

    def test_get_user_attribute(self):
        user_id = 'test_user'
        chat_id = 123
        username = 'test_username'
        first_name = 'test_first_name'
        last_name = 'test_last_name'
        if self.user_service.check_if_user_exists(user_id):
            self.user_service.del_user(user_id)
        self.user_service.add_new_user(user_id, chat_id, username, first_name, last_name)

        attr = self.user_service.get_user_attribute(user_id, 'username')
        self.assertEqual(attr, username)

        attr = self.user_service.get_user_attribute(user_id, 'first_name')
        self.assertEqual(attr, first_name)

    def test_set_user_attribute(self):
        user_id = 'test_user'
        chat_id = 123
        username = 'test_username'
        first_name = 'test_first_name'
        last_name = 'test_last_name'
        if self.user_service.check_if_user_exists(user_id):
            self.user_service.del_user(user_id)
        self.user_service.add_new_user(user_id, chat_id, username, first_name, last_name)

        new_username = 'new_username'
        self.user_service.set_user_attribute(user_id, 'username', new_username)

        user = self.session.query(User).filter_by(user_id=user_id).first()
        self.assertEqual(user.username, new_username)

    def test_del_user(self):
        user_id = 'test_user'
        chat_id = 123
        username = 'test_username'
        first_name = 'test_first_name'
        last_name = 'test_last_name'
        if self.user_service.check_if_user_exists(user_id):
            self.user_service.del_user(user_id)
        self.user_service.add_new_user(user_id, chat_id, username, first_name, last_name)

        self.user_service.del_user(user_id)
        self.assertFalse(self.user_service.check_if_user_exists(user_id))

    def tearDown(self):
        self.session.rollback()
        self.session.close()
        engine.dispose()


if __name__ == '__main__':
    unittest.main()
