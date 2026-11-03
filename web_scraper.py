import re
import json
import logging
import urllib.request
from typing import List, Dict, Any
from extractor import extract_codes

logger = logging.getLogger("WebScraper")

# Web sources that publish fresh Binance Crypto Box & Red Packet codes
WEB_DROP_SOURCES = [
    {
        "name": "Binance Square Public Feeds",
        "url": "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=48&pageNo=1&pageSize=10",
        "type": "json"
    },
    {
        "name": "Crypto Giveaway Aggregator",
        "url": "https://api.allorigins.win/raw?url=https://coingabbar.com/en/crypto-giveaway-airdrop",
        "type": "html"
    }
]

class WebRedPacketScraper:
    def __init__(self, storage):
        self.storage = storage

    def scrape_web_source(self, url: str) -> str:
        """Fetches webpage content with safe browser User-Agent headers."""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            logger.debug(f"Web source {url} fetch error: {e}")
            return ""

    def harvest_web_codes(self) -> List[str]:
        """Scrapes web sources and ingests discovered 8-char codes directly into storage."""
        new_codes = []
        for src in WEB_DROP_SOURCES:
            raw_content = self.scrape_web_source(src["url"])
            if not raw_content:
                continue

            extracted = extract_codes(raw_content)
            for code in extracted:
                if not self.storage.is_known(code):
                    logger.info(f"🌐 [WEB DROP DISCOVERED] Code: {code} from {src['name']}")
                    self.storage.add_code(code, source=src["name"])
                    new_codes.append(code)

        return new_codes

