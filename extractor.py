import re
from typing import List, Set

# Regex matches:
# 1. Standard 8-character uppercase Crypto Box codes (e.g. BP88ZKL9, 7XQ12WAA)
# 2. Direct Binance share links (e.g. s.binance.com/xxxxxx or binance.com/en/my/wallet/account/payment/cryptobox?code=XXXXX)
CODE_REGEX = re.compile(r'\b[A-Za-z0-9]{8}\b')
BINANCE_LINK_REGEX = re.compile(r'(?:s\.binance\.com/([A-Za-z0-9]+)|code=([A-Za-z0-9]{8}))', re.IGNORECASE)

EXCLUDED_WORDS: Set[str] = {
    "ETHEREUM", "BINANCEE", "TRANSFER", "AIRDROPS", "BITCOINS", 
    "WITHDRAW", "DEPOSITS", "DISCOUNT", "VOUCHERS", "TELEGRAM",
    "RECEIVED", "SENDINGS", "EXCHANGE", "CAMPAIGN", "PLATFORM",
    "REMINDER", "REGISTER", "SECURITY", "PASSWORD", "SETTINGS",
    "ACTIVITY", "OFFICIAL", "ANNOUNCE", "TOMORROW", "YESTERDAY",
    "COMPLETE", "QUESTION", "SCHEDULE", "STARTING", "DOWNLOAD"
}

def extract_codes(text: str) -> List[str]:
    """
    Extracts all Binance Crypto Box codes, including direct links and inline text.
    """
    if not text:
        return []

    candidates = []

    # 1. Extract from direct binance short links (e.g. s.binance.com/xyz)
    for m in BINANCE_LINK_REGEX.finditer(text):
        link_code = m.group(1) or m.group(2)
        if link_code:
            candidates.append(link_code.upper())

    # 2. Extract standard 8-character alphanumeric codes
    found = CODE_REGEX.findall(text)
    for code in found:
        upper = code.upper()
        if upper in EXCLUDED_WORDS:
            continue
        # Accept if starts with BP or has at least one number
        if upper.startswith("BP") or any(c.isdigit() for c in upper):
            candidates.append(upper)

    return list(dict.fromkeys(candidates))
