from pathlib import Path

import yaml

# config_dir = Path(__file__).parent.parent.resolve() / "config"
config_dir = Path('/etc/gpt')
# load yaml config
with open(config_dir / "config.yml", 'r') as f:
    config_yaml = yaml.safe_load(f)

# config parameters
telegram_token = config_yaml["telegram_token"]
openai_api_key = config_yaml["openai_api_key"]
use_chatgpt_api = config_yaml.get('use_chatgpt_api', True)
allowed_telegram_usernames = config_yaml["allowed_telegram_usernames"]
new_dialog_timeout = config_yaml["new_dialog_timeout"]
default_language = config_yaml.get("default_language", 'en')
typing_effect = config_yaml["typing_effect"]
azure_speech_key = config_yaml["azure_speech_key"]
azure_speech_region = config_yaml["azure_speech_region"]
azure_speech_lang = config_yaml["azure_speech_lang"]
azure_speech_voice = config_yaml["azure_speech_voice"]
reply_with_voice = config_yaml["reply_with_voice"]

log = '/var/log/chatgpt.log'
