#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: test_prompt.py
# Author: Zhou
# Date: 2023/5/23
# Copyright: 2023 Zhou
# License:
# Description: Test prompt

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.model_view import PromptServices
from database.models import Base, Prompt

engine = create_engine('sqlite:///./test.sqlite')
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


class TestPromptService(unittest.TestCase):

    def setUp(self) -> None:
        session = sessionmaker(bind=engine)
        self.session = session()
        self.prompt_svc = PromptServices(engine)

    def test_1get_prompt(self):
        if self.session.query(Prompt).count() > 0:
            self.session.query(Prompt).delete()
            self.session.commit()
        self.prompt_svc.add_new_prompt('desc1', 'prompt1')
        prompt = self.prompt_svc.get_prompt(1)
        self.assertEqual(prompt.short_desc, 'desc1')
        self.assertEqual(prompt.description, 'prompt1')

    def test_2get_prompts(self):
        if self.session.query(Prompt).count() > 0:
            self.session.query(Prompt).delete()
            self.session.commit()
        self.prompt_svc.add_new_prompt('desc1', 'prompt1')
        self.prompt_svc.add_new_prompt('desc2', 'prompt2')
        prompts = self.prompt_svc.get_prompts()
        self.assertEqual(len(prompts), 2)

    def test_3add_new_prompt(self):
        if self.session.query(Prompt).count() > 0:
            self.session.query(Prompt).delete()
            self.session.commit()
        self.prompt_svc.add_new_prompt('desc1', 'prompt1')
        prompts = self.prompt_svc.get_prompts()
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0].short_desc, 'desc1')
        self.assertEqual(prompts[0].description, 'prompt1')

    def test_4del_prompt(self):
        if self.session.query(Prompt).count() > 0:
            self.session.query(Prompt).delete()
            self.session.commit()
        self.prompt_svc.add_new_prompt('desc1', 'prompt1')
        prompt = self.prompt_svc.get_prompt(1)
        self.assertEqual(prompt.short_desc, 'desc1')

        self.prompt_svc.del_prompt(1)
        prompts = self.prompt_svc.get_prompts()
        self.assertEqual(len(prompts), 0)
