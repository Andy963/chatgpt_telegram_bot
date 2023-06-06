from pathlib import Path

import yaml

# config_dir = Path(__file__).parent.parent.resolve() / "config"
config_dir = Path('/etc/gpt')
# load yaml config
with open(config_dir / "config.yml", 'r') as f:
    config_yaml = yaml.safe_load(f)

# config parameters
telegram_token = config_yaml.get("telegram_token")
telegram_typing_effect = config_yaml.get("telegram_typing_effect", True)
allowed_telegram_usernames = config_yaml.get("allowed_telegram_usernames", [])

openai_api_key = config_yaml.get("openai_api_key")
openai_engine = config_yaml.get("openai_engine", "gpt-3.5-turbo")
openai_response_streaming = config_yaml.get("openai_response_streaming", True)
openai_session_key = config_yaml.get("openai_session_key", None)

azure_text2speech_key = config_yaml.get("azure_text2speech_key", None)
azure_speech2text_key = config_yaml.get("azure_speech2text_key", None)
azure_recognize_key = config_yaml.get("azure_recognize_key", None)
azure_recognize_endpoint = config_yaml.get("azure_recognize_endpoint")
azure_bing_key = config_yaml.get("azure_bing_key", None)
azure_bing_endpoint = config_yaml.get("azure_bing_endpoint")
azure_region = config_yaml.get("azure_region", 'eastasia')
azure_translate_key = config_yaml.get("azure_translate_key", None)
azure_translate_endpoint = config_yaml.get("azure_translate_endpoint", None)
azure_openai_endpoint = config_yaml.get("azure_openai_endpoint", None)
azure_openai_api_version = config_yaml.get("azure_openai_api_version", None)
azure_openai_api_key = config_yaml.get("azure_openai_api_key", None)

new_dialog_timeout = config_yaml.get("new_dialog_timeout", 600)
palm_api_key = config_yaml.get('palm_api_key', None)
ai_models = config_yaml.get("ai_models", None)

log = '/etc/gpt/chatgpt.log'

