import traceback

import requests

from bot import config
from bot.log import logger


class BingSearch:
    headers = {"Ocp-Apim-Subscription-Key": config.azure_bing_key}
    search_url = config.azure_bing_endpoint

    def search_web(self, search_term: str = None):
        params = {"q": search_term, "textDecorations": True, "textFormat": "HTML"}
        try:
            response = requests.get(self.search_url, headers=self.headers, params=params)
            response.raise_for_status()
            search_results = response.json()
            return search_results['webPages']['value']
        except Exception as ex:
            logger.error(f"Error when searching {search_term}, {ex}")
            logger.error(f"error trace:{traceback.format_exc()}")
        return []
