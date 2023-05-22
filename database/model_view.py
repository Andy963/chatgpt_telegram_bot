import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import desc
from sqlalchemy.orm import sessionmaker

from .models import User, Dialog, engine, Prompt, AiModel


class Database:

    def __init__(self):
        self.engine = engine
        self.session = sessionmaker(bind=self.engine)()

    def check_if_user_exists(self, user_id: str):
        return self.session.query(User).filter_by(user_id=user_id).count() > 0

    def add_new_user(self, user_id: str, chat_id: int, username: str = "", first_name: str = "", last_name: str = ""):
        if not self.check_if_user_exists(user_id):
            user = User(**{'user_id': user_id, 'chat_id': chat_id, 'username': username, 'first_name': first_name,
                           'last_name': last_name})
            self.session.add(user)
            self.session.commit()

    def start_new_dialog(self, user_id: str, ai_model: str = "ChatGpt"):
        self.check_if_user_exists(user_id)
        user = self.session.query(User).filter_by(user_id=user_id).first()
        dialog_id = str(uuid.uuid4())
        ai_model_obj = self.session.query(AiModel).filter_by(name=ai_model).first()
        dialog = Dialog(
            **{'dialog_id': dialog_id, 'user_id': user_id, 'chat_mode': user.current_chat_mode,
               'start_time': datetime.now(),
               'messages': []}, ai_model=ai_model_obj)
        self.session.add(dialog)
        self.session.commit()

        self.session.query(User).filter_by(user_id=user_id).update({'current_dialog_id': dialog_id})
        return dialog_id

    def get_user_attribute(self, user_id: str, key: str):
        if not self.check_if_user_exists(user_id):
            return None
        user = self.session.query(User).filter_by(user_id=user_id).first()
        if not hasattr(user, key):
            raise ValueError(f"User {user_id} does not have a value for {key}")
        return getattr(user, key)

    def get_available_models(self):
        return [m.name for m in self.session.query(AiModel).filter_by(is_available=1).all()]

    def get_default_model(self):
        return self.session.query(AiModel).filter_by(is_default=1).first().name

    def set_user_attribute(self, user_id: str, key: str, value: Any):
        if not self.check_if_user_exists(user_id):
            return None
        self.session.query(User).filter_by(user_id=user_id).update({key: value})
        self.session.commit()

    def get_dialog_messages(self, user_id: str, dialog_id: Optional[str] = None, ai_model: str = "ChatGpt"):
        if not self.check_if_user_exists(user_id):
            return None
        ai_model_obj = self.session.query(AiModel).filter_by(name=ai_model).first()
        if dialog_id is None:
            dialog = self.session.query(Dialog).filter_by(ai_model=ai_model_obj).order_by(desc(Dialog.id)).first()
        if dialog:
            return dialog.messages
        return []

    def get_real_dialog_id(self, user_id: str, dialog_id: int) -> int:
        """
         if dialog_id is -1 then get the first dialog
         else from the latest dialog
        :param user_id: the user_id
        :param dialog_id: user input dialog_id
        :rtype: int
        """
        self.check_if_user_exists(user_id)
        dq = self.session.query(Dialog).filter_by(user_id=user_id)
        if dialog_id in [0, None]:
            dialog_id = dq.order_by(Dialog.start_time.desc())[0].id
        elif dialog_id < 0:
            dialog_id = dq.order_by(Dialog.start_time.asc())[-dialog_id - 1].id
        else:
            dialog_id = dq.order_by(Dialog.start_time.desc())[dialog_id - 1].id
        return dialog_id

    def set_dialog_messages(self, user_id: str, dialog_messages: list, dialog_id: Optional[str] = None,
                            ai_model: str = "ChatGpt"):
        ai_model_obj = self.session.query(AiModel).filter_by(name=ai_model).first()
        if dialog_id is None:
            dialog_id = self.get_user_attribute(user_id, "current_dialog_id")
            if dialog_id is None:
                dialog_id = self.start_new_dialog(user_id)
        dialog_obj = self.session.query(Dialog).filter_by(dialog_id=dialog_id).first()
        if dialog_obj.ai_model != ai_model_obj:
            new_dialog = Dialog(
                **{'dialog_id': str(uuid.uuid4()), 'user_id': user_id, 'chat_mode': dialog_obj.chat_mode,
                   'start_time': datetime.now()})
            new_dialog.ai_model = ai_model_obj
            new_dialog.messages = dialog_messages
            self.session.add(new_dialog)
        else:
            dialog_obj.messages = dialog_messages
            dialog_obj.ai_model = ai_model_obj

        self.session.commit()

    def get_prompts(self):
        return self.session.query(Prompt).all()

    def get_prompt(self, _id: int):
        return self.session.query(Prompt).filter_by(id=_id).first()

    def add_new_prompt(self, desc: str, prompt: str):
        self.session.add(Prompt(**{'description': prompt, 'short_desc': desc}))
        self.session.commit()

    def del_prompt(self, _id: int):
        self.session.query(Prompt).filter_by(id=_id).delete()
        self.session.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
        self.engine.dispose()
