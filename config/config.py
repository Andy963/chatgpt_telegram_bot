import json
import os
from pathlib import Path

import yaml

# config_dir = Path(__file__).parent.parent.resolve() / "config"
config_dir = Path('/etc/aibot')
# load yaml config
with open(config_dir / "config.yml", 'r') as f:
    config_yaml = yaml.safe_load(f)

log_dir = Path('/etc/aibot/aibot.log')
if not log_dir.exists():
    log_dir.touch()

# config parameters
telegram_token = config_yaml.get("telegram_token")
allowed_telegram_usernames = config_yaml.get("allowed_telegram_usernames", [])

openai_api_key = config_yaml.get("openai_api_key")
openai_engine = config_yaml.get("openai_engine", "gpt-3.5-turbo")
openai_session_key = config_yaml.get("openai_session_key", None)

azure_region = config_yaml.get("azure_region", 'eastasia')
azure_text2speech_key = config_yaml.get("azure_text2speech_key", None)
azure_speech2text_key = config_yaml.get("azure_speech2text_key", None)

azure_recognize_key = config_yaml.get("azure_recognize_key", None)
azure_recognize_endpoint = config_yaml.get("azure_recognize_endpoint")

azure_translate_key = config_yaml.get("azure_translate_key", None)
azure_translate_endpoint = config_yaml.get("azure_translate_endpoint", None)

azure_openai_endpoint = config_yaml.get("azure_openai_endpoint", None)
azure_openai_engine = config_yaml.get("azure_openai_engine", 'gpt-35-turbo')
azure_openai_api_version = config_yaml.get("azure_openai_api_version", None)
azure_openai_api_key = config_yaml.get("azure_openai_api_key", None)

new_dialog_timeout = config_yaml.get("new_dialog_timeout", 600)
palm_api_key = config_yaml.get('palm_api_key', None)
palm_support_zh = config_yaml.get('palm_support_zh', False)
palm_model_name = config_yaml.get('palm_model_name', 'models/chat-bison-001')
claude_api_key = config_yaml.get('claude_api_key', None)
claude_model_name = config_yaml.get('claude_model_name', 'claude-2')
ai_models = config_yaml.get("ai_models", None)

root_user_id = config_yaml.get("root_user_id", None)  # set telegram user admin
config_file = config_yaml.get('chat_mode_path', Path(config_dir /
                                                     'chat_mode.json'))
if not config_file.exists():
    with open(config_file, 'r') as f:
        chat_mode = json.load(f)
else:
    with open('./config/chat_mode.json', 'r') as f:
        chat_mode = json.load(f)
log = '/etc/aibot/aibot.log'
