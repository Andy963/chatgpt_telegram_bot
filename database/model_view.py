import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import desc
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import sessionmaker

from config import config
from .models import User, Dialog, Prompt, AiModel, Permission, Role


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


class RoleServices(Database):
    def init_roles(self):
        with self as session:
            roles = {
                'User': [Permission.USER, ],
                'Admin': [Permission.USER, Permission.ADMIN],
                'Root': [Permission.USER, Permission.ADMIN, Permission.ROOT],
            }
            for r in roles:
                role = self.session.query(Role).filter_by(name=r).first()
                if role is None:
                    role = Role(name=r)
                role.reset_permission()
                for p in roles[r]:
                    role.add_permission(p)
                session.add(role)

    def get_default_role(self):
        return self.session.query(Role).filter_by(name='User').first()


class UserServices(Database):
    def check_if_user_exists(self, user_id: str):
        """Check if user exists in database,
        use cache to reduce database query
        """
        return self.session.query(User).filter_by(user_id=user_id).count() > 0

    def add_new_user(self, user_id: str, chat_id: int, username: str = "", first_name: str = "", last_name: str = "",
                     role_id: int = 0):
        """Add new user to database if not exists
        """
        if not self.check_if_user_exists(user_id):
            if role_id == 0:
                role_id = RoleServices(self._engine).get_default_role().id
            with self as session:
                user = User(**{'user_id': user_id, 'chat_id': chat_id, 'username': username, 'first_name': first_name,
                               'last_name': last_name, 'role_id': role_id})
                session.add(user)
        else:
            raise Exception('user already exists')

    def get_user_attribute(self, user_id: str, key: str):
        """Do Not use check if user exists before calling this method or it query the database twice,
        use try except instead
        get user's attribute by key
        """
        try:
            user = self.session.query(User).filter_by(user_id=user_id).first()
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
            user = self.session.query(User).filter_by(user_id=user_id).first()
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

    def get_user_by_user_id(self, user_id):
        # telegram user id
        return self.session.query(User).filter_by(user_id=user_id).first()

    def init_root_user(self):
        with self as session:
            role_id = session.query(Role).filter_by(name='Root').first().id
            user = session.query(User).filter_by(user_id=config.root_user_id).first()
            if user:
                if role_id and user.role_id != role_id:
                    user.role_id = role_id
                    session.add(user)
            else:
                self.add_new_user(config.root_user_id, 0, role_id=role_id)


class DialogServices(Database):

    def start_new_dialog(self, user_id: str):
        """Start a new dialog for user"""
        with self as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            ai_models = session.query(AiModel).filter_by(is_available=True).all()
            dialog_list = []
            for ai in ai_models:
                dialog = Dialog(
                    **{'dialog_id': str(uuid.uuid4()), 'user_id': user_id, 'chat_mode': user.current_chat_mode,
                       'start_time': datetime.now(), 'messages': [], "ai_model": ai})
                dialog_list.append(dialog)
            session.add_all(dialog_list)
            default_model = session.query(AiModel).filter_by(is_default=True).first()
            return session.query(Dialog).filter_by(user_id=user_id, ai_model=default_model).first()

    def get_dialog_messages(self, user_id: str, dialog_id: Optional[str] = None, ai_model: str = "ChatGpt"):
        """Get dialog messages for user"""
        user_obj = self.session.query(User).filter_by(user_id=user_id).first()
        ai_model_obj = self.session.query(AiModel).filter_by(name=ai_model).first()
        if dialog_id is None:
            dialog = self.session.query(Dialog).filter_by(user_id=user_obj.user_id, ai_model=ai_model_obj).order_by(
                desc(Dialog.id)).first()
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

    def set_dialog_messages(self, user_id: str, dialog_messages: list,
                            ai_model: str = "ChatGpt"):
        ai_model_obj = self.session.query(AiModel).filter_by(name=ai_model).first()
        user_obj = self.session.query(User).filter_by(user_id=user_id).first()
        dialog_obj = self.session.query(Dialog).filter_by(user_id=user_id, ai_model=ai_model_obj).order_by(
            desc(Dialog.id)).first()
        if dialog_obj is None:
            dialog_id = str(uuid.uuid4())
            new_dialog = Dialog(
                **{'dialog_id': dialog_id, 'user_id': user_id,
                   'start_time': datetime.now(), 'messages': dialog_messages})
            new_dialog.ai_model = ai_model_obj
            self.session.add(new_dialog)
            user_obj.current_dialog_id = dialog_id
            self.session.add(user_obj)
        else:
            dialog_obj.messages = dialog_messages
            self.session.merge(dialog_obj)

        self.session.commit()


class ModelServices(Database):

    def init_models(self):
        # init models from config available models
        models = config.ai_models.split(' ')
        for index, model_name in enumerate(models, 1):
            self.add_new_model(model_name, is_default=model_name == 'Claude', is_available=True)

    def get_available_models(self):
        return [m.name for m in self.session.query(AiModel).filter_by(is_available=True).all()]

    def get_default_model(self):
        return self.session.query(AiModel).filter_by(is_default=True).first()

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

    def list_all_model(self):
        return self.session.query(AiModel).filter_by(is_available=True).all()


class PromptServices(Database):
    def get_prompts(self):
        return self.session.query(Prompt).all()

    def get_prompt(self, _id: int):
        return self.session.query(Prompt).filter_by(id=_id).first()

    def add_new_prompt(self, desc: str, prompt: str):
        with self as session:
            session.add(Prompt(**{'description': prompt, 'short_desc': desc}))

    def del_prompt(self, _id: int):
        with self as session:
            session.query(Prompt).filter_by(id=_id).delete()
