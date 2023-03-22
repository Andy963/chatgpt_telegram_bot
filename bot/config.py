from pathlib import Path

import yaml

# config_dir = Path(__file__).parent.parent.resolve() / "config"
config_dir = Path('/etc/gpt')
# load yaml config
with open(config_dir / "config.yml", 'r') as f:
    config_yaml = yaml.safe_load(f)

# config parameters
telegram_token = config_yaml.get("telegram_token")
openai_api_key = config_yaml.get("openai_api_key")
use_chatgpt_api = config_yaml.get('use_chatgpt_api', True)
allowed_telegram_usernames = config_yaml.get("allowed_telegram_usernames", [])
new_dialog_timeout = config_yaml.get("new_dialog_timeout", 600)
typing_effect = config_yaml.get("typing_effect", True)
azure_speech_key = config_yaml.get("azure_speech_key", None)
azure_text_key = config_yaml.get("azure_text_key", None)
azure_speech_region = config_yaml.get("azure_speech_region", 'eastasia')
enable_message_streaming = config_yaml.get("enable_message_streaming", True)
log = '/var/log/chatgpt.log'
