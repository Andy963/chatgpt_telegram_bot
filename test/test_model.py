#!/usr/bin/env python
# -*- coding: utf-8 -*-

# File: test_model.py
# Author: Zhou
# Date: 2023/5/23
# Copyright: 2023 Zhou
# License:
# Description: TODO

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.model_view import ModelServices
from database.models import Base, AiModel

engine = create_engine('sqlite:///./test.sqlite')
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


class TestModelServices(unittest.TestCase):
    continue_after_fail = True

    def setUp(self):
        session = sessionmaker(bind=engine)
        self.session = session()
        self.model_svc = ModelServices(engine)

    def test_1get_available_models(self):
        print('start test_get_available_models')
        models = self.model_svc.get_available_models()
        self.assertListEqual(models, [])

    def test_2add_new_model(self):
        print('start test_add_new_model')
        models = self.model_svc.get_available_models()
        self.model_svc.add_new_model('model1')
        models = self.model_svc.get_available_models()
        self.assertListEqual(models, ['model1'])

    def test_3set_default_model(self):
        print('start test_set_default_model')
        if self.session.query(AiModel).count() > 0:
            self.session.query(AiModel).delete()
            # if some operation like update, insert, delete without commit, the database will locked
            # bcz sqlite use single thread to access database
            self.session.commit()
        self.model_svc.add_new_model('model1', is_default=True)
        default_model = self.model_svc.get_default_model()
        self.assertEqual(default_model, 'model1')
        self.session.close()

    def test_4update_model(self):
        if self.session.query(AiModel).count() > 0:
            self.session.query(AiModel).delete()
            self.session.commit()
        self.model_svc.add_new_model('model1', is_available=True)
        self.model_svc.update_model('model1', is_available=False)
        models = self.model_svc.get_available_models()
        self.assertListEqual(models, [])


if __name__ == '__main__':
    unittest.main()
