from ai import chatgpt, palm2
from bot.helper import AzureService
from config import config
from database import engine
from database.model_view import UserServices, DialogServices, ModelServices, PromptServices

azure_service = AzureService()
gpt_service = chatgpt.ChatGPT(model_name=config.openai_engine, use_stream=config.openai_response_streaming)
palm_service = palm2.GooglePalm()

user_db = UserServices(engine)
dialog_db = DialogServices(engine)
ai_model_db = ModelServices(engine)
prompt_db = PromptServices(engine)