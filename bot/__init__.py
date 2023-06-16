from ai.anthropic_utils import AnthropicAIService
from ai.google_utils import GoogleAIService
from ai.openai_utils import OpenAIService
from bot.helper import AzureService
from config import config
from database import engine
from database.model_view import UserServices, DialogServices, ModelServices, PromptServices

azure_service = AzureService()
gpt_service = OpenAIService(model_name=config.openai_engine, api_type='chatgpt')
azure_openai_service = OpenAIService(model_name=config.azure_openai_engine, api_type='azure')
palm_service = GoogleAIService(api_key=config.palm_api_key)
anthropic_service = AnthropicAIService(api_key=config.claude_api_key)

user_db = UserServices(engine)
dialog_db = DialogServices(engine)
ai_model_db = ModelServices(engine)
prompt_db = PromptServices(engine)
