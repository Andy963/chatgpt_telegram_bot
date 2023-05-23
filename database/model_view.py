import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import desc
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import sessionmaker

from .models import User, Dialog, Prompt, AiModel


class Database:

    def __init__(self, _engine):
        self._engine = _engine
        self.session = sessionmaker(bind=self._engine)()

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.session.commit()
        else:
            self.session.rollback()
        self.session.close()
        # self._engine.dispose()


class UserServices(Database):
    def check_if_user_exists(self, user_id: str):
        """Check if user exists in database,
        use cache to reduce database query
        """
        return self.session.query(User).filter_by(user_id=user_id).count() > 0

    @contextmanager
    def user_context(self, user_id: str):
        user = self.session.query(User).filter_by(user_id=user_id).first()
        try:
            yield user
        finally:
            pass

    def add_new_user(self, user_id: str, chat_id: int, username: str = "", first_name: str = "", last_name: str = ""):
        """Add new user to database if not exists
        """
        if not self.check_if_user_exists(user_id):
            with self as session:
                user = User(**{'user_id': user_id, 'chat_id': chat_id, 'username': username, 'first_name': first_name,
                               'last_name': last_name})
                session.add(user)
        else:
            raise Exception('user already exists')

    def get_user_attribute(self, user_id: str, key: str):
        """Do Not use check if user exists before calling this method or it query the database twice,
        use try except instead
        get user's attribute by key
        """
        try:
            with self.user_context(user_id) as user:
                if not hasattr(user, key):
                    raise ValueError(f"User {user_id} does not have a value for {key}")
                return getattr(user, key)
        except NoResultFound:
            return None

    def set_user_attribute(self, user_id: str, key: str, value: Any):
        """Do Not use check if user exists before calling this method or it query the database twice,
                use try except instead
                set user's attribute by key
        """
        try:
            with self.user_context(user_id) as user:
                with self as session:
                    setattr(user, key, value)
                    session.add(user)
        except NoResultFound:
            pass

    def del_user(self, user_id: str):
        """Delete user from database
        """
        with self as session:
            session.query(User).filter_by(user_id=user_id).delete()


class DialogServices(Database):

    def start_new_dialog(self, user_id: str, ai_model: str = "ChatGpt"):
        """Start a new dialog for user"""
        with self as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            dialog_id = str(uuid.uuid4())
            ai_model_obj = session.query(AiModel).filter_by(name=ai_model).first()
            dialog = Dialog(
                **{'dialog_id': dialog_id, 'user_id': user_id, 'chat_mode': user.current_chat_mode,
                   'start_time': datetime.now(), 'messages': [], "ai_model": ai_model_obj})
            session.add(dialog)
        return dialog_id

    def get_dialog_messages(self, user_id: str, dialog_id: Optional[str] = None, ai_model: str = "ChatGpt"):
        """Get dialog messages for user"""
        user_obj = self.session.query(User).filter_by(user_id=user_id).first()
        ai_model_obj = self.session.query(AiModel).filter_by(name=ai_model).first()
        if dialog_id is None:
            dialog = self.session.query(Dialog).filter_by(user_id=user_obj.user_id, ai_model=ai_model_obj).order_by(
                desc(Dialog.id)).first()
            return dialog.messages
        else:
            dialog = self.session.query(Dialog).filter_by(user_id=user_obj.user_id, dialog_id=dialog_id,
                                                          ai_model=ai_model_obj).first()
            if dialog is not None:
                return dialog.messages
            else:
                return []

    def get_real_dialog_id(self, user_id: str, dialog_id: int) -> int:
        """
         if dialog_id is -1 then get the first dialog
         else from the latest dialog
        :param user_id: the user_id
        :param dialog_id: user input dialog_id
        """
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
            dialog_id = self.session.query(User).filter_by(user_id=user_id).first().current_dialog_id
            if dialog_id is None:
                dialog_id = self.start_new_dialog(user_id)
        dialog_obj = self.session.query(Dialog).filter_by(dialog_id=dialog_id).first()
        if dialog_obj.ai_model != ai_model_obj:
            # if the ai_model is different from the current one, then start a new dialog
            new_dialog = Dialog(
                **{'dialog_id': str(uuid.uuid4()), 'user_id': user_id, 'chat_mode': dialog_obj.chat_mode,
                   'start_time': datetime.now()})
            new_dialog.ai_model = ai_model_obj
            new_dialog.messages = dialog_messages
            self.session.add(new_dialog)
        else:
            dialog_obj.messages = dialog_messages
            dialog_obj.ai_model = ai_model_obj
            self.session.add(dialog_obj)


class ModelServices(Database):
    def get_available_models(self):
        return [m.name for m in self.session.query(AiModel).filter_by(is_available=True).all()]

    def get_default_model(self):
        return self.session.query(AiModel).filter_by(is_default=True).first().name

    def add_new_model(self, name: str, is_default: bool = False, is_available: bool = True):
        with self as session:
            session.add(AiModel(**{'name': name, 'is_default': is_default, 'is_available': is_available}))

    def del_model(self, name: str):
        with self as session:
            session.query(AiModel).filter_by(name=name).delete()

    def update_model(self, name: str, is_default: bool = False, is_available: bool = True):
        with self as session:
            model = session.query(AiModel).filter_by(name=name).first()
            model.is_default = is_default
            model.is_available = is_available
            session.add(model)

    def get_model(self, name: str):
        return self.session.query(AiModel).filter_by(name=name).first()


class PromptServices(Database):
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
